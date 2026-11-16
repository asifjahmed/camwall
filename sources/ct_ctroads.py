"""Connecticut: CTDOT's cameras on CTroads (IBI's 511 platform), from the camera list its Cameras page pages through
(no key). Stills only: CTDOT's pictures come through TrafficLand, and CTroads serves them at /map/Cctv/<id>,
refreshed every 10 s. Each view says which way the traffic nearest the camera is going ("Traffic closest to the camera
is traveling SOUTH"), given as `approach`."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "CTDOT (CTroads)",
    "state": "CT",
    "covers": "Connecticut's interstates and state highways",
    "site": "https://ctroads.org/cctv",
    "terms": "https://ctroads.org/termsandconditions",
    "key": None,
    "headers": {},
    "restricted": "\"Redistribution or republication of any part of ctroads.org or its content is prohibited, including "
                  "by such methods as framing, other similar methods or by any other means, without the prior express "
                  "written consent of CTDOT.\" Its Uses section: \"ctroads.org may be used only for a lawful and "
                  "appropriate purpose by individuals seeking consumer traveler information\", and you may not \"reproduce "
                  "or publicly display, perform, or distribute or otherwise use the content for any personal, public or "
                  "commercial purpose, including without limitation use of the content on any other website\" or \"Use "
                  "any robot, spider or other similar kind of automatic program or device, or manual process to monitor, "
                  "copy, summarize, or otherwise extract information from this website\". Unlike Mass511's terms, there "
                  "is no grant for third-party traveler-information apps.",
    "notes": "Undocumented: the list CTroads' Cameras page loads (/List/GetData/Cameras, 100 a page). CTroads' developer "
             "API (free key) has signs, events and advisories but no cameras. No video: every view is marked "
             "isVideoAuthRequired but has no videoUrl, and /Camera/GetVideoUrl answers empty. `approach` comes from "
             "each view's own label (\"Traffic closest to the camera is traveling SOUTH\"); the site-level direction "
             "(kept as extra.traffic_direction) contradicts the camera's name for a few cameras, so it isn't used.",
}
BASE = "https://ctroads.org"
PAGE = 100
BOUND = {"NORTH": "Northbound", "SOUTH": "Southbound", "EAST": "Eastbound", "WEST": "Westbound"}


def _query(start):
    return quote(json.dumps({
        "columns": [{"data": None, "name": ""}, {"name": "sortOrder", "s": True}, {"name": "roadway", "s": True}],
        "order": [{"column": 1, "dir": "asc"}, {"column": 2, "dir": "asc"}],
        "start": start, "length": PAGE, "search": {"value": ""}}))

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    start, total = 0, None
    while total is None or start < total:
        page = json.loads(get(f"{BASE}/List/GetData/Cameras?query={_query(start)}&lang=en-US"))
        total = page.get("recordsTotal") or 0
        rows = page.get("data") or []
        if not rows:
            break
        start += PAGE
        for site in rows:
            wkt = ((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or ""
            point = re.match(r"POINT \((-?[\d.]+) (-?[\d.]+)\)", wkt)
            if not point or not float(point.group(1)) or not float(point.group(2)):
                continue
            views = site.get("images") or []
            for view in views:
                if not view.get("imageUrl"):
                    continue
                name = site.get("location") or site.get("roadway") or "Camera"
                going = re.search(r"traveling (NORTH|SOUTH|EAST|WEST)\b", view.get("description") or "", re.I)
                if len(views) > 1 and view.get("description"):
                    name = f"{name} ({view['description']})"
                yield {
                    "id": str(view["id"]),
                    "name": name,
                    "lat": float(point.group(2)),
                    "lon": float(point.group(1)),
                    "image": BASE + view["imageUrl"],
                    "road": site.get("roadway"),
                    "approach": BOUND[going.group(1).upper()] if going else None,
                    "city": site.get("city"),
                    "county": site.get("county"),
                    "refresh": (view.get("refreshRateMs") or 10000) / 1000,
                    "online": bool(site.get("visible", True)) and not view.get("blocked") and not view.get("disabled"),
                    "extra": {k: v for k, v in {"site_id": site.get("id"), "trafficland_id": site.get("sourceId"),
                                                "traffic_direction": site.get("direction")}.items() if v},
                }
