"""Spokane: the Spokane Regional Transportation Management Center's cameras (City of Spokane, Spokane Valley, Spokane
County and WSDOT's Eastern Region), from the GraphQL API its travel map (www.srtmc.org/trafficmap, a Castle Rock
platform) uses. SRTMC's own cameras are video cameras: a still on images.srtmc.org and HLS from Wowza (streamlock.net).
The map also shows WSDOT's eastern road-weather cameras, copied to public.carsprogram.org; those are left to wa_wsdot.
A camera is known by its picture's name (a GUID)."""

import json
import re
from urllib.parse import urlparse

SOURCE = {
    "name": "Spokane Regional Transportation Management Center (SRTMC)",
    "state": "WA",
    "covers": "Spokane and Spokane Valley streets, Spokane County roads, and I-90, US 2, US 195 and US 395 around Spokane",
    "site": "https://www.srtmc.org/trafficmap/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the GraphQL query (mapFeaturesQuery, layer normalCameras) the map makes, asked for the "
             "whole region at zoom 16 so nothing is clustered. Stills refresh about every minute; HLS is unsigned, but "
             "a few listed streams answer 404. About half the highway cameras are also in WSDOT's list as "
             "images.wsdot.wa.gov/spokane/ stills (same cameras). No terms of use are posted.",
}
API = "https://www.srtmc.org/api/graphql"
QUERY = ("query MapFeatures($input: MapFeaturesArgs!, $plowType: String) { mapFeaturesQuery(input: $input) { "
         "mapFeatures { bbox title tooltip uri features { id geometry properties type } ... on Cluster { maxZoom } "
         "__typename ... on Camera { active views(limit: 10) { uri ... on CameraView { url sources { type src } } "
         "category } } ... on Plow { views(limit: 5, plowType: $plowType) { uri ... on PlowCameraView { url } "
         "category } } } error { message type } } }")
AREA = {"north": 48.6, "south": 46.6, "east": -116.6, "west": -118.9}
LOOKING = re.compile(r"\blooking (north|south|east|west)", re.I)


def cameras(get, key=None):
    body = {"query": QUERY, "variables": {"input": {**AREA, "zoom": 16, "layerSlugs": ["normalCameras"],
                                                    "nonClusterableUris": ["dashboard"]}, "plowType": "plowCameras"}}
    data = json.loads(get(API, data=body))
    result = data["data"]["mapFeaturesQuery"]
    seen = set()
    for feature in result.get("mapFeatures") or []:
        if feature.get("__typename") != "Camera":
            continue
        views = [v for v in feature.get("views") or [] if v.get("category") == "VIDEO" and v.get("url")]
        try:
            lon, lat = feature["features"][0]["geometry"]["coordinates"][:2]
        except (KeyError, IndexError, TypeError):
            continue
        title = (feature.get("title") or "").strip()
        looking = LOOKING.search(title)
        for n, view in enumerate(views, 1):
            image = view["url"].replace(":443/", "/")
            cid = urlparse(image).path.strip("/").rsplit(".", 1)[0]
            if not cid or cid in seen:
                continue
            seen.add(cid)
            hls = next((s["src"] for s in view.get("sources") or []
                        if "mpegurl" in (s.get("type") or "").lower() and s.get("src")), None)
            yield {
                "id": cid,
                "name": f"{title} ({n})" if len(views) > 1 else title or cid,
                "lat": float(lat),
                "lon": float(lon),
                "image": image,
                "video": hls.replace(":443/", "/") if hls else None,
                "video_type": "hls" if hls else None,
                "direction": looking[1].title() if looking else None,
                "refresh": 60,
                "online": feature.get("active") is not False,
                "extra": {"camera": feature.get("uri")},
            }
