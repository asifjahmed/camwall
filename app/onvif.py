"""Finding IP cameras on the local network and asking them for their video and snapshot addresses, by ONVIF, which
most IP cameras speak (Hikvision, Dahua and Amcrest, Reolink, Axis, Uniview, Tapo, many more).

discover() sends a WS-Discovery probe to the local network and lists what answers; streams() asks one camera, with its
username and password, for its profiles (main stream, sub stream) and each one's RTSP and snapshot addresses.
"""

import base64
import hashlib
import os
import re
import socket
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import system

MULTICAST = ("239.255.255.250", 3702)
LISTEN = 3.0     # s to wait for cameras to answer a probe
TIMEOUT = 8      # s for a camera to answer a request

PROBE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
<e:Header><w:MessageID>uuid:{id}</w:MessageID><w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
<w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action></e:Header>
<e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body></e:Envelope>"""

ENVELOPE = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
 xmlns:trt="http://www.onvif.org/ver10/media/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
<s:Header>{security}</s:Header><s:Body>{body}</s:Body></s:Envelope>"""


def _xml(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _security(username, password):
    if not username:
        return ""
    nonce = os.urandom(16)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    digest = base64.b64encode(hashlib.sha1(nonce + created.encode() + password.encode()).digest()).decode()
    return ('<Security s:mustUnderstand="1" xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
            f"<UsernameToken><Username>{_xml(username)}</Username>"
            '<Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">'
            f"{digest}</Password>"
            '<Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">'
            f"{base64.b64encode(nonce).decode()}</Nonce>"
            f'<Created xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">{created}</Created>'
            "</UsernameToken></Security>")


def _text(node, tag):
    found = node.find(f".//{{*}}{tag}")
    return found.text.strip() if found is not None and found.text else None


def discover():
    """Cameras that answer a WS-Discovery probe on each local network: [{"address", "port", "service", "name",
    "maker", "model"}], one per camera."""
    found = {}
    sockets = []
    for address in system.local_addresses() or ["0.0.0.0"]:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        try:
            if address != "0.0.0.0":
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(address))
                s.bind((address, 0))
            s.sendto(PROBE.format(id=uuid.uuid4()).encode(), MULTICAST)
            sockets.append(s)
        except OSError:
            s.close()
    deadline = time.monotonic() + LISTEN
    try:
        while sockets and time.monotonic() < deadline:
            for s in sockets:
                s.settimeout(max(0.05, min(0.3, deadline - time.monotonic())))
                try:
                    data, (ip, _) = s.recvfrom(65535)
                except (socket.timeout, OSError):
                    continue
                try:
                    root = ET.fromstring(data)
                except ET.ParseError:
                    continue
                xaddrs = (_text(root, "XAddrs") or "").split()
                scopes = (_text(root, "Scopes") or "").split()
                service = next((x for x in xaddrs if urlsplit(x).hostname == ip), xaddrs[0] if xaddrs else None)
                if not service:
                    continue
                scope = lambda key: next((re.sub(r"%20", " ", s.rsplit("/", 1)[1]) for s in scopes
                                          if f"onvif.org/{key}/" in s), None)
                parts = urlsplit(service)
                found[ip] = {"address": ip, "port": parts.port or 80, "service": service,
                             "name": scope("name"), "maker": scope("mfr") or scope("manufacturer"), "model": scope("hardware")}
    finally:
        for s in sockets:
            s.close()
    return sorted(found.values(), key=lambda c: tuple(int(p) for p in c["address"].split(".")))


def _call(url, body, username, password):
    request = urllib.request.Request(url, data=ENVELOPE.format(security=_security(username, password), body=body).encode(),
                                     headers={"Content-Type": "application/soap+xml; charset=utf-8"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            return ET.fromstring(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if e.code in (400, 401, 500) and re.search(r"NotAuthorized|not authorized|Sender|authority", detail, re.I):
            raise PermissionError("The camera turned down that username and password") from None
        raise OSError(f"The camera answered {e.code}") from None
    except (urllib.error.URLError, socket.timeout) as e:
        raise OSError(f"The camera didn't answer ({getattr(e, 'reason', e)})") from None
    except ET.ParseError:
        raise OSError("The camera's answer wasn't ONVIF") from None


def streams(address, port, username, password, service=None):
    """A camera's device information and its profiles: {"maker", "model", "profiles": [{"name", "width", "height",
    "rtsp", "snapshot"}]} (addresses without the username and password in them). PermissionError for a wrong
    password, OSError if it can't be asked."""
    service = service or f"http://{address}:{port}/onvif/device_service"
    info = _call(service, "<tds:GetDeviceInformation/>", username, password)
    caps = _call(service, '<tds:GetCapabilities><tds:Category>Media</tds:Category></tds:GetCapabilities>', username, password)
    media = _text(caps, "XAddr") or service
    profiles = _call(media, "<trt:GetProfiles/>", username, password)
    out = []
    for profile in profiles.iter():
        if not profile.tag.endswith("}Profiles"):
            continue
        token = profile.get("token")
        if not token:
            continue
        resolution = profile.find(".//{*}Resolution")
        stream = _call(media, '<trt:GetStreamUri><trt:StreamSetup><tt:Stream>RTP-Unicast</tt:Stream><tt:Transport>'
                              f'<tt:Protocol>RTSP</tt:Protocol></tt:Transport></trt:StreamSetup><trt:ProfileToken>{_xml(token)}'
                              '</trt:ProfileToken></trt:GetStreamUri>', username, password)
        try:
            snap = _text(_call(media, f"<trt:GetSnapshotUri><trt:ProfileToken>{_xml(token)}</trt:ProfileToken></trt:GetSnapshotUri>",
                               username, password), "Uri")
        except OSError:
            snap = None
        out.append({"name": _text(profile, "Name") or token, "token": token,
                    "width": int(_text(resolution, "Width") or 0) if resolution is not None else 0,
                    "height": int(_text(resolution, "Height") or 0) if resolution is not None else 0,
                    "rtsp": _without_login(_text(stream, "Uri")), "snapshot": _without_login(snap)})
    out.sort(key=lambda p: -(p["width"] * p["height"]))
    return {"maker": _text(info, "Manufacturer"), "model": _text(info, "Model"), "profiles": out}


def _without_login(url):
    """A URL with any username and password in it taken out (camwall adds its own)."""
    if not url:
        return None
    parts = urlsplit(url)
    if parts.username is None:
        return url
    return parts._replace(netloc=parts.netloc.rsplit("@", 1)[1]).geturl()
