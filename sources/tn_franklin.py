"""Tennessee: the City of Franklin's traffic cameras, from the ArcGIS layer behind its public camera map (no key). The
cameras stream through ipcamlive.com: a camera's still is ipcamlive's snapshot link for its alias (a redirect to the
current picture). Their video isn't listed: it's locked to the city's own map."""

import json
import re

SOURCE = {
    "name": "City of Franklin Traffic Operations Center",
    "state": "TN",
    "covers": "Franklin, Tennessee (Williamson County): signalized arterial intersections, Cool Springs, downtown, "
              "Mallory Lane, Hillsboro Road, Columbia Avenue and the I-65 interchanges",
    "site": "https://publicmaps.franklintn.gov/trafficcameras/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Documented-ish: the city's public ArcGIS MapServer layer Maps/TrafficCameras "
             "(publicmaps.franklintn.gov), the one its camera map shows; each row's URL is an ipcamlive player link "
             "with the camera's alias. Still: https://g1.ipcamlive.com/player/snapshot.php?alias=<alias>, which "
             "redirects to the stream's current snapshot (1920x1080 JPEG, live). Video isn't listed: ipcamlive gives "
             "a stream's address only to the city's own map (the cameras are domain-locked to it). Not on TDOT "
             "SmartWay.",
}
LAYER = ("https://publicmaps.franklintn.gov/arcgis/rest/services/Maps/TrafficCameras/MapServer/0/query"
         "?where=1%3D1&outFields=*&outSR=4326&f=json")
PLAYER = "https://g1.ipcamlive.com/player/"


def cameras(get, key=None):
    seen = set()
    for f in json.loads(get(LAYER)).get("features") or []:
        a, g = f.get("attributes") or {}, f.get("geometry") or {}
        alias = re.search(r"alias=([0-9a-z]+)", f"{a.get('URL') or ''} {a.get('alias') or ''}")
        try:
            lat, lon = float(a.get("YCOORD") or g["y"]), float(a.get("XCOORD") or g["x"])
        except (KeyError, TypeError, ValueError):
            continue
        if not alias or alias.group(1) in seen:
            continue
        seen.add(alias.group(1))
        yield {
            "id": alias.group(1),
            "name": (a.get("SPECINST") or "Traffic camera").strip(),
            "lat": lat,
            "lon": lon,
            "image": f"{PLAYER}snapshot.php?alias={alias.group(1)}",
            "video": None,
            "city": "Franklin",
            "county": "Williamson",
            "refresh": 10,
            "extra": {"player": a.get("URL")},
        }

