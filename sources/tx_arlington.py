"""Texas: the City of Arlington's traffic cameras, from the ArcGIS layer behind the city's "Traffic Camera Locations
Map" (no key). Arterial intersections, with stills the city updates every 5 minutes. A camera is known by its
picture's file name ("Abram_Center.jpg")."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "City of Arlington Transportation",
    "state": "TX",
    "covers": "City of Arlington arterial intersections",
    "site": "https://experience.arcgis.com/experience/a2fceb484bd04e2c9f795e8c9ce78786",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "ArcGIS FeatureServer layer Traffic_Camera_Updates_view (the city's camera map loads it; not otherwise "
             "documented). JPEG stills on webapps.arlingtontx.gov, updated every 5 minutes. TxDOT's Arlington freeway "
             "cameras (I-20, I-30, SH 360) are in tx_txdot_its and tx_drivetexas.",
}
LAYER = ("https://services.arcgis.com/jXi5GuMZwfCYtZP9/arcgis/rest/services/Traffic_Camera_Updates_view/FeatureServer/0/"
         "query?where=1%3D1&outFields=*&outSR=4326&orderByFields=ObjectId&resultRecordCount=1000&f=json&resultOffset=")


def cameras(get, key=None):
    offset = 0
    while True:
        body = json.loads(get(LAYER + str(offset)))
        features = body.get("features") or []
        for feature in features:
            a, g = feature.get("attributes") or {}, feature.get("geometry") or {}
            url = a.get("Pic_URL") or a.get("Thumb_URL")
            if not url or g.get("x") is None:
                continue
            yield {
                "id": urlparse(url).path.rsplit("/", 1)[-1],
                "name": (a.get("Camera_Location") or "Camera").strip(),
                "lat": g["y"],
                "lon": g["x"],
                "image": url,
                "city": "Arlington",
                "refresh": 300,
                "extra": {"status": a["Status"]} if a.get("Status") else {},
                "online": (a.get("Status") or "Online").strip().lower().startswith("online"),  # also "Online (Entertainment)"
            }
        if not body.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
