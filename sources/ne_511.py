"""Nebraska: NDOT's cameras on Nebraska 511, a Castle Rock CARS site, from the GraphQL map query its map runs (no
key). A camera site has up to nine views (one per direction, often one of the road surface); each view is a camera
here, known by its CARS view uri ("camera/512/178590730"). JPEG stills only, from dot511.nebraska.gov and
public.carsprogram.org."""

import json
import re

SOURCE = {
    "name": "NDOT (Nebraska 511)",
    "state": "NE",
    "covers": "Nebraska state highways and interstates, with Omaha and Lincoln freeways",
    "site": "https://511.nebraska.gov/",
    "terms": "https://dot.nebraska.gov/policies-and-disclaimers/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: /api/graphql mapFeaturesQuery (layer normalCameras) at a zoom where nothing is clustered, "
             "as the map runs it. JPEG stills, refreshed every few minutes. direction is the view's own label (the "
             "part after the last colon of its title: North, South, Surface ...). A handful of views list no picture "
             "and are left out (1,035 views at 342 sites on 8 Nov 2026). 511.nebraska.gov and new.511.nebraska.gov "
             "serve the same app; NDOT links the first. Terms: NDOT's Policies and Disclaimers page has a Highway "
             "Camera Policy (\"The cameras and their images ... are for transportation purposes only, unless "
             "otherwise approved\"; \"Camera images are not archived\") and allows use of website information at the "
             "user's risk; nothing forbids apps or redistribution.",
}
API = "https://511.nebraska.gov/api/graphql"
QUERY = ("query MapFeatures($input: MapFeaturesArgs!, $plowType: String) { mapFeaturesQuery(input: $input) { "
         "mapFeatures { bbox title tooltip uri features { id geometry properties type } ... on Cluster { maxZoom } "
         "... on Sign { signDisplayType } ... on Event { priority } __typename ... on Camera { active views(limit: 25) "
         "{ uri ... on CameraView { url title } category } } ... on Plow { views(limit: 5, plowType: $plowType) "
         "{ uri ... on PlowCameraView { url } category } } } error { message type } } }")
COMPASS = {"north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"}


def cameras(get, key=None):
    body = {"query": QUERY, "variables": {"input": {"north": 43.5, "south": 39.5, "east": -95.0, "west": -104.5,
                                                    "zoom": 12, "layerSlugs": ["normalCameras"],
                                                    "nonClusterableUris": ["dashboard"]},
                                          "plowType": "plowCameras"}}
    answer = json.loads(get(API, data=body))["data"]["mapFeaturesQuery"]
    if answer.get("error"):
        raise OSError(f"Nebraska 511 said {answer['error']}")
    seen = set()
    for feature in answer.get("mapFeatures") or []:
        if feature.get("__typename") != "Camera":
            continue
        points = [f["geometry"]["coordinates"] for f in feature.get("features") or []
                  if (f.get("geometry") or {}).get("type") == "Point"]
        if not points:
            continue
        lon, lat = points[0][:2]
        for view in feature.get("views") or []:
            if not (view.get("url") or "").strip() or view["uri"] in seen:
                continue
            seen.add(view["uri"])
            title = (view.get("title") or feature.get("title") or view["uri"]).strip()
            label = title.rsplit(":", 1)[-1].strip() if ":" in title else ""
            road = re.match(r"^((?:I|US|N|L|S|Spur|Link)[- ]?\d+[A-Z]?)\b", feature.get("title") or "")
            yield {
                "id": view["uri"],
                "name": title,
                "lat": float(lat),
                "lon": float(lon),
                "image": view["url"].strip().split("?")[0],
                "road": road.group(1) if road else None,
                "direction": label if label.lower() in COMPASS else None,
                "online": feature.get("active") is not False,
                "extra": {"camera": feature.get("uri"), "view": label} if label else {"camera": feature.get("uri")},
            }
