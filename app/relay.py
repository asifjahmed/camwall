"""Fetching cameras' pictures and video for the pages and the detector, from the URLs their sources list and nowhere
else. Only public addresses are reached, redirects included, so a camera list can't make this reach into the user's
own network. Connections are kept for reuse (a fresh TLS handshake costs ~0.5 s), and a picture fetched a moment ago is
shared with whoever asks next, so several viewers (pages, the detector) cost a camera's server no more than one.

HLS video is relayed by rewriting each playlist's URLs to come back here (playlist_for); only URLs a camera's own
playlists named are fetched for it."""

import base64
import binascii
import hashlib
import http.client
import json
import ipaddress
import queue
import socket
import ssl
import threading
import time
from collections import namedtuple
from urllib.parse import quote, urljoin, urlsplit

from sources import tls

TIMEOUT = 15
MAX_REDIRECTS = 3
MAX_BODY = 25 * 1024 * 1024  # a picture or playlist bigger than this isn't one
PER_HOST = 6                 # requests to one server at once
SHARE = 1.0                  # s: a picture fetched this recently is given as it is to the next to ask
CACHE_KEEP = 120             # s a picture is kept for its validators after it was last asked for
NAMED_KEEP = 180             # s a URL a playlist named may be fetched for it
STAND_IN = 3                 # cameras giving the very same picture: it's a source's "camera unavailable" stand-in
USER_AGENT = "camwall/0.1 (traffic camera viewer; +https://github.com/asifjahmed/camwall)"

Picture = namedtuple("Picture", "at body etag modified type date upstream_etag")


class Refused(OSError):
    """A URL this won't fetch."""


def _public(host, port):
    """(family, address) of host that's on the public internet; Refused if it isn't."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise OSError(f"{host}: {e.strerror}") from None
    for family, _, _, _, address in infos:
        if ipaddress.ip_address(address[0].split("%")[0]).is_global:
            return family, address
    raise Refused(f"{host} isn't on the public internet")


class _Connection(http.client.HTTPConnection):
    """A connection to an address checked to be public (resolving again could give another)."""

    def __init__(self, host, port, family, address):
        super().__init__(host, port, timeout=TIMEOUT)
        self.family, self.address = family, address

    def connect(self):
        self.sock = socket.socket(self.family, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(self.address)
        except OSError:
            self.sock.close()
            raise


class _TLSConnection(_Connection):
    context = ssl.create_default_context()

    def connect(self):
        super().connect()
        context = tls.context(self.host) or self.context  # (with its intermediate, for a server that leaves it out)
        self.sock = context.wrap_socket(self.sock, server_hostname=self.host)


_idle = {}  # (scheme, host, port) -> idle connections
_slots = {}
_slots_lock = threading.Lock()


def _slot(host):
    with _slots_lock:
        return _slots.setdefault(host, threading.BoundedSemaphore(PER_HOST))


def _connection(scheme, host, port, fresh=False):
    """An idle connection to reuse (and True), or a new one (and False); fresh: always a new one."""
    try:
        if fresh:
            raise queue.Empty
        return _idle.setdefault((scheme, host, port), queue.SimpleQueue()).get_nowait(), True
    except queue.Empty:
        family, address = _public(host, port)
        cls = _TLSConnection if scheme == "https" else _Connection
        return cls(host, port, family, address), False


def open_url(url, headers=None, method="GET"):
    """Ask for a URL, following redirects. Returns (response, connection, url it came from); the caller reads the
    response and then calls done(connection, response) or closes the connection. OSError (Refused for a URL that
    isn't public or http(s)) if it can't be had."""
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise Refused(f"not a web address: {url[:100]}")
        port = parts.port or (443 if parts.scheme == "https" else 80)
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        sent = {"User-Agent": USER_AGENT, **(headers or {})}
        with _slot(parts.hostname):
            for attempt in range(2):
                conn, reused = _connection(parts.scheme, parts.hostname, port, fresh=attempt > 0)
                try:
                    conn.request(method, target, headers=sent)
                    resp = conn.getresponse()
                    break
                except (http.client.HTTPException, OSError) as e:
                    conn.close()
                    if tls.is_missing_intermediate(e) and not attempt and tls.learn(parts.hostname, port):
                        continue  # (fetched, as browsers do: again with it)
                    if not reused or attempt:  # (a reused one may have been closed by the server while idle)
                        raise OSError(f"{parts.hostname}: {e}") from None
        if resp.status in (301, 302, 303, 307, 308) and resp.getheader("Location"):
            resp.read(MAX_BODY)
            done(conn, resp)
            url = urljoin(url, resp.getheader("Location"))
            continue
        return resp, conn, url
    raise OSError("too many redirects")


def done(conn, resp):
    """Put a connection whose response has been read back for reuse."""
    if resp.will_close or not resp.isclosed():
        conn.close()
        return
    scheme = "https" if isinstance(conn, _TLSConnection) else "http"
    _idle.setdefault((scheme, conn.host, conn.port), queue.SimpleQueue()).put(conn)


def fetch(url, headers=None):
    """(status, headers, body) for a URL."""
    resp, conn, _ = open_url(url, headers)
    try:
        body = resp.read(MAX_BODY + 1)
    except (http.client.HTTPException, OSError):
        conn.close()
        raise
    if len(body) > MAX_BODY:
        conn.close()
        raise OSError("too big")
    done(conn, resp)
    return resp.status, resp.headers, body


# ---- pictures ----

_pictures = {}  # url -> Picture
_pictures_lock = threading.Lock()
_seen_with = {}  # picture etag -> URLs that gave it (for spotting stand-ins)
_last_prune = 0.0


def _kind(body):
    if body[:2] == b"\xff\xd8":
        return "image/jpeg"
    if body[:4] == b"\x89PNG":
        return "image/png"
    if body[:4] == b"GIF8":
        return "image/gif"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    return None


def picture(url, headers=None, json_field=None, bust=False):
    """A camera's current picture: Picture(at, body, etag, ...). Its etag is made from what's in it, so a page can ask
    whether it has changed whatever the camera's server sends. json_field: the picture comes as base64 in this field of
    a JSON answer. bust: the server caches pictures for ages, so each fetch asks with a fresh query string (it's still
    known by url, for sharing and for spotting stand-ins). OSError if there's none to be had."""
    global _last_prune
    now = time.monotonic()
    with _pictures_lock:
        known = _pictures.get(url)
        if now - _last_prune > 60:
            _last_prune = now
            for old in [u for u, p in _pictures.items() if now - p.at > CACHE_KEEP]:
                del _pictures[old]
    if known and now - known.at < SHARE:
        return known
    ask = dict(headers or {})
    if known and known.upstream_etag:
        ask["If-None-Match"] = known.upstream_etag
    elif known and known.modified:
        ask["If-Modified-Since"] = known.modified
    fetch_from = f"{url}{'&' if '?' in url else '?'}_={int(time.time())}" if bust else url
    status, got, body = fetch(fetch_from, {} if bust else ask)
    if status == 304 and known:
        fresh = known._replace(at=now, date=got.get("Date") or known.date)
    elif status == 200:
        if json_field:  # (a source that gives its picture as base64 in a JSON answer)
            try:
                body = base64.b64decode(json.loads(body)[json_field] or "")
            except (ValueError, KeyError, TypeError, binascii.Error):
                raise OSError("the camera's answer had no picture in it") from None
        kind = _kind(body)
        if not kind:
            raise OSError("the camera sent something that isn't a picture")
        etag = '"' + hashlib.blake2b(body, digest_size=10).hexdigest() + '"'
        fresh = Picture(now, body, etag, got.get("Last-Modified"), kind, got.get("Date"), got.get("ETag"))
    else:
        raise OSError(f"the camera's server answered {status}")
    with _pictures_lock:
        _pictures[url] = fresh
        urls = _seen_with.setdefault(fresh.etag, set())
        if len(urls) < STAND_IN:
            urls.add(url)
        if len(_seen_with) > 20000:  # (forgets, now and then)
            _seen_with.clear()
    return fresh


def stand_in(pic):
    """Whether a picture is the same as several other cameras give: a source's stand-in for a camera that's out."""
    return len(_seen_with.get(pic.etag, ())) >= STAND_IN


# ---- HLS video ----

_named = {}  # camera key -> {url: until}: what its playlists have named
_named_lock = threading.Lock()


def _proxied(key, url):
    with _named_lock:
        _named.setdefault(key, {})[url] = time.monotonic() + NAMED_KEEP
    return f"x?u={quote(url, safe='')}"


def named(key, url):
    """Whether one of the camera's playlists named this URL lately."""
    now = time.monotonic()
    with _named_lock:
        urls = _named.get(key, {})
        for old in [u for u, until in urls.items() if until < now]:
            del urls[old]
        return url in urls


def rewrite(key, playlist_url, text):
    """An HLS playlist with every URL in it (segments, variant playlists, keys, maps) made to come back here."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            out.append(_proxied(key, urljoin(playlist_url, stripped)))
        elif 'URI="' in line:
            head, _, rest = line.partition('URI="')
            uri, _, tail = rest.partition('"')
            out.append(f'{head}URI="{_proxied(key, urljoin(playlist_url, uri))}"{tail}')
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def is_playlist(content_type, body):
    return "mpegurl" in (content_type or "").lower() or body[:7] == b"#EXTM3U"
