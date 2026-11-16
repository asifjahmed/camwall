"""Loveland: the City of Loveland's intersection cameras, from the ArcGIS layer behind its Cone Zone map
(services1.arcgis.com/d4MV7N9xmuHYbLrF, Traffic_Cameras_view). Each intersection has one to two pictures, labelled by
the approach they show (North, South, East, West); each is a camera here, known by its picture's number. JPEG stills
on maps.cityofloveland.org, which the City says update every three minutes."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "City of Loveland Public Works",
    "state": "CO",
    "covers": "Loveland signalized intersections",
    "site": "https://www.lovgov.org/services/public-works/cone-zone",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Public ArcGIS FeatureServer (the Cone Zone map's own layer; no license text on the item). Stills "
             "refresh about every 3 minutes (640x360). The direction is the label the City gives each picture.",
}
LAYER = "https://services1.arcgis.com/d4MV7N9xmuHYbLrF/arcgis/rest/services/Traffic_Cameras_view/FeatureServer/0"
VIEWS = ("North", "South", "East", "West", "Multi")


def cameras(get, key=None):
    offset = 0
    while True:
        data = json.loads(get(f"{LAYER}/query?where=1%3D1&outFields=*&outSR=4326&orderByFields=OBJECTID"
                              f"&resultOffset={offset}&resultRecordCount=1000&f=json"))
        features = data.get("features") or []
        for feature in features:
            a, geometry = feature.get("attributes") or {}, feature.get("geometry") or {}
            for view in VIEWS:
                url = (a.get(view) or "").strip()
                if not url.startswith("http"):
                    continue
                camera = {
                    "id": urlparse(url).path.rsplit("/", 1)[-1].removesuffix(".jpg"),
                    "name": f"{a.get('Name') or 'Intersection'} ({view})",
                    "lat": geometry.get("y"),
                    "lon": geometry.get("x"),
                    "image": url,
                    "refresh": 180,
                    "city": "Loveland",
                    "county": "Larimer",
                    "extra": {"intersection": a.get("OBJECTID")},
                }
                if view != "Multi":
                    camera["direction"] = view
                yield camera
        offset += len(features)
        if not features or not data.get("exceededTransferLimit"):
            return
