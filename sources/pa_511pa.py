"""Pennsylvania: 511PA's cameras (IBI's 511 platform), from the camera list its Cameras page pages through (no key).
It has PennDOT's cameras in all its districts (Philadelphia and Pittsburgh included), the Pennsylvania Turnpike
Commission's (source "PTC"), PennDOT's work-zone cameras and its RWIS road-weather cameras.

Every camera has a still (/map/Cctv/<image id>, cached for 60 s). Most have HLS video too, whose URL needs a token:
the site asks /Camera/GetVideoUrl for the camera's stream id, then Arcadis's token service for a ?token= to add to the
stream's URL, which resolve() does the same way."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "PennDOT (511PA)",
    "state": "PA",
    "covers": "Pennsylvania's state highways in all PennDOT districts, the Pennsylvania Turnpike, work zones and RWIS",
    "site": "https://www.511pa.com/cctv",
    "terms": "https://www.511pa.com/about/disclaimer",
    "key": None,
    "headers": {},
    "restricted": "\"You must not republish material from this website (including republication on other sites), or "
                  "reproduce or store material from this site in any public or private retrieval system. You must not "
                  "reproduce, duplicate, copy, sell, resell, or otherwise exploit this site or material on this site for "
                  "a commercial purpose, without the express written permission of PennDOT.\" Camera streams for third "
                  "parties are under PennDOT's Non-Exclusive Video Sharing License Agreement, given on request "
                  "(https://www.penndot.pa.gov/Doing-Business/OnlineServices/Pages/Developer-Resources.aspx).",
    "notes": "Undocumented: the list 511PA's Cameras page loads (/List/GetData/Cameras, 100 a page). PennDOT's documented "
             "feeds need an approved request. Video streams (pa-se*.arcadis-ivds.com:8200) need a short-lived token "
             "and couldn't be reached when checked (the TLS handshake times out), so video is untested. Cameras the "
             "list hides (blocked or disabled; their picture is a placeholder) are marked out of service. approach is "
             "the list's direction ('Traffic closest to camera is traveling Westbound'; 'Both Directions' kept as "
             "given).",
}
BASE = "https://www.511pa.com"
TOKENS = "https://pa.arcadis-ivds.com/api/SecureTokenUri/GetSecureTokenUriBySourceId"
PAGE = 100


def _query(start):
    return quote(json.dumps({
        "columns": [{"data": None, "name": ""}, {"name": "sortOrder", "s": True}, {"name": "roadway", "s": True}],
        "order": [{"column": 1, "dir": "asc"}, {"column": 2, "dir": "asc"}],
        "start": start, "length": PAGE, "search": {"value": ""}}))


def _point(site):
    wkt = ((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or ""
    m = re.match(r"POINT \((-?[\d.]+) (-?[\d.]+)\)", wkt)
    return (float(m.group(2)), float(m.group(1))) if m else (None, None)

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
            lat, lon = _point(site)
            if not lat or not lon:  # unplaced portable cameras sit at (0, 0)
                continue
            views = site.get("images") or []
            for view in views:
                video = view.get("videoUrl") or None
                if video and ".m3u8" not in video:
                    video = None
                name = site.get("location") or site.get("cameraName") or "Camera"
                approach = site.get("direction") if site.get("direction") not in (None, "", "Unknown") else None
                if len(views) > 1 and view.get("description"):
                    name = f"{name} ({view['description']})"
                yield {
                    "id": str(view["id"]),
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "image": BASE + view["imageUrl"] if view.get("imageUrl") else None,
                    "video": video,
                    "video_type": "hls" if video else None,
                    "road": site.get("roadway"),
                    "approach": approach,
                    "county": site.get("county"),
                    "city": site.get("city"),
                    "refresh": 60,
                    "online": bool(site.get("visible", True)) and not view.get("blocked") and not view.get("disabled"),
                    "extra": {k: v for k, v in {
                        "site_id": site.get("id"), "owner": site.get("source"), "district": site.get("district"),
                        "camera_name": site.get("cameraName"),
                        "video_token": bool(view.get("isVideoAuthRequired")) or None}.items() if v},
                }


def resolve(get, camera, key=None):
    """The camera's stream with a fresh token (the site renews it every minute or so)."""
    video = camera.get("video")
    if not video or not (camera.get("extra") or {}).get("video_token"):
        return {"image": camera.get("image"), "video": video}
    ticket = get(f"{BASE}/Camera/GetVideoUrl?imageId={camera['id']}")
    try:
        ticket = json.loads(ticket)
    except ValueError:
        return {"image": camera.get("image"), "video": None}
    if not isinstance(ticket, dict):
        return {"image": camera.get("image"), "video": ticket or None}
    token = json.loads(get(TOKENS, data=ticket))
    return {"image": camera.get("image"), "video": video + token if isinstance(token, str) else None}
