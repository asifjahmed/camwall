"""Albuquerque: the City of Albuquerque's signal cameras that ABQRoads (abqroads.com, NMDOT's Albuquerque traveler map,
built by Real Time Solutions like NMRoads) shows in its "View Camera List" beside NMDOT's own cameras. The list is the
City's ArcGIS layer of its traffic cameras (DMD, dmdmaps.cabq.gov CABQ_Roads_Data/FeatureServer/2, 388 Axis cameras),
queried the way ABQRoads queries it: enabled = 'Yes' and a public name. Each camera's picture is
ss.abqroads.com/<image_name>.jpeg, which ABQRoads fetches with a timestamp query. Cameras without an image_name are left
out (ABQRoads would show a broken picture for them). One image_name is given to two records; the record whose name
doesn't contain any of the picture's street names is left out (in Nov 2026, "Alameda Blvd NE & Louisiana Blvd NE"
carried the Unser & Ladera picture). NMDOT's cameras on ABQRoads are the same as NMRoads' and are in nm_nmroads.

In Nov 2026 every picture sampled (10 of 45) was the City's "Camera not Available" card (one 1920x1080 file, 330,622
bytes, Last-Modified 14 Feb 2025), so the City's feed to ABQRoads looks switched off; the list has no out-of-service
flag."""

import json
import re
from collections import Counter
from urllib.parse import quote, urlencode

SOURCE = {
    "name": "City of Albuquerque (ABQRoads)",
    "state": "NM",
    "covers": "City of Albuquerque signalized intersections (the City's cameras on ABQRoads)",
    "site": "https://abqroads.com/",
    "terms": "https://www.cabq.gov/about/legal",
    "key": None,
    "headers": {},
    "restricted": "The City of Albuquerque's website terms (cabq.gov/about/legal) give 'a limited license to display "
                  "... images ... for non-commercial, personal, or educational purposes only, provided that ... you "
                  "do not modify any content; you include ... the associated copyright notice ... No other use is "
                  "permitted without the express written permission of the City of Albuquerque.' The list is the "
                  "City's (dmdmaps.cabq.gov); the pictures are served by ABQRoads, whose own disclaimer (a dialog on "
                  "the map, as on NMRoads) is information-only.",
    "notes": "Undocumented: the City's public ArcGIS layer that ABQRoads' camera list queries (where enabled = 'Yes' "
             "and public_name is not null; 47 rows in Nov 2026, 45 with a picture name). Pictures come through "
             "CloudFront with no Cache-Control, and ABQRoads adds a timestamp to each request, hence cache_bust. In "
             "Nov 2026 all 10 pictures sampled were the City's 'Camera not Available' card (Last-Modified "
             "14 Feb 2025): the feed looks off. Attribution: City of Albuquerque, Department of Municipal "
             "Development (the layer's copyright text).",
    "cache_bust": True,
}
LIST = "https://dmdmaps.cabq.gov/serverext/rest/services/traffic/CABQ_Roads_Data/FeatureServer/2/query"
WHERE = "enabled = 'Yes' and public_name is not null"
IMAGE = "https://ss.abqroads.com/{}.jpeg"
PAGE = 1000


def _streets(image_name):
    """The street names in a picture name: "GEN_Unser _ Ladera" -> ["unser", "ladera"]."""
    return [s.strip().lower() for s in image_name.removeprefix("GEN_").split(" _ ") if s.strip()]


def cameras(get, key=None):
    rows, offset = [], 0
    while True:
        query = urlencode({"where": WHERE, "outFields": "*", "outSR": 4326, "orderByFields": "OBJECTID",
                           "resultOffset": offset, "resultRecordCount": PAGE, "f": "json"})
        data = json.loads(get(f"{LIST}?{query}"))
        if data.get("error"):
            raise OSError(f"{LIST}: {data['error']}")
        features = data.get("features") or []
        rows += features
        if not features or not data.get("exceededTransferLimit"):
            break
        offset += len(features)
    shared = Counter((f["attributes"].get("image_name") or "").strip() for f in rows)
    for feature in rows:
        a, point = feature.get("attributes") or {}, feature.get("geometry") or {}
        name, image = (a.get("public_name") or "").strip(), (a.get("image_name") or "").strip()
        if not image or point.get("x") is None or point.get("y") is None:
            continue
        if shared[image] > 1 and not any(street in name.lower() for street in _streets(image)):
            continue  # (a picture another record names better)
        yield {
            "id": str(a["OBJECTID"]),
            "name": re.sub(r"\s+", " ", name),
            "lat": point["y"],
            "lon": point["x"],
            "image": IMAGE.format(quote(image)),
            "city": "Albuquerque",
            "county": "Bernalillo",
            "extra": {"image_name": image, "intersection_id": a.get("intersection_id"),
                      "model": a.get("camera_type"), "signal_type": a.get("signal_type"),
                      "owner": a.get("infrastructure_owner")},
        }
