"""New York: the Seaway International Bridge's cameras (Seaway International Bridge Corporation, owned jointly by
Canada's Federal Bridge Corporation and the U.S. Great Lakes St. Lawrence Seaway Development Corporation), from its
Bridge Cameras page (no key). One looks down the South Channel bridge toward U.S. Customs at Rooseveltown (Massena,
NY); the other at the North Channel bridge toward Canadian Customs in Cornwall, Ontario (extra["country"] = "CA").
Stills only, about 30 seconds apart."""

import html
import re
import time
from urllib.parse import urljoin

SOURCE = {
    "name": "Seaway International Bridge Corporation",
    "state": "NY",
    "covers": "The Seaway International Bridge between Massena, NY, Akwesasne and Cornwall, ON: the South Channel "
              "bridge to U.S. Customs and the North Channel bridge to Canadian Customs",
    "site": "https://cameras.sibc.ca/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "cache_bust": True,
    "notes": "Undocumented: the cameras are the pictures on https://cameras.sibc.ca/ (linked as 'Bridge Cameras' "
             "from sibc.ca), 1920x1080 JPEG stills at /<camera>/snap_c1.jpg; the page reloads them every 30 s with a "
             "timestamp query once /check_mtime.php says they've changed, so cache_bust is set. Each picture's "
             "data-mtime (Unix time) is on the page; a camera whose picture is over an hour old is marked out of "
             "service. The page gives no positions: they're on the two bridges as OpenStreetMap draws them, so only "
             "roughly where each camera is. sibc.ca has no terms or privacy page.",
}
PAGE = "https://cameras.sibc.ca/"
PLACES = {  # camera -> lat, lon, in Canada, road
    "south": (44.9900, -74.7394, False, "NY 37 (Seaway International Bridge, South Channel)"),
    "north": (45.0081, -74.7399, True, "Seaway International Bridge (North Channel)"),
}
STALE = 3600


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", errors="replace")
    now = time.time()
    for cell in re.findall(r"<td\b.*?</td>", page, re.S):
        img = re.search(r'<img[^>]*\bsrc="(/([\w-]+)/[^"?]+)[^"]*"[^>]*>', cell)
        if not img:
            continue
        path, camera = img.group(1), img.group(2)
        label = re.search(r"<p>(.*?)<br", cell, re.S)
        name = html.unescape(re.sub(r"<[^>]+>|\s+", " ", label.group(1))).strip() if label else camera.title()
        mtime = re.search(r'data-mtime="(\d+)"', img.group(0))
        lat, lon, canada, road = PLACES.get(camera, (44.9990, -74.7390, False, "Seaway International Bridge"))
        yield {
            "id": camera,
            "name": f"Seaway International Bridge: {name}",
            "lat": lat,
            "lon": lon,
            "image": urljoin(PAGE, path),
            "road": road,
            "city": "Cornwall" if canada else "Massena",
            "county": None if canada else "St. Lawrence",
            "refresh": 30,
            "online": None if not mtime else now - int(mtime.group(1)) < STALE,
            "extra": {"country": "CA"} if canada else {},
        }
