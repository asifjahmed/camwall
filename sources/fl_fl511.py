"""Florida: FDOT's cameras on FL511 (Arcadis IBI's 511 platform), from the camera list its List page loads (no key).
FL511 gathers FDOT's seven districts, Florida's Turnpike, the Central Florida Expressway Authority (CFX), the
Greater Miami Expressway Agency (MDX), Broward County's traffic division, the City of Tampa and the City of
Tallahassee, all fed through FDOT's DIVAS video system. Every camera has a still at /map/Cctv/<id>; most also have
HLS video whose URL needs a token the site's own page asks for (see resolve)."""

import json
import time
from urllib.parse import quote

BASE = "https://fl511.com"

SOURCE = {
    "name": "FDOT (FL511)",
    "state": "FL",
    "covers": "Florida's interstates, Turnpike, toll expressways (CFX, MDX) and major state roads in all seven FDOT "
              "districts, plus Broward County, City of Tampa and City of Tallahassee signal cameras",
    "site": "https://fl511.com/map",
    "terms": "https://fl511.com/terms",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the DataTables list behind fl511.com/list/cameras (/List/GetData/Cameras, 100 a page; it "
             "sometimes answers 500, so pages are retried). Stills are JPEG, 640x480, cached 60 s. Video is HLS on "
             "dis-se*.divas.cloud:8200 and needs a token: GET /Camera/GetVideoUrl?imageId=<id> gives a request that "
             "POSTed to divas.cloud/VDS-API/SecureTokenUri/GetSecureTokenUriBySourceId returns '?token=...' to add "
             "to the URL (the map page does this, and repeats it every minute). The video servers didn't answer when "
             "this was written (TLS times out, or the connection is reset, on port 8200), so video is unverified. The "
             "terms page is empty. The list's direction (Northbound...) is the way the traffic at the camera "
             "travels, so it's given as approach. FL511's stills are taken from the DIVAS streams, and a camera the "
             "list gives no video URL serves FL511's grey 'No live camera feed at this time' PNG (540x330) instead "
             "of a picture (16 of 16 checked on 2026-11-08, across ten districts and agencies), so those are marked "
             "out of service (594 that day, 187 of them City of Tampa's). The City of Tampa's 207 signal cameras are "
             "in District 7's feed (roadway 'for City of Tampa cameras'), as are some of the City of Tallahassee's "
             "('DIVAS-COT').",
}
TOKEN_URL = "https://divas.cloud/VDS-API/SecureTokenUri/GetSecureTokenUriBySourceId"


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
                    "approach": site.get("direction") if site.get("direction") not in (None, "", "Unknown") else None,
                    "county": site.get("county"),
                    "city": site.get("city"),
                    "refresh": 60,
                    "extra": {"source": site.get("source"), "district": site.get("dotDistrict"),
                              "region": site.get("region"), "video_auth": bool(image.get("isVideoAuthRequired"))},
                }
                if image.get("disabled") or image.get("blocked") or not image.get("videoUrl"):
                    cam["online"] = False  # (a camera with no stream serves only the "No live camera feed" picture)
                yield cam


def resolve(get, camera, key=None):
    """A fresh token for the camera's video, asked for the way the FL511 map asks for it."""
    video = camera.get("video")
    if not video or not (camera.get("extra") or {}).get("video_auth"):
        return {"image": camera.get("image"), "video": video}
    request = json.loads(get(f"{BASE}/Camera/GetVideoUrl?imageId={camera['id']}"))
    if isinstance(request, dict):
        token = json.loads(get(TOKEN_URL, data=request))
        video = video + token if isinstance(token, str) else video
    elif isinstance(request, str) and request.startswith("http"):  # the URL itself, already signed
        video = request
    return {"image": camera.get("image"), "video": video}
