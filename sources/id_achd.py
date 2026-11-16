"""Ada County, Idaho: the Ada County Highway District's (ACHD) traffic cameras in Boise, Meridian, Eagle, Garden City,
Kuna and Star, and at the I-84 interchanges ACHD watches as far as Nampa, from ACHD's own public ArcGIS layer
(gis.achdidaho.org, Traffic/Traffic_Cameras layer 26), which feeds its "Traffic Cameras" map. JPEG stills on
more.achdidaho.org. Most of these cameras are also on Idaho 511 (id_511, under other ids); about 20 are only here.

The layer has no county or city, so they come from ITD's boundary layers (gisp.itd.idaho.gov, PoliticalBoundaries),
by where each camera is: the I-84 cameras at Nampa's interchanges are in Canyon County."""

import json

SOURCE = {
    "name": "Ada County Highway District (ACHD)",
    "state": "ID",
    "covers": "Ada County (Boise metro) intersections and the I-84 / I-184 interchanges ACHD watches",
    "site": "https://experience.arcgis.com/experience/9f671143b725487cb2238e4b0f48d2cb",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Public ArcGIS MapServer (ACHD's camera map's own layer; no license text on the service or its items). "
             "JPEG stills (768x432, some 1920x1080) update every minute or so (Last-Modified current); camtimestamp is when the layer "
             "was last refreshed, the same for every row. A few cameras are listed twice; they're given once. "
             "About 210 of these are also on Idaho 511 (id_511) under 511's ids. achdidaho.org itself answered with "
             "an Akamai 'Access Denied' when this was written.",
}
LAYER = "https://gis.achdidaho.org/server/rest/services/Traffic/Traffic_Cameras/MapServer/26"
BOUNDARIES = "https://gisp.itd.idaho.gov/server/rest/services/GDWarehouse/PoliticalBoundaries/FeatureServer"


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


def cameras(get, key=None):
    seen, offset, counties, cities = set(), 0, None, None
    while True:
        data = json.loads(get(f"{LAYER}/query?where=1%3D1&outFields=*&outSR=4326&orderByFields=OBJECTID"
                              f"&resultOffset={offset}&resultRecordCount=1000&f=json"))
        features = data.get("features") or []
        for feature in features:
            a, geometry = feature.get("attributes") or {}, feature.get("geometry") or {}
            url = (a.get("hyperlink") or "").strip()
            if a.get("camID") is None or not url:
                continue
            cam_id = str(int(a["camID"]))
            if cam_id in seen:
                continue
            seen.add(cam_id)
            lat = geometry.get("y") if geometry.get("y") is not None else a.get("Latitude")
            lon = geometry.get("x") if geometry.get("x") is not None else a.get("Longitude")
            if counties is None:
                counties, cities = _areas(get, 2, "CountyName"), _areas(get, 1, "CityName")
            camera = {
                "id": cam_id,
                "name": (a.get("label") or f"Camera {cam_id}").strip(),
                "lat": lat,
                "lon": lon,
                "image": "https://" + url.split("://", 1)[1] if "://" in url else url,
                "county": (_within(counties, lat, lon) if lat is not None and lon is not None else None) or "Ada",
                "extra": {"layer_updated": a.get("camtimestamp")},
            }
            city = _within(cities, lat, lon) if lat is not None and lon is not None else None
            if city:
                camera["city"] = city
            yield camera
        offset += len(features)
        if not features or not data.get("exceededTransferLimit"):
            return
