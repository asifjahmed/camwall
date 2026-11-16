"""Illinois: the Illinois Tollway's cameras, from the TrafficCams layer of its Virtual Map (ArcGIS, no key). A camera
site has up to eight views (a tower's north and south legs), and each view is a camera here, known by its picture's
file name. The map's service is versioned by quarter (IllinoisVirtualTollway2026Q3), so the adapter reads the map's
config.json for the current service and camera layer."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "Illinois Tollway",
    "state": "IL",
    "covers": "The Illinois Tollway's I-90, I-88, I-94, I-294 and I-355 at toll plazas and interchanges around "
              "Chicago",
    "site": "https://www.illinoisvirtualtollway.com/",
    "terms": "https://www.illinoisvirtualtollway.com/about",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the Virtual Map's ArcGIS MapServer layer TrafficCams (gis.illinoisvirtualtollway.com), "
             "with pictures at services.illinoisvirtualtollway.com/cameraimages/<file>. JPEG stills, uploaded about "
             "every five minutes (most were under a minute old when checked; I-294 at Cicero North Leg was months old "
             "and both I-90 at I-294 (O'Hare) legs and Western Springs South Leg were 404s). No video. About two "
             "thirds of these views are also in IDOT's Gateway layer (il_idot, IL-ISTHA ids) under travelmidwest.com "
             "picture URLs. The About page has only a general disclaimer.",
}
SITE = "https://www.illinoisvirtualtollway.com/"
IMAGES = "https://services.illinoisvirtualtollway.com/cameraimages/"
DIRECTIONS = {"north": "N", "south": "S", "east": "E", "west": "W"}


def cameras(get, key=None):
    config = json.loads(get(SITE + "config.json"))
    layer = f"{config['services']['mapURL']}/{config['layers'].get('camerasLayerID', 17)}"
    base = (config.get("trafficCameras") or {}).get("baseURL") or IMAGES
    page = json.loads(get(f"{layer}/query?where=1%3D1&outFields=*&outSR=4326&returnGeometry=true&f=json"))
    seen = set()
    for f in page.get("features") or []:
        a, g = f.get("attributes") or {}, f.get("geometry") or {}
        lat, lon = a.get("latitude") or g.get("y"), a.get("longitude") or g.get("x")
        if lat is None or lon is None:
            continue
        site = (a.get("DisplayName") or a.get("CamDesc") or "Tollway camera").strip()
        for n in range(1, 9):
            file = (a.get(f"Ap{n}File") or "").strip()
            if not file or file in seen:
                continue
            seen.add(file)
            view = (a.get(f"Ap{n}Desc") or "").strip()
            yield {
                "id": file.removesuffix(".jpg"),
                "name": f"{site} ({view})" if view else site,
                "lat": float(lat),
                "lon": float(lon),
                "image": base + quote(file),
                "direction": DIRECTIONS.get((a.get(f"Ap{n}Dir") or "").strip().lower()),
                "road": a.get("Road") or None,
                "refresh": 300,
                "extra": {k: v for k, v in (("milepost", round(a["MP"], 1) if a.get("MP") else None),
                                             ("site", a.get("CamID"))) if v},
            }
