"""Virginia: VDOT's cameras on 511 Virginia (Iteris ClearPath), from the camera lists its map loads (no key). It
includes VDOT's districts (Northern Virginia, Hampton Roads, Richmond, Salem, Staunton, Bristol, Lynchburg) and
cameras from Arlington County, the cities of Fairfax, Hampton, Newport News, Virginia Beach, Richmond, Suffolk and
Chesapeake, Elizabeth River Crossings, the James River and Coleman bridges and RMTA. Video and stills come from
Skyline's vdotcameras.com. The map's "Inactive Cameras" layer is listed too, as out of service."""

import json

SOURCE = {
    "name": "VDOT (511 Virginia)",
    "state": "VA",
    "covers": "Virginia interstates and primary routes statewide, with Northern Virginia, Hampton Roads and Richmond "
              "local and toll-facility cameras",
    "site": "https://511.vdot.virginia.gov/",
    "terms": "https://511.vdot.virginia.gov/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the map's lists 511.vdot.virginia.gov/services/511/map/array/cameras (active cameras) and "
             "services/511/map/layers/map/inactiveCams (the map's 'Inactive Cameras' layer, ~86, whose stills are a "
             "placeholder; listed here as out of service). map/layers/cameras (~10 MB, cameras along each route) "
             "names only 2 ids found in neither list. VDOT's documented feed is on SmarterRoads (smarterroads.org), "
             "which needs an account. Stills are 320x240 PNG (the listed URL redirects to "
             "snapshot.vdotcameras.com/<name>.png), changing every 1-2 minutes; video is unsigned HLS on "
             "media-sfsN.vdotcameras.com. Many stream names are long random strings and may change; the ids are "
             "VDOT's camera ids. The site's 'Privacy and Disclaimer Policy' (a popup) says nothing about the cameras.",
}
LIST = "https://511.vdot.virginia.gov/services/511/map/array/cameras"
INACTIVE = "https://511.vdot.virginia.gov/services/511/map/layers/map/inactiveCams"


def _camera(feature, inactive=False):
    p = feature.get("properties") or {}
    coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
    video = p.get("https_url") or None
    cam = {
        "id": str(p.get("id") or p.get("guid")),
        "name": p.get("description") or "Camera",
        "lat": coords[1],
        "lon": -coords[0] if (coords[0] or 0) > 0 else coords[0],  # one is listed with its sign dropped
        "image": p.get("image_url") or None,
        "video": video,
        "video_type": "hls" if video else None,
        "road": p.get("route") or None,
        "direction": p.get("direction") or None,
        "refresh": 120,
        "extra": {"jurisdiction": p.get("jurisdiction"), "stream": p.get("name"), "milepost": p.get("mrm")},
    }
    if inactive or p.get("active") is False or p.get("problem_stream"):
        cam["online"] = False
    return cam


def cameras(get, key=None):
    seen = set()
    for feature in json.loads(get(LIST)).get("data") or []:
        cam = _camera(feature)
        seen.add(cam["id"])
        yield cam
    try:
        inactive = json.loads(get(INACTIVE)).get("features") or []
    except (OSError, ValueError):
        inactive = []  # (the active list stands on its own)
    for feature in inactive:
        cam = _camera(feature, inactive=True)
        if cam["id"] not in seen:
            seen.add(cam["id"])
            yield cam
