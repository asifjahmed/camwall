"""Salem: the City of Salem's traffic cameras, from the city's open-data layer (TrafficCams on Data Salem), which gives
each camera's picture on egov.cityofsalem.net and whether it is offline. All but one of these are also on TripCheck
(or_odot, as "Salem - ..."), which mirrors the same pictures; this is the city's own list and status. A camera is known
by its picture's name ("Lancasteranddevon")."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "City of Salem Public Works",
    "state": "OR",
    "covers": "City of Salem intersections (Commercial St, Lancaster Dr, Market St, Center St)",
    "site": "https://www.cityofsalem.net/community/transportation-getting-around/traffic-road-conditions/"
            "view-traffic-cameras",
    "terms": "https://data.cityofsalem.net/datasets/trafficcams",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Documented: the city's open-data dataset 'TrafficCams' on Data Salem (data.cityofsalem.net), served as "
             "the public layer services.arcgis.com/kIA6yS9KDGqZL7U3/.../TrafficCams. JPEG stills; CAMERA_OFFLINE gives "
             "online. 22 of the 23 duplicate TripCheck's Salem cameras (the same pictures). The dataset's licence: "
             "'Development of derivative products is encouraged however copying and selling the data is prohibited.' "
             "(selling, not use, so not marked restricted).",
}
LIST = ("https://services.arcgis.com/kIA6yS9KDGqZL7U3/arcgis/rest/services/TrafficCams/FeatureServer/0/query"
        "?where=1%3D1&outFields=*&outSR=4326&f=json&orderByFields=OBJECTID&resultRecordCount=1000&resultOffset={offset}")

# Its list isn't shipped with camwall, only fetched by each install. Salem's terms: "copying and selling the
# data is prohibited".
SHIPPED = False


def cameras(get, key=None):
    offset = 0
    while True:
        page = json.loads(get(LIST.format(offset=offset)))
        features = page.get("features") or []
        for f in features:
            a, g = f.get("attributes") or {}, f.get("geometry") or {}
            image = (a.get("IMAGE_LINK") or "").strip()
            if not image.startswith("http") or g.get("x") is None:
                continue
            # (one row names a host that doesn't exist, eweb.; the picture is at the same path on egov.)
            image = image.replace("://eweb.cityofsalem.net/", "://egov.cityofsalem.net/")
            yield {
                "id": urlparse(image).path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
                "name": " ".join((a.get("INTERSECTION") or image).split()),
                "lat": float(g["y"]),
                "lon": float(g["x"]),
                "image": image,
                "city": "Salem",
                "online": (a.get("CAMERA_OFFLINE") or "No").strip().lower() != "yes",
                "extra": {k: v for k, v in {"agency": a.get("AGENCY"), "type": a.get("CAMTYPE")}.items() if v},
            }
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
