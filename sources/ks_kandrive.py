"""Kansas: KDOT's cameras on KanDrive, a Castle Rock CARS 511 site, from the GraphQL map query its map runs (no key).
It also shows all of KC Scout's Kansas City cameras, on both sides of the state line, with pictures from kcscout.net
(KC Scout's own list, with video, is mo_kcscout). A camera here is one view, known by its CARS view uri
("camera/3969/2090255207"). KDOT's still cameras give a JPEG; its video cameras give a still and an HLS stream on
skyvdn.com whose token lasts 5 minutes, so resolve() asks the map again for that camera."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "KDOT (KanDrive)",
    "state": ["KS", "MO"],
    "covers": "Kansas highways statewide, with KC Scout's Kansas City cameras in Kansas and Missouri",
    "site": "https://www.kandrive.gov/list/cameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: KanDrive's /api/graphql mapFeaturesQuery (layer normalCameras) at a zoom where nothing is "
             "clustered. JPEG stills (KDOT's on kscam.carsprogram.org, KC Scout's on kcscout.net); a third of KDOT's "
             "also have HLS video with a 5-minute token (resolve()). About 27 cameras (of 603 on 8 Nov 2026) list no "
             "picture and are left out. KDOT's road-weather station cameras (the stationsNormal layer) are the same "
             "views as in normalCameras. No terms of use found on the site. KC Scout's cameras are also in mo_kcscout.",
}
API = "https://www.kandrive.gov/api/graphql"
QUERY = ("query MapFeatures($input: MapFeaturesArgs!, $plowType: String) { mapFeaturesQuery(input: $input) { "
         "mapFeatures { bbox title tooltip uri features { id geometry properties type } ... on Cluster { maxZoom } "
         "... on Sign { signDisplayType } ... on Event { priority } __typename ... on Camera { active views(limit: 5) "
         "{ uri ... on CameraView { url sources { type src } } category } } ... on Plow { views(limit: 5, plowType: "
         "$plowType) { uri ... on PlowCameraView { url } category } } } error { message type } } }")


def _features(get, north, south, east, west, zoom=12):
    body = {"query": QUERY, "variables": {"input": {"north": north, "south": south, "east": east, "west": west,
                                                    "zoom": zoom, "layerSlugs": ["normalCameras"],
                                                    "nonClusterableUris": ["dashboard"]},
                                          "plowType": "plowCameras"}}
    answer = json.loads(get(API, data=body))["data"]["mapFeaturesQuery"]
    if answer.get("error"):
        raise OSError(f"KanDrive said {answer['error']}")
    return [f for f in answer.get("mapFeatures") or [] if f.get("__typename") == "Camera"]


def _state(image):
    name = urlparse(image or "").path.rsplit("/", 1)[-1]
    if "kcscout" in (image or "") and (name.startswith("M") or (name.startswith("PTCCTV") and "KS" not in name)):
        return "MO"
    return "KS"


def _views(feature):
    points = [f["geometry"]["coordinates"] for f in feature.get("features") or []
              if (f.get("geometry") or {}).get("type") == "Point"]
    if not points:
        return
    lon, lat = points[0][:2]
    # (a view with no picture lists its url as just a cache-busting query, "?1794156300000": left out)
    views = [v for v in feature.get("views") or [] if (v.get("url") or "").split("?")[0] or v.get("sources")]
    for n, view in enumerate(views, 1):
        image = (view.get("url") or "").split("?")[0] or None
        hls = [s["src"] for s in view.get("sources") or [] if "mpegurl" in (s.get("type") or "").lower()]
        name = (feature.get("title") or feature.get("tooltip") or view["uri"]).strip()
        yield {
            "id": view["uri"],
            "name": f"{name} ({n})" if len(views) > 1 else name,
            "lat": float(lat),
            "lon": float(lon),
            "image": image,
            "video": hls[0] if hls else None,
            "video_type": "hls" if hls else None,
            "state": _state(image),
            "online": feature.get("active") is not False,
            "extra": {"camera": feature.get("uri")},
        }

EXPIRING = ("video",)  # (shipped lists keep none of these: signed stream links; resolve() looks up fresh ones)


def cameras(get, key=None):
    seen = set()
    for feature in _features(get, north=43.0, south=35.0, east=-91.0, west=-104.0):
        for cam in _views(feature):
            if cam["id"] not in seen:
                seen.add(cam["id"])
                yield cam


def resolve(get, camera, key=None):
    lat, lon = camera["lat"], camera["lon"]
    for feature in _features(get, north=lat + 0.01, south=lat - 0.01, east=lon + 0.01, west=lon - 0.01, zoom=16):
        for cam in _views(feature):
            if cam["id"] == camera["id"]:
                return {"image": cam["image"], "video": cam["video"]}
    return {"image": camera.get("image"), "video": None}
