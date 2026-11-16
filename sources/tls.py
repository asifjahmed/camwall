"""Servers that leave their intermediate certificate out. Browsers fetch it from the address the server's certificate
names (its Authority Information Access) and carry on; Python doesn't, so their lists and pictures fail with "unable
to get local issuer certificate". learn(host) does what a browser does, once per host: it fetches that certificate
and makes a context that uses it to build the chain, which must still end at one of the system's trusted roots
(partial chains are off, and a downloaded root is never used).
"""

import ipaddress
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

CA_ISSUERS = bytes.fromhex("06082b06010505073002")  # the OID 1.3.6.1.5.5.7.48.2, caIssuers, in DER
TIMEOUT = 10
USER_AGENT = "camwall/0.1 (+https://github.com/asifjahmed/camwall)"
MAX_CERT = 64 * 1024
MAX_DEPTH = 3  # intermediates fetched at most for one host

_contexts = {}  # host -> SSLContext that has its intermediate
_failed = {}  # host -> when it couldn't be helped (not tried again for RETRY s)
RETRY = 3600
_lock = threading.Lock()


def context(host):
    """The context to reach a host with: the usual one, or one with the intermediate it leaves out."""
    return _contexts.get(host)


def is_missing_intermediate(error):
    text = str(getattr(error, "reason", error))
    return "unable to get local issuer certificate" in text or "unable to verify the first certificate" in text


def _length(der, i):
    """(length, where the content starts) of the DER element whose length byte is at i."""
    first = der[i]
    if first < 0x80:
        return first, i + 1
    n = first & 0x7F
    return int.from_bytes(der[i + 1:i + 1 + n], "big"), i + 1 + n


def _children(der, start, end):
    """(tag, element bytes) of each element directly inside der[start:end]."""
    out, i = [], start
    while i < end:
        tag = der[i]
        size, content = _length(der, i + 1)
        out.append((tag, der[i:content + size]))
        i = content + size
    return out


def _issuer_and_subject(der):
    """A certificate's issuer and subject names, as DER."""
    size, content = _length(der, 1)            # Certificate
    tbs = _children(der, content, content + size)[0][1]
    size, content = _length(tbs, 1)            # TBSCertificate
    fields = _children(tbs, content, content + size)
    if fields[0][0] == 0xA0:                   # (its version, if given)
        fields = fields[1:]
    return fields[2][1], fields[4][1]           # serial, signature, issuer, validity, subject


STRINGS = {0x0C: "utf-8", 0x13: "ascii", 0x14: "latin-1", 0x16: "ascii", 0x1A: "ascii", 0x1E: "utf-16-be",
           0x1C: "utf-32-be"}  # (DER string tags: UTF8, Printable, T61, IA5, Visible, BMP, Universal)


def _canonical(name):
    """A DER name as OpenSSL compares names, or looser: each attribute's text with its case and runs of white space
    ignored, empty ones left out, and each RDN's attributes in order. Two names OpenSSL takes for the same (so that
    a certificate with them is self-issued, a root) are always the same here; this errs towards finding them so."""
    size, content = _length(name, 1)
    rdns = []
    for _, rdn in _children(name, content, content + size):              # SET of attributes
        rsize, rcontent = _length(rdn, 1)
        attributes = []
        for _, attribute in _children(rdn, rcontent, rcontent + rsize):  # SEQUENCE: type, value
            asize, acontent = _length(attribute, 1)
            (_, kind), (tag, value) = _children(attribute, acontent, acontent + asize)[:2]
            vsize, vcontent = _length(value, 1)
            raw = value[vcontent:vcontent + vsize]
            text = raw.decode(STRINGS[tag], "replace") if tag in STRINGS else raw.hex()
            text = " ".join(text.split()).casefold()
            if text:
                attributes.append((kind, text))
        if attributes:
            rdns.append(tuple(sorted(attributes)))
    return tuple(rdns)


def _issuers_url(der):
    i = der.find(CA_ISSUERS)
    if i < 0 or der[i + len(CA_ISSUERS)] != 0x86:  # (a URI)
        return None
    size, content = _length(der, i + len(CA_ISSUERS) + 1)
    return der[content:content + size].decode("ascii", "replace")


def _public(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        return all(ipaddress.ip_address(info[4][0].split("%")[0]).is_global
                   for info in socket.getaddrinfo(parts.hostname, parts.port or 80, type=socket.SOCK_STREAM))
    except OSError:
        return False


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    """Redirects followed only to public addresses, as the first address must be."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _public(newurl):
            raise urllib.error.URLError("its issuer's address redirects off the public internet")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_PublicRedirects)


def _issuer_of(der):
    """The certificate that issued this one, fetched from the address in it; ValueError if there's none to be had, or
    it's a root (a root is never taken from a download)."""
    url = _issuers_url(der)
    if not url or not _public(url):
        raise ValueError("no address for its issuer")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _opener.open(request, timeout=TIMEOUT) as resp:
        issuer = resp.read(MAX_CERT)
    if b"-----BEGIN CERTIFICATE-----" in issuer:
        pem = re.search(rb"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", issuer, re.S)
        issuer = ssl.PEM_cert_to_DER_cert(pem.group().decode("ascii", "replace")) if pem else b""
    if issuer[:1] != b"\x30":
        raise ValueError("its issuer's certificate isn't one")
    size, content = _length(issuer, 1)
    if content + size != len(issuer):  # (exactly one certificate: never others riding along with it)
        raise ValueError("its issuer's certificate isn't one")
    name_of_issuer, subject = _issuer_and_subject(issuer)
    if _canonical(name_of_issuer) == _canonical(subject):
        raise ValueError("a root certificate is never taken from a download")
    return issuer


def _with(certs, context):
    """The context, with these certificates to build chains from, and chains that must reach a root it trusts."""
    context.verify_flags &= ~getattr(ssl, "VERIFY_X509_PARTIAL_CHAIN", 0)
    for der in certs:
        context.load_verify_locations(cadata=der)
    return context


def _verifies(host, port, context):
    """Whether the host's certificate verifies with this context (OSError if the host can't be reached)."""
    try:
        with socket.create_connection((host, port), TIMEOUT) as raw, context.wrap_socket(raw, server_hostname=host):
            return True
    except ssl.SSLCertVerificationError as e:
        if "issuer certificate" in str(e) or "self-signed" in str(e) or "self signed" in str(e):
            return False
        raise


def learn(host, port=443):
    """A context for a host that leaves its intermediate out, or None if that isn't what's wrong or it can't be had."""
    with _lock:
        if host in _contexts:
            return _contexts[host]
        if time.monotonic() - _failed.get(host, -RETRY) < RETRY:
            return None
    try:
        peek = ssl.create_default_context()
        peek.check_hostname, peek.verify_mode = False, ssl.CERT_NONE  # (just to read its certificate)
        with socket.create_connection((host, port), TIMEOUT) as raw, peek.wrap_socket(raw, server_hostname=host) as tls:
            cert = tls.getpeercert(binary_form=True)
        found = []
        for _ in range(MAX_DEPTH):  # (an intermediate can itself be issued by one the system doesn't have)
            cert = _issuer_of(cert)
            found.append(cert)
            fixed = _with(found, ssl.create_default_context())
            if _verifies(host, port, fixed):
                # The downloaded certificates on their own mustn't be enough: if they are, one of them is a root (one
                # OpenSSL takes for self-issued, whatever its names' bytes), and a root is never taken from a download.
                if _verifies(host, port, _with(found, ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))):
                    raise ValueError("a downloaded certificate would be a root")
                break
        else:
            raise ValueError("no chain to a trusted root")
    except (OSError, ValueError, IndexError, ssl.SSLError):
        with _lock:
            _failed[host] = time.monotonic()
        return None
    with _lock:
        _contexts[host] = fixed
    return fixed
