"""Nevada: NDOT's cameras from Nevada 511 (nvroads.com, Arcadis IBI's 511 platform), with the Las Vegas freeway and
arterial cameras NDOT and RTC run together as FAST. The list is the one the site's own camera list page loads
(/List/GetData/Cameras, paged 100 at a time); the documented API (/api/v2/get/cameras) needs a key from a sign-up.
Each camera has a JPEG still at /map/Cctv/<id>, and most have an open HLS stream from NDOT's Wowza servers
(*.its.nv.gov) that needs no token."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "NDOT (Nevada 511)",
    "state": "NV",
    "covers": "Nevada's interstates and highways statewide, and Las Vegas (FAST) freeway and arterial cameras",
    "site": "https://www.nvroads.com/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented list the site's camera list page loads; the documented API needs a key from an account "
             "(https://www.nvroads.com/developers/doc, 10 calls a minute). Stills are small JPEGs (360x240) served "
             "with max-age 60; HLS streams are open Wowza playlists (no token). A camera listed without a stream is "
             "down (its still is a 'No live camera feed' placeholder PNG) and is marked online: False. The list "
             "doesn't flag every dead camera: in November 2026 every camera sampled on the d1wse5 stream server "
             "(74 in the Las Vegas area) answered 404 for its stream, and its still was frozen at 14 April 2026. "
             "The stills are NDOT's images.its.nv.gov/images/<stream guid>.jpg, proxied without their "
             "Last-Modified header. NDOT and RTC's public Video Gateway (public.its.nv.gov) lists the same cameras. "
             "The site has no terms page, only a privacy page.",
}
BASE = "https://www.nvroads.com"
PAGE = 100


def _sites(get):
    start, seen = 0, set()
    while True:
        query = {"columns": [{"name": "id", "s": True}], "order": [{"column": 0, "dir": "asc"}],
                 "start": start, "length": PAGE, "search": {"value": ""}}
        data = json.loads(get(f"{BASE}/List/GetData/Cameras?query={quote(json.dumps(query))}&lang=en"))
        rows = data.get("data") or []
        for row in rows:
            if row.get("id") not in seen:
                seen.add(row.get("id"))
                yield row
        start += PAGE
        if not rows or start >= (data.get("recordsTotal") or 0):
            return


def _point(site):
    wkt = ((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or ""
    m = re.match(r"POINT \(([-\d.]+) ([-\d.]+)\)", wkt)
    return (float(m.group(2)), float(m.group(1))) if m else (None, None)


def _clean(text):
    text = (text or "").strip()
    return "" if text in ("N/A", "Unknown") else re.sub(r"\s+", " ", text)

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    for site in _sites(get):
        lat, lon = _point(site)
        images = site.get("images") or []
        base = _clean(site.get("location")) or _clean(site.get("roadway")) or "Camera"
        region = _clean(site.get("region"))
        for n, image in enumerate(images, 1):
            # (a few views are described only by their region, "Reno" or "Elko": the site's name says more)
            description = _clean(image.get("description"))
            name = description if description and description != region else base
            if len(images) > 1 and name == base:
                name = f"{base} (view {n})"
            video = (image.get("videoUrl") or "").replace(":443/", "/") or None
            if image.get("videoDisabled"):
                video = None
            camera = {
                "id": str(image["id"]),
                "name": name,
                "lat": lat,
                "lon": lon,
                "image": BASE + image["imageUrl"] if image.get("imageUrl") else None,
                "video": video,
                "video_type": "hls" if video else None,
                "refresh": 60,
                "extra": {"site": site.get("id"), "source": site.get("source"), "source_id": site.get("sourceId")},
            }
            if region:  # NDOT's area: Las Vegas, Reno or Elko
                camera["extra"]["region"] = region
            # NVRoads drops the stream of a camera that's down, and its still is then the platform's "No live camera
            # feed at this time" placeholder (a 540x330 PNG): every one sampled was.
            if image.get("disabled") or image.get("blocked") or not image.get("videoUrl"):
                camera["online"] = False
            road = _clean(site.get("roadway"))
            if road and road != name:
                camera["road"] = road
            if _clean(site.get("direction")):
                camera["direction"] = site["direction"]
            for field in ("county", "city"):
                if site.get(field):
                    camera[field] = site[field]
            yield camera
