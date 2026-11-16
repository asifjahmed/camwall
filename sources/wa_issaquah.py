"""Issaquah: the City of Issaquah's traffic cameras, from the public ArcGIS layer its traffic-camera map (a Geocortex
site on products.issaquahwa.gov) draws (General_Mapservices/traffic_cameras/MapServer/0). The layer also lists WSDOT's
I-90 and SR 900 cameras, left to wa_wsdot. A camera is known by its picture's name ("Front2nd_SE")."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "City of Issaquah",
    "state": "WA",
    "covers": "City of Issaquah intersections (Front St, Gilman Blvd, Issaquah Highlands, East Lake Sammamish Pkwy)",
    "site": "https://www.issaquahwa.gov/1383/Traffic-Cams",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the public layer behind the city's GIS camera map. JPEG stills; each camera also has a "
             "fixed 'key' picture (CamStaticURL) showing which way it points, kept in extra. No terms found.",
}
LIST = ("https://apps.issaquahwa.gov/server/rest/services/General_Mapservices/traffic_cameras/MapServer/0/query"
        "?where=1%3D1&outFields=*&outSR=4326&f=json&orderByFields=OBJECTID&resultRecordCount=1000&resultOffset={offset}")
HOST = "products.issaquahwa.gov"


def cameras(get, key=None):
    seen, offset = set(), 0
    while True:
        page = json.loads(get(LIST.format(offset=offset)))
        features = page.get("features") or []
        for f in features:
            a, g = f.get("attributes") or {}, f.get("geometry") or {}
            url = (a.get("CamURL") or "").strip()
            parsed = urlparse(url)
            if parsed.hostname != HOST or g.get("x") is None:
                continue
            cid = parsed.path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if cid in seen:
                continue
            seen.add(cid)
            key_picture = (a.get("CamStaticURL") or "").strip()
            yield {
                "id": cid,
                "name": " ".join((a.get("Description") or cid).split()),
                "lat": float(g["y"]),
                "lon": float(g["x"]),
                "image": "https://" + HOST + parsed.path,
                "city": "Issaquah",
                "extra": {"key_picture": key_picture} if key_picture and "CamNA" not in key_picture else {},
            }
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
