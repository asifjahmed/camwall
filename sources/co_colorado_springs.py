"""Colorado Springs: the City's traffic cameras at intersections (and a few on I-25 and Powers Blvd), from the ArcGIS
layer behind the City's "Traffic Cameras" map (gis.coloradosprings.gov, TrafficCameras_PRO MapServer layer 0).
JPEG stills on websvc.coloradosprings.gov, which the City says refresh every 2 to 3 minutes; on 8 Nov 2026 they had
not changed since 15 Sep 2026, so check their Last-Modified before trusting them."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "City of Colorado Springs Traffic Engineering",
    "state": "CO",
    "covers": "Colorado Springs city intersections, plus some I-25 and Powers Blvd views",
    "site": "https://experience.arcgis.com/experience/71136f72e75d4814812fab2a2ef767dd",
    "terms": "https://www.arcgis.com/home/item.html?id=71136f72e75d4814812fab2a2ef767dd",
    "key": None,
    "headers": {},
    "restricted": "\"This work, and/or the data contained hereon, may not be reproduced, modified, distributed, "
                  "republished, used to prepare derivative works, publicly displayed or commercially exploited in any "
                  "manner without the prior express written consent of the City of Colorado Springs and Colorado "
                  "Springs Utilities.\" (license on the City's camera map and web map)",
    "notes": "Public ArcGIS MapServer layer (the City's own map's layer). Stills said to refresh about every 2-3 "
             "minutes, but every picture sampled on 2026-11-08 was last modified 2026-09-15 or earlier: the City's "
             "image updater looks stalled. InactiveFl=1 cameras are marked online: False.",
}
LAYER = "https://gis.coloradosprings.gov/arcgis/rest/services/TrafficCameras/TrafficCameras_PRO/MapServer/0"
PAGE = 1000


def cameras(get, key=None):
    offset = 0
    while True:
        data = json.loads(get(f"{LAYER}/query?where=1%3D1&outFields=*&outSR=4326&orderByFields=OBJECTID"
                              f"&resultOffset={offset}&resultRecordCount={PAGE}&f=json"))
        features = data.get("features") or []
        for feature in features:
            a = feature.get("attributes") or {}
            if a.get("PublicFlag") == 0 or not a.get("IMAGE_URL"):
                continue
            geometry = feature.get("geometry") or {}
            camera = {
                "id": str(a.get("ReferenceN") or a.get("Filename")),
                "name": (a.get("CameraLoca") or a.get("CAMERA_LOC") or "Camera").strip(),
                "lat": geometry.get("y") if geometry.get("y") is not None else a.get("Latitude"),
                "lon": geometry.get("x") if geometry.get("x") is not None else a.get("Longitude"),
                "image": quote(a["IMAGE_URL"].strip(), safe=":/"),
                "city": "Colorado Springs",
                "county": "El Paso",
                "refresh": 180,
            }
            if a.get("InactiveFl") == 1:
                camera["online"] = False
            yield camera
        offset += len(features)
        if not features or not data.get("exceededTransferLimit"):
            return
