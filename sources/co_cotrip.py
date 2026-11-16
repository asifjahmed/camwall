"""Colorado: CDOT's cameras from COtrip (cotrip.org, Castle Rock's CARS 511 platform), with the cellular cameras CDOT
runs on rural highways and Douglas County's cameras. The list is the GeoJSON COtrip's own map loads
(api-511x-co.carsprogram.org/cameras/map-features). A site can have several views; each view is a camera here, known
by its stream's name or its picture's path (see _id). Most CDOT views are live video: an open HLS stream from publicstreamer*.cotrip.org
with a snapshot ("videoPreviewUrl") on cocam.carsprogram.org. The others are JPEG stills on cocam.carsprogram.org."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "CDOT (COtrip)",
    "state": "CO",
    "covers": "Colorado's interstates and state highways statewide, CDOT's rural cellular cameras, and Douglas County",
    "site": "https://www.cotrip.org/",
    "terms": "https://www.colorado.gov/privacy-statement",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented list COtrip's map loads. CDOT's documented feed (manage-api.cotrip.org, data-sharing "
             "sign-up) needs registration. HLS streams are open (no token); stream snapshots and stills update every "
             "few minutes. COtrip has no terms of use page; the State of Colorado privacy statement is linked.",
}
LIST = "https://api-511x-co.carsprogram.org/cameras/map-features"
COMPASS = {"North", "South", "East", "West", "Northeast", "Northwest", "Southeast", "Southwest"}


def _id(url):
    """The view's id: its stream's name for a live view ("070E23965CAM1RHS"), its picture's path for a still. A CDOT
    video camera whose stream is down is listed as a still of its stream's snapshot (Snapshots/<name>.flv.png), so
    that picture gets the stream's name too, and the camera keeps one id whether or not its video is up."""
    path = urlparse(url).path.strip("/")
    for prefix in ("rtplive/",):
        path = path.removeprefix(prefix)
    path = path.removesuffix("/playlist.m3u8")
    if path.startswith("Snapshots/") and path.endswith(".flv.png"):
        path = path.removeprefix("Snapshots/").removesuffix(".flv.png")
    return path


def cameras(get, key=None):
    for feature in json.loads(get(LIST)).get("features") or []:
        props = feature.get("properties") or {}
        if props.get("public") is False:
            continue
        lon, lat = (feature.get("geometry") or {}).get("coordinates") or (None, None)
        views = props.get("views") or []
        for view in views:
            url = view.get("url")
            if not url:
                continue
            name = props.get("name") or props.get("tooltip") or "Camera"
            if len(views) > 1 or (view.get("name") or "").startswith("Looking"):
                name = f"{name}: {view.get('name')}" if view.get("name") else name
            camera = {
                "id": _id(url),
                "name": name,
                "lat": lat,
                "lon": lon,
                "road": props.get("route"),
                "extra": {"site": props.get("id"), "owner": props.get("cameraOwner"), "type": view.get("type")},
            }
            if view.get("type") == "WMP":  # live video, with a snapshot
                camera.update(image=view.get("videoPreviewUrl"), video=url, video_type="hls")
            else:
                camera["image"] = url
                if "/Snapshots/" in url:  # a video camera whose stream is down (its id before 8 Nov 2026)
                    camera["extra"]["also_id"] = urlparse(url).path.strip("/")
            direction = (view.get("name") or "").removeprefix("Looking ").strip()
            if direction in COMPASS:
                camera["direction"] = direction
            place = ((props.get("location") or {}).get("cityReference") or "").strip()
            if place.startswith("in "):  # "in Golden"; not "near Golden" or "6 miles west of the Golden area"
                camera["city"] = place.removeprefix("in ")
            elif place:
                camera["extra"]["place"] = place
            if view.get("broken"):
                camera["online"] = False
            yield camera
