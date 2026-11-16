"""Idaho: the cameras on Idaho 511 (511.idaho.gov, Arcadis IBI's 511 platform): ITD's highway cameras and road-weather
(RWIS) cameras, and the Boise-area intersection cameras of the Ada County Highway District (ACHD). A site can have
several views (an RWIS mast's three or four directions); each view is a camera, known by its picture's id.

Idaho 511 also shows its neighbours' cameras near the border (UDOT, WYDOT, MDT, ODOT, WSDOT, NDOT, DriveBC, and a few
Nevada ones it added itself) and one private airstrip camera; those are left out here, since they come from their own
states' sources. The list is the one the site's own camera list page loads (/List/GetData/Cameras, paged 100 at a
time); the documented API (/api/v2/get/cameras) needs a key from a sign-up. Stills only.

The list's own county field is a default ("Nez Perce" on 308 of 457 sites, Boise's included) and its city field is
empty, so county and city come instead from ITD's own boundary layers (gisp.itd.idaho.gov, PoliticalBoundaries:
County Boundary and City Area), by where each camera is. The list's direction is the way the road's traffic goes
("I-90E ramp" is Eastbound), so it is given as approach, as the other IBI modules do."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "ITD (Idaho 511)",
    "state": "ID",
    "covers": "Idaho's highways and road-weather stations (ITD) statewide, and Boise-area intersections (ACHD)",
    "site": "https://511.idaho.gov/",
    "terms": "https://511.idaho.gov/about/privacy#disclaimer",
    "key": None,
    "headers": {},
    "restricted": "Idaho 511's robots.txt asks automated clients to keep off this list, in both spellings of its path "
                  "(\"disallow: /list/getdata/\" and \"disallow: /list/GetData/\"). ITD offers apps a keyed developer "
                  "API instead (https://511.idaho.gov/developers/doc).",
    "notes": "Undocumented list the site's camera list page loads; the documented API needs a key from an account "
             "(https://511.idaho.gov/developers/doc, 10 calls a minute). Stills: ACHD's are JPEG and refresh every "
             "15 s; ITD's highway cameras are large PNGs (800x486 to 1920x1166, 0.5-2.6 MB) and the RWIS views JPEG, "
             "both every 5 minutes (the list's own refresh rates). Neighbouring states' cameras on the map are left "
             "out. County and city come from ITD's public boundary layers (the list's own county field is a "
             "default). The site has no terms page; its privacy page carries a disclaimer (accuracy only, no use "
             "restriction). Its robots.txt asks automated clients to leave this path alone, and unlike the other IBI sites "
             "it names both spellings, so it's off until a user turns it on (restricted), and never shipped. The "
             "documented route is the keyed developer API (https://511.idaho.gov/developers/doc).",
}
BASE = "https://511.idaho.gov"
PAGE = 100
OTHERS = {"UDOT", "WYDOT", "MTD", "ODOT", "WSDOT", "NDot", "DriveBC", "Private"}  # other states' and private cameras
AGENCY = {"ACHD": "Ada County Highway District", "RWIS": "ITD (road-weather station)", "ITDNET": "ITD",
          "USER": "ITD", "Idaho511": "ITD"}
BOUNDARIES = "https://gisp.itd.idaho.gov/server/rest/services/GDWarehouse/PoliticalBoundaries/FeatureServer"


def _sites(get):
    start, seen = 0, set()
    while True:
        query = {"columns": [{"name": "id", "s": True}], "order": [{"column": 0, "dir": "asc"}],
                 "start": start, "length": PAGE, "search": {"value": ""}}
        data = json.loads(get(f"{BASE}/List/GetData/Cameras?query={quote(json.dumps(query))}&lang=en"))
        rows = data.get("data") or []
        for row in rows:
            if row.get("id") not in seen:
                seen.add(row.get("id"))
                yield row
        start += PAGE
        if not rows or start >= (data.get("recordsTotal") or 0):
            return


def _point(site):
    wkt = ((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or ""
    m = re.match(r"POINT \(([-\d.]+) ([-\d.]+)\)", wkt)
    return (float(m.group(2)), float(m.group(1))) if m else (None, None)


def _clean(text):
    text = (text or "").strip()
    return "" if text in ("N/A", "Unknown") else re.sub(r"\s+", " ", text)


def _areas(get, layer, field):
    """ITD's polygons in one boundary layer (layer 2 counties, 1 cities), simplified: [(name, rings, bbox)]; [] on failure."""
    try:
        data = json.loads(get(f"{BOUNDARIES}/{layer}/query?where=1%3D1&outFields={field}&outSR=4326"
                              "&geometryPrecision=4&maxAllowableOffset=0.0005&f=json"))
    except (OSError, ValueError):
        return []
    areas = []
    for feature in data.get("features") or []:
        rings = (feature.get("geometry") or {}).get("rings") or []
        points = [p for ring in rings for p in ring]
        name = ((feature.get("attributes") or {}).get(field) or "").strip()
        if points and name:
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            areas.append((name, rings, (min(xs), min(ys), max(xs), max(ys))))
    return areas


def _within(areas, lat, lon):
    for name, rings, (x0, y0, x1, y1) in areas:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        inside = False
        for ring in rings:  # even-odd rule over all rings, so holes count
            for i in range(len(ring)):
                (xa, ya), (xb, yb) = ring[i], ring[i - 1]
                if (ya > lat) != (yb > lat) and lon < (xb - xa) * (lat - ya) / (yb - ya) + xa:
                    inside = not inside
        if inside:
            return name
    return None

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    counties, cities = None, None
    for site in _sites(get):
        if site.get("source") in OTHERS or site.get("type") in OTHERS:
            continue
        lat, lon = _point(site)
        if lat is None or not 42.0 <= lat <= 49.0:  # Idaho lies between 42 and 49 degrees north
            continue
        if counties is None:
            counties, cities = _areas(get, 2, "CountyName"), _areas(get, 1, "CityName")
        county, city = _within(counties, lat, lon), _within(cities, lat, lon)
        images = site.get("images") or []
        base = _clean(site.get("location")) or _clean(site.get("roadway")) or "Camera"
        for n, image in enumerate(images, 1):
            name = _clean(image.get("description")) or base
            if len(images) > 1 and name == base:
                name = f"{base} (view {n})"
            camera = {
                "id": str(image["id"]),
                "name": name,
                "lat": lat,
                "lon": lon,
                "image": BASE + image["imageUrl"],
                "extra": {"site": site.get("id"), "agency": AGENCY.get(site.get("source"), site.get("source")),
                          "source_id": site.get("sourceId")},
            }
            if image.get("refreshRateMs"):
                camera["refresh"] = image["refreshRateMs"] // 1000
            if image.get("disabled") or image.get("blocked"):
                camera["online"] = False
            road = _clean(site.get("roadway"))
            if road and road != "Local":
                camera["road"] = road
            if _clean(site.get("direction")):
                camera["approach"] = site["direction"]
            if county:
                camera["county"] = county
            if city:
                camera["city"] = city
            yield camera
