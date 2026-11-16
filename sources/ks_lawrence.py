"""Kansas: the City of Lawrence's traffic cameras, from the city's ArcGIS layer of detection equipment (no key), whose
CCTV cameras link a still the city publishes on assets.lawrenceks.gov. The layer is the one behind the city's
"Traffic Cameras" web map. A camera is known by the city's facility id ("DE-1000")."""

import json
import re
from urllib.parse import unquote, urlparse

SOURCE = {
    "name": "City of Lawrence Traffic",
    "state": "KS",
    "covers": "City of Lawrence signalized intersections",
    "site": "https://lawrenceks.maps.arcgis.com/apps/instant/basic/index.html?appid=d7c108bb6a0c405aa50a3e8168102b75",
    "terms": "https://www.lawrenceks.gov/Copyright",
    "key": None,
    "headers": {},
    "restricted": None,
    "credit": "City of Lawrence, Kansas",
    "notes": "ArcGIS FeatureServer Traffic_Cameras (layer 4, Detection Equipment), the layer the city's camera map "
             "(lawrenceks.gov/Community/View/Traffic-Cameras) uses. JPEG stills, refreshed every few minutes (about "
             "15 minutes old when checked). A camera that isn't feeding serves a 330x330 \"NO IMAGE AVAILABLE\" JPEG "
             "(5 of 13 sampled on 8 Nov 2026, the layer marking them in service like the rest). The layer's "
             "Direction and Approach fields (where on the pole, which approach) are in extra, not direction. "
             "Terms: City content \"may be used and reproduced for "
             "informational and noncommercial purposes, provided that the City of Lawrence is appropriately "
             "credited\".",
}
LAYER = ("https://services.arcgis.com/8O9UlSTnqjKptoda/arcgis/rest/services/Traffic_Cameras/FeatureServer/4/query?"
         "where=Hyperlink+IS+NOT+NULL&outFields=*&outSR=4326&orderByFields=OBJECTID&f=json&resultOffset=")


def cameras(get, key=None):
    offset = 0
    while True:
        body = json.loads(get(LAYER + str(offset)))
        features = body.get("features") or []
        for feature in features:
            a, g = feature.get("attributes") or {}, feature.get("geometry") or {}
            url = (a.get("Hyperlink") or "").strip()
            if not url.startswith("http") or g.get("x") is None:
                continue
            place = re.sub(r"^GEN_|\.jpe?g$", "", unquote(urlparse(url).path.rsplit("/", 1)[-1]), flags=re.I)
            yield {
                "id": a.get("FacilityID") or place,
                "name": place or a.get("FacilityID") or "Camera",
                "lat": g["y"],
                "lon": g["x"],
                "image": url,
                "city": "Lawrence",
                "county": "Douglas",
                "online": a.get("Status") in (8, 16, None),
                "extra": {k: v for k, v in {"mount": a.get("Direction"), "approach": a.get("Approach"),
                                            "pole": a.get("Pole_ID"), "comments": a.get("Comments")}.items() if v},
            }
        if not body.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
