"""Redmond: the City of Redmond's traffic cameras, from the public ArcGIS layer its traffic map (gis.redmond.gov/traffic)
draws (Traffic/Cameras/MapServer/0). The map's second layer shows other agencies' cameras (WSDOT, King County, Seattle,
Sammamish), which their own modules cover. A camera is known by Redmond's camera number (TCID)."""

import json

SOURCE = {
    "name": "City of Redmond",
    "state": "WA",
    "covers": "City of Redmond intersections (about 70)",
    "site": "https://gis.redmond.gov/traffic/",
    "terms": "https://gis.redmond.gov/traffic/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the public layer the map draws. JPEG stills that update about every minute; each shows "
             "its direction (N, S, E, W) in the upper left corner. The map's disclaimer (a dialog on the page) only "
             "disclaims accuracy. Some of these also appear on Bellevue's and King County's maps.",
}
LIST = ("https://gis.redmond.gov/arcgis/rest/services/Traffic/Cameras/MapServer/0/query?where=1%3D1&outFields=*"
        "&outSR=4326&f=json&orderByFields=OBJECTID&resultRecordCount=1000&resultOffset={offset}")


def cameras(get, key=None):
    offset = 0
    while True:
        page = json.loads(get(LIST.format(offset=offset)))
        features = page.get("features") or []
        for f in features:
            a, g = f.get("attributes") or {}, f.get("geometry") or {}
            image = (a.get("ImagePath") or "").strip().replace("http://", "https://", 1)
            if not image or a.get("d_Published") == "No" or g.get("x") is None:
                continue
            yield {
                "id": str(a.get("TCID") or a["OBJECTID"]),
                "name": " ".join((a.get("Description") or image).split()),
                "lat": float(g["y"]),
                "lon": float(g["x"]),
                "image": image,
                "city": "Redmond",
                "refresh": 60,
                "online": a.get("d_CameraStatus") != "Disabled",
            }
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
