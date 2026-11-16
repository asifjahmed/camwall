"""North Carolina: NCDOT's cameras on DriveNC (Arcadis IBI's 511 platform since 2026, replacing TIMS), from the camera
list its List page loads (no key). It covers NCDOT's 14 highway divisions, the ferry terminals and the City of
Wilmington's signal cameras. Every camera has a still at /map/Cctv/<id>; the HLS video needs a token the site's own
page asks for (see resolve)."""

import json
import time
from urllib.parse import quote

BASE = "https://www.drivenc.gov"

SOURCE = {
    "name": "NCDOT (DriveNC)",
    "state": "NC",
    "covers": "North Carolina interstates and major routes in all 14 NCDOT divisions (Charlotte, Raleigh-Durham, "
              "the Triad, Asheville, Wilmington and the coast), ferry terminals and City of Wilmington cameras",
    "site": "https://www.drivenc.gov/cctv",
    "terms": "https://www.ncdot.gov/about-us/how-we-operate/policy-process/Pages/terms-use.aspx",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Terms: NCDOT allows copying and distributing its images \"for non-commercial use, provided they are copied and "
             "distributed without alteration\"; camwall is free and shows them unaltered, so it's on. "
             "Undocumented: the DataTables list behind drivenc.gov/cctv (/List/GetData/Cameras, 100 a page). DriveNC "
             "also has a documented API (drivenc.gov/developers/doc) that needs a free key from a registered account "
             "(10 calls a minute); the old TIMS API (eapps.ncdot.gov/services/traffic-prod/v1/cameras) now only "
             "points there. Stills are 1280x720 JPEG, cached 60 s; one changed between 1 and 2 minutes. "
             "Video is HLS on *.services.ncdot.gov:8887 and "
             "needs a token: GET /Camera/GetVideoUrl?imageId=<id> gives a request that POSTed to "
             "vds.nc.insight-atms.com/api/SecureTokenUri/GetSecureTokenUriBySourceId returns '?token=...' for the "
             "URL. The video servers didn't answer when this was written (port 8887 accepts the connection but never "
             "answers the TLS hello), so video is unverified and the checker reports the video as failed. "
             "NCDOT's ArcGIS camera layer (nc_ncdot_gis) lists some cameras this map leaves off.",
}
TOKEN_URL = "https://vds.nc.insight-atms.com/api/SecureTokenUri/GetSecureTokenUriBySourceId"


def _page(get, start):
    query = json.dumps({"columns": [], "order": [], "start": start, "length": 100, "search": {"value": ""}})
    url = f"{BASE}/List/GetData/Cameras?query={quote(query)}&lang=en-US"
    for attempt in range(4):
        try:
            return json.loads(get(url))
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 + 2 * attempt)


def _point(site):
    wkt = (((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or "")
    try:
        lon, lat = wkt[wkt.index("(") + 1:wkt.index(")")].split()
        return float(lat), float(lon)
    except ValueError:
        return None, None

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    seen, start, total = set(), 0, None
    while total is None or start < total:
        page = _page(get, start)
        total, rows = page.get("recordsTotal") or 0, page.get("data") or []
        if not rows:
            break
        start += len(rows)
        for site in rows:
            lat, lon = _point(site)
            images = site.get("images") or []
            for image in images:
                if image.get("id") in seen or not image.get("imageUrl"):
                    continue
                seen.add(image.get("id"))
                name = site.get("location") or image.get("description") or "Camera"
                if len(images) > 1 and image.get("description"):
                    name = f"{name} ({image['description']})"
                video = None if image.get("videoDisabled") else image.get("videoUrl") or None
                cam = {
                    "id": str(image["id"]),
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "image": BASE + image["imageUrl"],
                    "video": video,
                    "video_type": "hls" if video else None,
                    "road": site.get("roadway"),
                    "direction": site.get("direction"),
                    "county": site.get("county"),
                    "city": site.get("city"),
                    "refresh": 120,
                    "extra": {"source": site.get("source"), "division": site.get("dotDistrict"),
                              "video_auth": bool(image.get("isVideoAuthRequired"))},
                }
                if image.get("disabled") or image.get("blocked"):
                    cam["online"] = False
                yield cam


def resolve(get, camera, key=None):
    """A fresh token for the camera's video, asked for the way the DriveNC map asks for it."""
    video = camera.get("video")
    if not video or not (camera.get("extra") or {}).get("video_auth"):
        return {"image": camera.get("image"), "video": video}
    request = json.loads(get(f"{BASE}/Camera/GetVideoUrl?imageId={camera['id']}"))
    if isinstance(request, dict):
        token = json.loads(get(TOKEN_URL, data=request))
        video = video + token if isinstance(token, str) else video
    elif isinstance(request, str) and request.startswith("http"):
        video = request
    return {"image": camera.get("image"), "video": video}
