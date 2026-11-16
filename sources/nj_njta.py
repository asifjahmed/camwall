"""New Jersey: the New Jersey Turnpike Authority's cameras on the Turnpike and the Garden State Parkway, from the
camera list its Traffic Cameras page carries in its map's settings (no key). Live HLS video only; the Authority
publishes no stills."""

import html
import json
import re

SOURCE = {
    "name": "New Jersey Turnpike Authority",
    "state": "NJ",
    "covers": "The New Jersey Turnpike (with its extensions) and the Garden State Parkway",
    "site": "https://www.njta.gov/travel-resources/camera-list/",
    "terms": "https://www.njta.gov/disclaimer/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the list is embedded in the camera page's map block (data-block-config). Video only "
             "(untokenized HLS from wink.njta.com, 2 s segments); no still pictures. Some streams are down at any time (2 of "
             "8 tried answered 404, again minutes later) and the page doesn't say which. 511NJ shows NJDOT's cameras but "
             "isn't usable.",
}
PAGE = "https://www.njta.gov/travel-resources/camera-list/"
ROADS = {"turnpike": "New Jersey Turnpike", "parkway": "Garden State Parkway"}


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", errors="replace")
    for attr in re.findall(r'data-block-config="([^"]*)"', page):
        config = json.loads(html.unescape(attr))
        if config.get("mode") != "traffic-cameras":
            continue
        for tab, cams in ((config.get("initialData") or {}).get("cameras") or {}).items():
            road = ROADS.get(tab, tab)
            for cam in cams:
                if not cam.get("video_url") or not cam.get("lat") or not cam.get("lng"):
                    continue
                where = cam.get("relative_text") or "Camera"
                mile = cam.get("mile_marker")
                town = re.search(r"\(([^()]+)\)\s*$", where)  # "NJ 18 (East Brunswick Twp)"
                yield {
                    "id": str(cam["id"]),
                    "name": f"{road} MP {mile}: {where}" if mile is not None else f"{road}: {where}",
                    "lat": float(cam["lat"]),
                    "lon": float(cam["lng"]),
                    "image": None,
                    "video": cam["video_url"],
                    "video_type": "hls",
                    "road": road,
                    "city": town.group(1).strip() if town else None,
                    "extra": {k: cam[k] for k in ("mile_marker", "relative_direction", "section") if cam.get(k)},
                }
        return
