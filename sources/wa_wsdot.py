"""Washington: WSDOT's highway cameras, from WSDOT's documented open-data layer "WSDOT - Travel Information Cameras"
(data.wsdot.wa.gov TravelInformation/TravelInfoCamerasWeather FeatureServer, published on ArcGIS Online by WSDOT's
Online Map Support), which is the same list its travel map loads as data.wsdot.wa.gov/travelcenter/Cameras.json (same
ids and pictures; that file is the fallback). It covers every region (Northwest/Seattle, Olympic, Southwest, South
Central, North Central, Eastern/Spokane), the road-weather (RWIS) cameras and the Washington State Ferries terminal
cameras. The list also carries ODOT's Portland cameras (from TripCheck, left to or_odot), WSDOT Aviation's airport
cameras (runways, not roads) and a few private webcams; those are left out. A camera is known by WSDOT's CameraID
(the layer's OBJECTID)."""

import json
import math
from urllib.parse import urlparse

SOURCE = {
    "name": "WSDOT",
    "state": "WA",
    "covers": "Washington's state highways and interstates, its RWIS road-weather cameras and the ferry terminals",
    "site": "https://wsdot.com/travel/real-time/map/",
    "terms": "https://wsdot.wa.gov/about/policies/travel-information-disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Documented open data: the TravelInfoCamerasWeather feature layer (WSDOT says pictures refresh about "
             "every 5 minutes; most change every 1 to 2). If the layer fails, the keyless Cameras.json the travel map "
             "loads is used. WSDOT's Traveler Information API (https://wsdot.wa.gov/traffic/api/, HighwayCameras) "
             "has the same cameras with more fields but needs a free access code. JPEG stills; no video.",
}
LAYER = ("https://data.wsdot.wa.gov/arcgis/rest/services/TravelInformation/TravelInfoCamerasWeather/FeatureServer/0/"
         "query?where=1%3D1&outFields=OBJECTID,CameraTitle,ImageURL,CompassDirection&outSR=4326&orderByFields=OBJECTID"
         "&f=json&resultRecordCount=1000&resultOffset={offset}")
LIST = "https://data.wsdot.wa.gov/travelcenter/Cameras.json"
SKIP_PATHS = ("/airports/",)  # WSDOT Aviation's runway cameras
KEEP_HOSTS = {"images.wsdot.wa.gov", "www.seattle.gov", "home.lewiscounty.com"}  # agencies' own pictures
WAYS = {"N": "N", "S": "S", "E": "E", "W": "W"}


def _lonlat(x, y):
    lon = math.degrees(x / 6378137.0)
    lat = math.degrees(2 * math.atan(math.exp(y / 6378137.0)) - math.pi / 2)
    return round(lon, 6), round(lat, 6)


def _from_layer(get):
    """(CameraID, attributes, lon, lat) from the open-data layer, a page at a time."""
    rows, offset = [], 0
    while True:
        page = json.loads(get(LAYER.format(offset=offset)))
        if "error" in page:
            raise ValueError(page["error"])
        features = page.get("features") or []
        for f in features:
            a, g = f.get("attributes") or {}, f.get("geometry") or {}
            if g.get("x") is not None and g.get("y") is not None:
                rows.append((a.get("OBJECTID"), a, round(float(g["x"]), 6), round(float(g["y"]), 6)))
        if not page.get("exceededTransferLimit") or not features:
            return rows
        offset += len(features)


def _from_file(get):
    """(CameraID, attributes, lon, lat) from the travel map's Cameras.json (Web Mercator)."""
    body = get(LIST)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:  # the file is Windows-1252
        text = body.decode("cp1252", errors="replace")
    rows = []
    for f in json.loads(text)["features"]:
        a, g = f.get("attributes") or {}, f.get("geometry") or {}
        if g.get("x") is not None and g.get("y") is not None:
            rows.append((a.get("CameraID"), a, *_lonlat(g["x"], g["y"])))
    return rows


def cameras(get, key=None):
    try:
        rows = _from_layer(get)
    except (OSError, ValueError, KeyError):
        rows = []
    if not rows:
        rows = _from_file(get)
    seen = set()
    for cid, a, lon, lat in rows:
        url = (a.get("ImageURL") or "").strip()
        parsed = urlparse(url)
        if cid is None or parsed.hostname not in KEEP_HOSTS or any(p in parsed.path for p in SKIP_PATHS):
            continue
        if str(cid) in seen:
            continue
        seen.add(str(cid))
        title = (a.get("CameraTitle") or "").replace("\xa0", " ").strip()
        way = (a.get("CompassDirection") or "").strip().upper()
        region = parsed.path.strip("/").split("/")[0].lower() if parsed.hostname == "images.wsdot.wa.gov" else None
        road = title.split(" at ")[0].strip() if " at " in title and not title.startswith("WSF") else None
        extra = {k: v for k, v in {"region": region, "compass": way or None}.items() if v}
        yield {
            "id": str(cid),
            "name": title or url,
            "lat": lat,
            "lon": lon,
            "image": url,
            "road": road,
            "direction": WAYS.get(way),
            "extra": extra,
        }
