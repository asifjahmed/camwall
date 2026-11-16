"""Wyoming: WYDOT's web cameras, from the camera feed WYDOT's 511 map (map.wyoroad.info/511-map) loads. Each site has
two to six views (the road each way and the road surface); each view is a camera, known by WYDOT's picture id.

The feed is a small protobuf file whose name is hashed per release (wti511map-data/Msg-XXXXXXXX.pbf) and, like the
strings in it, is lightly obfuscated in the map's JavaScript: base64, XORed with a key that sits in the same bundle.
This module finds the feed the way the page does: it reads the map page, its app entry and the node bundle that
defines the WebCamerasLayer, takes the layer's feed URL and the key, and decodes them. The pictures
(www.wyoroad.info/web-cam/cache?ref=...) are the same URLs WYDOT's plain HTML camera pages
(/pls/Browse/WRR.Cameras) use, and their refs are stable."""

import base64
import re
import struct

SOURCE = {
    "name": "WYDOT (WYDOT 511)",
    "state": "WY",
    "covers": "Wyoming's interstates and highways statewide: WYDOT's road and road-weather web cameras",
    "site": "https://map.wyoroad.info/511-map/",
    "terms": "https://www.wyoroad.info/disclaimer.html",
    "key": None,
    "headers": {},
    "restricted": "Each picture is stamped 'Copyright (c) 2026 State of Wyoming. All rights reserved.', and Visit "
                  "Laramie's webcam pages say 'WYDOT no longer allows hotlinking of their webcam images'. The list is "
                  "decoded from what WYDOT's own map loads.",
    "notes": "Undocumented feed the 511 map loads; its URL is hashed per release and obfuscated in the map's JS, so "
             "the adapter re-derives it from the bundle each run (falling back to the last known name). WYDOT also "
             "lists the same pictures (all 758 as of Nov 2026), without coordinates, at "
             "https://www.wyoroad.info/pls/Browse/WRR.Cameras. JPEG stills, no Last-Modified header; WYDOT's camera "
             "pages say they 'should update every few minutes or so'. A view that is down serves an 800x450 card "
             "('This image is temporarily unavailable', 32,426 bytes) while the feed still lists it; the feed has "
             "no out-of-service flag. Disclaimer: data 'as is', no restrictions on use. But each picture is stamped "
             "'Copyright (c) 2026 State of Wyoming. All rights reserved.', and Visit Laramie's webcam pages say "
             "'WYDOT no longer allows hotlinking of their webcam images' (since WYDOT's 2024 switch to encrypted "
             "refs); WYDOT itself publishes no such rule, so restricted is left unset.",
}
MAP = "https://map.wyoroad.info/511-map/"
FALLBACK_FEED = "https://map.wyoroad.info/wti511map-data/Msg-FFBK373B.pbf"  # as of 2026-11-08
FALLBACK_KEY = b"EkhJp6wsgahsqkiw5nahFOSCwAND1zhZ"
COMPASS = {"North", "South", "East", "West", "Northeast", "Northwest", "Southeast", "Southwest"}


def _xor(text, key):
    data = base64.b64decode(text)
    return bytes(c ^ key[i % len(key)] for i, c in enumerate(data)).decode("utf-8", "replace")


def _feed(get):
    """The camera feed's URL and the key that decodes it and its strings, read from the map's own JavaScript."""
    try:
        page = get(MAP).decode("utf-8", "replace")
        app = re.search(r"/511-map/_app/immutable/entry/app\.[\w-]+\.js", page).group(0)
        nodes = sorted(set(re.findall(r"nodes/\d+\.[\w-]+\.js", get("https://map.wyoroad.info" + app).decode())),
                       key=lambda n: -int(re.search(r"\d+", n).group(0)))
        for node in nodes:
            js = get(f"{MAP}_app/immutable/{node}").decode("utf-8", "replace")
            layer = js.find("custom.layers.WebCamerasLayer")
            if layer < 0:
                continue
            name = re.findall(r"geometryURL=\w+\((\w+)\)", js[max(0, layer - 3000):layer])[-1]
            value = re.search(r"\b" + re.escape(name) + r"=`([A-Za-z0-9+/=]+)`", js).group(1)
            for key in re.findall(r"new TextEncoder\(\)\.encode\(`([^`]+)`\)", js):
                url = _xor(value, key.encode())
                if re.match(r"https://[\w.-]+/[\w./-]+\.pbf$", url):
                    return url, key.encode()
    except (OSError, AttributeError, IndexError, ValueError):
        pass
    return FALLBACK_FEED, FALLBACK_KEY


def _varint(data, i):
    result = shift = 0
    while True:
        byte = data[i]
        i += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return result, i


def _fields(data):
    """A protobuf message's fields, as (number, value): ints, doubles and bytes."""
    i = 0
    while i < len(data):
        tag, i = _varint(data, i)
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            value, i = _varint(data, i)
        elif wire == 1:
            value, i = struct.unpack("<d", data[i:i + 8])[0], i + 8
        elif wire == 5:
            value, i = struct.unpack("<f", data[i:i + 4])[0], i + 4
        elif wire == 2:
            size, i = _varint(data, i)
            value, i = data[i:i + size], i + size
        else:
            raise ValueError(f"protobuf wire type {wire}")
        yield number, value


def cameras(get, key=None):
    url, secret = _feed(get)
    for number, site_bytes in _fields(get(url)):
        if number != 1:
            continue
        site, views = {}, []
        for field, value in _fields(site_bytes):
            if field == 3:
                views.append(dict(_fields(value)))
            else:
                site[field] = value
        lat, lon = site.get(9), site.get(8)
        site_name = _xor(site[2], secret) if site.get(2) else ""
        for view in sorted(views, key=lambda v: v.get(4, 0)):
            if not view.get(3):
                continue
            name = _xor(view[2], secret) if view.get(2) else site_name
            camera = {
                "id": str(view.get(1)),
                "name": name,
                "lat": lat,
                "lon": lon,
                "image": _xor(view[3], secret),
                "extra": {"site": site.get(1), "site_name": site_name},
            }
            road = re.match(r"(I|US|WYO) \d+[A-Z]?\b", name)
            if road:
                camera["road"] = road.group(0)
            direction = name.rsplit(" - ", 1)[-1].strip() if " - " in name else ""
            if direction in COMPASS:
                camera["direction"] = direction
            yield camera
