"""Public traffic cameras across the United States, one module per source: a state DOT's 511 system, a city's traffic
department, a toll road, a bridge authority. A source module defines

    SOURCE = {
        "name": "Caltrans",                       # who runs the cameras
        "state": "CA",                            # its two-letter state (DC and PR too); a list if it spans several
        "covers": "California state highways",    # what it covers
        "site": "https://quickmap.dot.ca.gov/",   # the public page that shows them
        "terms": "https://...",                   # its terms of use (None if it has none)
        "key": None,                              # or how to get the free key it needs: "https://... (free sign-up)"
        "headers": {},                            # headers its pictures and video need (never ones that pretend to be
                                                  # the agency's own page: see CONTRIBUTING.md)
        "restricted": None,                       # or what its terms forbid, quoted ("no automated access ...")
        "no_capture": None,                       # or why its pictures mustn't be saved, quoted (alerts save them)
        "credit": None,                           # or the credit its terms ask for, shown with its pictures
        "disclaimer": None,                       # or the disclaimer its terms ask to be repeated with that credit
        "notes": "...",                           # anything else worth knowing (how often it updates, gaps)
        "cache_bust": False,                      # True if its pictures are cached so long that each fetch needs a
                                                  # fresh query string to get the current one
        "image_json": None,                       # or the field of a JSON answer that holds the picture, base64, for
    }                                             # a source whose image URLs answer with JSON

    def cameras(get, key=None):
        yield {"id": "1042", "name": "I-5 at Main St", "lat": 38.58, "lon": -121.49, "image": "https://...jpg"}

get(url, headers=None, data=None, method=None) fetches a URL and returns its body (bytes); data (bytes, or a dict or
list sent as JSON) makes it a POST. It raises OSError on an HTTP error or a timeout. A camera is a dict with

    id          its id within the source: the same camera must get the same id every time (not a list position)
    name        what it shows, as the source names it ("I-5 at Main St")
    lat, lon    where it is (floats)
    image       the URL of its still picture (JPEG, PNG or GIF), or None
    video       the URL of its live video, or None
    video_type  "hls" (an .m3u8 playlist) or "mjpeg", when it has video
    state       its state, when SOURCE["state"] is a list

and, when the source says: road, direction (the way the camera faces), approach (the traffic it watches, as the
source labels it: "Northbound"), county, city, refresh (how often its picture changes, in seconds), online (False for a
camera the source lists as out of service) and extra (a dict of anything else).

A source whose URLs expire (signed or tokenized video links) also defines resolve(get, camera, key=None), which
returns {"image": ..., "video": ..., "video_type": ...} with fresh ones for when the camera is opened. Such a camera can
be listed with video None and its video_type, to say it has video that resolve() gives. If its listed links are
tokens that expire, it says so with EXPIRING = ("video",) or ("image",), so that the lists shipped with camwall keep
none of them (no video link; pictures without their query): resolve() mustn't need them.

python3 -m sources.check <module> runs a source, checks what it gives and saves it to sources/out/<module>.json.
"""

import json
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from urllib.parse import urlparse

from . import tls

USER_AGENT = "camwall/0.1 (traffic camera viewer; +https://github.com/asifjahmed/camwall)"
TIMEOUT = 30
MIN_GAP = 0.25  # seconds between requests to one host
MAX_BODY = 64 * 1024 * 1024  # bytes of an answer, as sent and unpacked (the biggest lists are a few MB)
_last = {}  # host -> when it was last asked


def get(url, headers=None, data=None, method=None):
    """A URL's body, as bytes. OSError if the server answers with an error or doesn't answer in time."""
    if isinstance(data, (dict, list)):
        data = json.dumps(data).encode()
        headers = {"Content-Type": "application/json", **(headers or {})}
    host = urlparse(url).hostname or ""
    wait = _last.get(host, 0) + MIN_GAP - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    request = urllib.request.Request(url, data=data, method=method, headers={
        "User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate", **(headers or {})})
    try:
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT, context=tls.context(host)) as resp:
                body, encoding = _read(resp)
        except urllib.error.URLError as e:  # (a server leaving its intermediate certificate out: fetched, as browsers do)
            if not tls.is_missing_intermediate(e) or not (fixed := tls.learn(host, urlparse(url).port or 443)):
                raise
            with urllib.request.urlopen(request, timeout=TIMEOUT, context=fixed) as resp:
                body, encoding = _read(resp)
    except urllib.error.HTTPError as e:
        raise OSError(f"{url}: HTTP {e.code} {e.reason}") from None
    except urllib.error.URLError as e:
        raise OSError(f"{url}: {e.reason}") from None
    finally:
        _last[host] = time.monotonic()
    if encoding == "gzip":
        body = _unpacked(url, body, 16 + zlib.MAX_WBITS)
    elif encoding == "deflate":
        try:
            body = _unpacked(url, body, zlib.MAX_WBITS)
        except OSError:  # (raw deflate, as some servers send it)
            body = _unpacked(url, body, -zlib.MAX_WBITS)
    return body


def _read(resp):
    body = resp.read(MAX_BODY + 1)
    if len(body) > MAX_BODY:
        raise OSError(f"{resp.url}: answered more than {MAX_BODY >> 20} MB")
    return body, resp.headers.get("Content-Encoding", "")


def _unpacked(url, body, wbits):
    """A compressed answer unpacked, up to MAX_BODY (OSError beyond: a small answer can unpack to gigabytes), every
    member of it if it has several; OSError if it's cut short or isn't compressed after all."""
    unpacked = b""
    try:
        while body:
            member = zlib.decompressobj(wbits)
            unpacked += member.decompress(body, MAX_BODY + 1 - len(unpacked))
            if len(unpacked) > MAX_BODY:
                raise OSError(f"{url}: unpacks to more than {MAX_BODY >> 20} MB")
            if not member.eof:
                raise OSError(f"{url}: its compressed answer is cut short")
            body = member.unused_data.lstrip(b"\0") if wbits > zlib.MAX_WBITS else b""  # (gzip: the next member)
    except zlib.error as e:
        raise OSError(f"{url}: its answer says it's compressed but isn't ({e})") from None
    return unpacked


NOT_SOURCES = {"check", "tls"}  # (modules here that aren't camera sources)


def modules():
    """The source modules' names."""
    return sorted(p.stem for p in Path(__file__).parent.glob("*.py") if not p.stem.startswith("_") and p.stem not in NOT_SOURCES)
