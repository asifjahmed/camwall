"""Longmont: the City of Longmont's street cameras (the ones its Snow & Ice Control team watches, part of its road
weather stations), shown on the City's "Street Cameras" page as Ivideon public-camera embeds. The list is that page's
embeds (camera ids and the City's names for them). Positions come from the City's ArcGIS layer of camera locations
(services1.arcgis.com/Sb0rgSd67ecLKIvl, Traffic_Cameras), except for the cameras the layer lacks or places at an old
spot, which were placed from the City's own street centerlines (Streets layer, same org) on 8 Nov 2026.

Pictures and video come from Ivideon's public-camera API, with the "public" access token the City's embeds use:
live_preview answers with a redirect to a fresh full-HD JPEG, live_stream (format=hls) with a redirect to a fresh,
tokenized HLS playlist. Both links here are stable; the redirect gives a new token each time."""

import json
import re
from html import unescape

SOURCE = {
    "name": "City of Longmont Public Works (street cameras)",
    "state": "CO",
    "covers": "Longmont arterial intersections (Main St, Hover St, Airport Rd, Pace St, County Line Rd)",
    "site": "https://longmontcolorado.gov/information/webcams/street-cameras/",
    "terms": "https://longmontcolorado.gov/terms-of-use/",
    "key": None,
    "headers": {},
    "restricted": "City of Longmont terms of use: users may not \"distribute the text or graphics to others without the "
                  "express written permission of the City of Longmont\" or \"mirror or copy this information to another "
                  "server without permission\"; \"Commercial use of the materials is prohibited without the written "
                  "permission of the City of Longmont.\" The cameras are hosted on Ivideon, whose terms "
                  "(https://www.ivideon.com/terms-of-service/) forbid users to \"use any automated tool (e. g., robots, "
                  "spiders) to use the Service\" or \"compile or collect any Content as part of a database\".",
    "notes": "Undocumented: the list is the iframes on the City's Street Cameras page. Live 1920x1080 pictures and HLS "
             "video through Ivideon's public API (no key; the redirects carry short-lived tokens). The City says the "
             "cameras \"are intended for City business and may be added, removed, or re-aimed at anytime\"; the "
             "Main St & Jersey Ave camera looks at the St. Vrain bridge and creek. The City's separate stream-camera "
             "page adds one river camera in Lyons (McConnell Drive), left out as not a road camera.",
}
PAGE = "https://longmontcolorado.gov/information/webcams/street-cameras/"
LAYER = "https://services1.arcgis.com/Sb0rgSd67ecLKIvl/arcgis/rest/services/Traffic_Cameras/FeatureServer/0"
API = "https://openapi-alpha.ivideon.com/cameras/{}"
# Placed from the City's street centerlines: missing from the location layer, or the layer has the camera's old spot
# (589824 is at Hover & 3rd there, but the City's page and the picture's caption say Hover & Nelson).
PLACED = {
    "589824": (40.152419, -105.130653),   # Hover St & Nelson Rd
    "917504": (40.147978, -105.102505),   # Main St (US 287) & Jersey Ave
    "1310720": (40.160363, -105.055340),  # County Line Rd & Ken Pratt Blvd (SH 119)
}


def _embed(src):
    """(server, camera) from an Ivideon embed URL, in either of its two forms."""
    src = unescape(src)
    m = re.search(r"server=([\w-]+).*?camera=(\d+)", src) or re.search(r"/embed/v3/([\w-]+):(\d+)", src)
    return m.groups() if m else None


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", "replace")
    located = {}
    for feature in json.loads(get(f"{LAYER}/query?where=1%3D1&outFields=*&outSR=4326&f=json")).get("features") or []:
        a, g = feature.get("attributes") or {}, feature.get("geometry") or {}
        found = _embed(a.get("URL") or "")
        if found and g.get("y") is not None:
            located[found[1]] = (g["y"], g["x"], a.get("Name"))
    seen = set()
    for src, title in re.findall(r"<iframe[^>]*src=\"([^\"]*ivideon[^\"]*)\"[^>]*title=\"([^\"]*)\"", page):
        found = _embed(src)
        if not found or found[1] in seen:
            continue
        server, cam = found
        seen.add(cam)
        lat, lon = PLACED.get(cam) or located.get(cam, (None, None))[:2]
        if lat is None:
            continue
        cid = f"{server}:{cam}"
        name = re.sub(r"^Webcam of\s+", "", unescape(title)).strip() or (located.get(cam) or (0, 0, "Camera"))[2]
        yield {
            "id": cid,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": API.format(cid) + "/live_preview?op=GET&access_token=public&q=2",
            "video": API.format(cid) + "/live_stream?op=GET&access_token=public&q=2&video_codecs=h264&format=hls",
            "video_type": "hls",
            "city": "Longmont",
            "county": "Boulder",
            "extra": {"layer_name": (located.get(cam) or (0, 0, None))[2], "platform": "Ivideon"},
        }
