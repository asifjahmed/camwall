"""Massachusetts: MassDOT's cameras on Mass511 (Castle Rock's CARS platform), from the camera layer its map asks the
site's GraphQL API for (no key), at a zoom where nothing is clustered.

Every camera has a still that Castle Rock copies from TrafficLand (public.carsprogram.org). Most also have TrafficLand
HLS video on the site (extra["video"] is True), but its links carry an API key that's Mass511's, so it isn't used."""

import json

SOURCE = {
    "name": "MassDOT (Mass511)",
    "state": "MA",
    "covers": "Massachusetts interstates and state highways, including Boston's tunnels and the Turnpike (I-90)",
    "site": "https://mass511.com/",
    "terms": "https://mass511.com/help/147/Mass511-Terms-Conditions",
    "key": None,
    "headers": {},
    "restricted": None,
    "no_capture": "Mass511's terms let apps \"publish such content on your applications to be utilized solely for "
                  "purposes of public facing navigation and traveler information\", but not \"Capture images "
                  "(\u201cvideo scrape\u201d or \u201cweb scrape\u201d) except as expressly authorized\"; nor "
                  "\"Charge any fee ... in connection with the content\" or \"Modify or attempt to modify the content "
                  "in any way\".",
    "notes": "Undocumented: the GraphQL query (mapFeaturesQuery, layer normalCameras) Mass511's map makes; the site's "
             "Cameras list (listCameraViewsQuery) gives the same 311 views. Terms are a Mass511 help page (id 147, "
             "served from Castle Rock's CMS). MassDOT's developer page (mass.gov, 403 when checked) says camera access "
             "for developers and third parties is arranged by email through TrafficLand (\"a unique API feed\", JPEGs "
             "every 120 s); the views' TrafficLand stream links carry Mass511's API key, so their video isn't used: "
             "stills only. extra[\"view\"] is the view's own label (NORTH, SOUTH, EAST, WEST, UNKNOWN); it mostly "
             "matches the NB/SB/EB/WB in the name but not always, and whether it is the way the camera faces is "
             "unconfirmed, so it isn't given as direction. Out-of-service cameras aren't flagged: the list calls them "
             "active, and their still is a 9,170-byte \"This image is temporarily unavailable\" card (8 of 16 tried "
             "in November 2026). A few positions are wrong in the source (camera/13139, \"I-93-NB-MM3.5-Randolph\", "
             "is placed in Springfield; 13430, 13649 and 13659 on Route 3 are 40-50 km from the towns they name).",
}
API = "https://mass511.com/api/graphql"
BOX = {"north": 43.1, "south": 41.1, "east": -69.8, "west": -73.6}
FEATURES = ("query MapFeatures($input: MapFeaturesArgs!) { mapFeaturesQuery(input: $input) { mapFeatures { title uri "
            "features { id geometry } __typename ... on Camera { active views(limit: 5) { uri ... on CameraView { url "
            "title } category } } } error { message type } } }")


def cameras(get, key=None):
    answer = json.loads(get(API, data={"query": FEATURES, "variables": {"input": {
        **BOX, "zoom": 16, "layerSlugs": ["normalCameras"], "nonClusterableUris": ["dashboard"]}}}))
    for site in ((answer.get("data") or {}).get("mapFeaturesQuery") or {}).get("mapFeatures") or []:
        if site.get("__typename") != "Camera":
            continue
        points = [f["geometry"]["coordinates"] for f in site.get("features") or []
                  if (f.get("geometry") or {}).get("type") == "Point"]
        if not points:
            continue
        lon, lat = points[0][:2]
        views = site.get("views") or []
        title = site.get("title") or "Camera"
        road, _, name = title.partition(": ")
        for view in views:
            if not view.get("url") or not view.get("uri"):
                continue
            extra = {"camera": site.get("uri"), "video": view.get("category") == "VIDEO"}
            view_title = view.get("title") or ""
            if ": " in view_title:  # "<camera title>: NORTH", the view's own label
                extra["view"] = view_title.rpartition(": ")[2].strip()
            yield {
                "id": view["uri"].removeprefix("camera/"),
                "name": name or title,
                "lat": float(lat),
                "lon": float(lon),
                "image": view["url"],
                "video": None,
                "road": road if name else None,
                "refresh": 120,
                "online": site.get("active") is not False and not view["url"].endswith("unavailable.png"),
                "extra": extra,
            }

