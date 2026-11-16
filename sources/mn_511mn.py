"""Minnesota: MnDOT's cameras, from the camera list 511mn.org's map loads (Castle Rock's CARS "511x" platform; no key).
Each camera view is a camera here, known by its picture's name ("C704", or "C30337-v2" for an RWIS site's second
view). Traffic cameras have an HLS stream from MnDOT and a live still from MnDOT's video server; RWIS road-weather
sites have stills only, on Castle Rock's CDN. MnDOT's own IRIS list (camera_pub) adds the few public cameras 511mn
can't map because MnDOT gives them no position."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "MnDOT (511mn)",
    "state": "MN",
    "covers": "Minnesota's freeways and highways: the Twin Cities metro (RTMC), Duluth, Rochester, St. Cloud, "
              "Moorhead and the other districts, some city and county intersections MnDOT carries, and RWIS "
              "road-weather sites",
    "site": "https://511mn.org/",
    "terms": "https://www.dot.state.mn.us/information/disclaimer.html",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the GeoJSON 511mn's map loads from "
             "https://api-511x-mn.carsprogram.org/cameras/map-features (only cameras flagged public). A traffic "
             "camera's picture is MnDOT's own still (video.dot.state.mn.us/video/image/metro/<id>, made from the live "
             "video when asked, cached 10 s; it works even when the public HLS stream 404s); 511mn's own preview on "
             "public.carsprogram.org, 1-20 minutes old, is in extra['cars_image']. RWIS stills (public.carsprogram.org) "
             "change every 10-30 minutes. Video is HLS from video.dot.state.mn.us, not signed. MnDOT's documented IRIS "
             "list (https://data.dot.state.mn.us/iris/camera_pub) has 1,574 published cameras: the 1,541 sites here, "
             "11 I-394 reversible-lane gate cameras (C3901-C3913) that have no position (placed here at the MnDOT camera "
             "naming the same spot, so approximate), and 20 airport weather cameras and tests, left out. Snowplow "
             "cameras (moving) are left out. MnDOT's site disclaimer has no rule against apps; its linking policy asks "
             "that MnDOT's identity not be framed or altered.",
}
LIST = "https://api-511x-mn.carsprogram.org/cameras/map-features"
IRIS = "https://data.dot.state.mn.us/iris/camera_pub"
STILL = "https://video.dot.state.mn.us/video/image/metro/{}"
# Published IRIS cameras with no position whose spot has no positioned camera of exactly the same name: the MnDOT
# camera they're placed at instead.
NEAR = {"I-394 @ T.H.100": "C912", "I-394 @ I-94": "C917", "T.H.100 NB @ Wayzata Blvd": "C30718",
        "T.H.100 @ Wayzata Blvd": "C30718"}


def cameras(get, key=None):
    seen = set()
    for feature in json.loads(get(LIST)).get("features") or []:
        p = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if not p.get("public", True) or len(coords) < 2:
            continue
        views = p.get("views") or []
        location = p.get("location") or {}
        city = location.get("cityReference") or ""  # "in New Brighton", or "6 miles east of Luverne"
        for view in views:
            if view.get("type") == "STILL_IMAGE":
                image, video = view.get("url"), None
            else:
                image, video = view.get("videoPreviewUrl"), view.get("url")
            if video and ".m3u8" not in video:
                video = None
            if not image and not video:
                continue
            cam_id = urlparse(image).path.rsplit("/", 1)[-1] if image else urlparse(video).path.split("/")[-2]
            cam_id = cam_id.removesuffix(".stream")
            if cam_id in seen:
                continue
            seen.add(cam_id)
            extra = {k: v for k, v in (("site", p.get("id")), ("place", city)) if v}
            refresh = 600
            if video:  # MnDOT's live still, fresher than 511mn's preview
                extra["cars_image"] = image
                image, refresh = STILL.format(cam_id), 10
            yield {
                "id": cam_id,
                "name": view.get("name") or p.get("name") or "Camera",
                "lat": coords[1],
                "lon": coords[0],
                "image": image,
                "video": video,
                "video_type": "hls" if video else None,
                "road": p.get("route") or location.get("routeId") or None,
                "city": city[3:] if city.startswith("in ") else None,
                "refresh": refresh,
                "online": not view.get("broken"),
                "extra": extra,
            }
    yield from _unmapped(get, seen)


def _unmapped(get, seen):
    """Published IRIS cameras 511mn leaves off because MnDOT gives them no position, placed at the MnDOT camera that
    names the same spot (or the one NEAR names). Others (airport weather cameras, tests) are left out."""
    try:
        listed = json.loads(get(IRIS))
    except (OSError, ValueError):
        return
    placed, by_place = {}, {}
    for c in listed:
        if c.get("publish") and c.get("lat") and c.get("lon"):
            placed[c.get("name")] = c
            by_place.setdefault(c.get("location"), c)
    for c in listed:
        name, place = c.get("name"), c.get("location") or ""
        if not c.get("publish") or c.get("lat") or name in seen or not name:
            continue
        ref = by_place.get(place) or placed.get(NEAR.get(place))
        if not ref or ref.get("name") not in seen:
            continue
        seen.add(name)
        yield {
            "id": name,
            "name": place,
            "lat": ref["lat"],
            "lon": ref["lon"],
            "image": STILL.format(name),
            "video": None,
            "video_type": None,
            "road": c.get("roadway") or None,
            "refresh": 10,
            "extra": {"position": f"approximate: MnDOT gives none; placed at camera {ref['name']} ({ref.get('location')})",
                      "listed_by": "IRIS camera_pub, not on 511mn's map"},
        }
