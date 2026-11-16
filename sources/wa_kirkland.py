"""Kirkland: the City of Kirkland's traffic cameras, from the public ArcGIS layer (TRN_TrafficCams_10032022) its
traffic-camera map (an ArcGIS instant app on kirklandwa.gov) draws. The layer also lists WSDOT, Bellevue and Redmond
cameras near Kirkland, which their own modules cover. A camera is known by its picture's name on its.kirklandwa.gov
("100thAve132ndStPTZ"); an intersection with a second view gets one camera per view."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "City of Kirkland",
    "state": "WA",
    "covers": "City of Kirkland intersections (Totem Lake, NE 85th St, NE 124th/132nd St, downtown)",
    "site": "https://www.kirklandwa.gov/Government/Departments/Information-Technology/Kirkland-Traffic-Cameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the public layer the map draws (services2.arcgis.com/loGMwowmR0OPlOQb). JPEG stills that "
             "update about every minute (the map says so). kirklandwa.gov itself refuses scripted requests "
             "(Akamai); the layer and the pictures don't. No terms of use were found.",
}
LIST = ("https://services2.arcgis.com/loGMwowmR0OPlOQb/arcgis/rest/services/TRN_TrafficCams_10032022/FeatureServer/0/"
        "query?where=1%3D1&outFields=*&outSR=4326&f=json&orderByFields=OBJECTID&resultRecordCount=1000"
        "&resultOffset={offset}")
HOST = "its.kirklandwa.gov"


def cameras(get, key=None):
    seen, offset = set(), 0
    while True:
        page = json.loads(get(LIST.format(offset=offset)))
        features = page.get("features") or []
        for f in features:
            a, g = f.get("attributes") or {}, f.get("geometry") or {}
            if g.get("x") is None:
                continue
            name = " ".join((a.get("LOCATION") or "").split())
            views = [("", a.get("IMAGE_"))] + [(k.title(), a.get(k)) for k in ("NORTH", "SOUTH", "EAST", "WEST")]
            for label, url in views:
                url = (url or "").strip()
                parsed = urlparse(url)
                if parsed.hostname != HOST:
                    continue
                cid = parsed.path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                yield {
                    "id": cid,
                    "name": f"{name} ({label} view)" if label else name or cid,
                    "lat": float(g["y"]),
                    "lon": float(g["x"]),
                    "image": "https://" + HOST + parsed.path,
                    "city": "Kirkland",
                    "refresh": 60,
                    "extra": {"camera": a.get("TRAFCAM_ID")} if a.get("TRAFCAM_ID") else {},
                }
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
