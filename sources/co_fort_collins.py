"""Fort Collins: the City's intersection cameras (Traffic Operations), from the GeoJSON its FCTrip map loads
(www.fcgov.com/webservices/gis/data/fctrip-cameras). Each intersection has up to four pictures, one looking along
each approach (the feed's "Northbound Image" and so on); each is a camera, known by its picture's file name. The feed
lists every intersection with a Status; FCTrip shows only the ACTIVE ones, and the INACTIVE ones are marked
online: False here."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "City of Fort Collins Traffic Operations (FCTrip)",
    "state": "CO",
    "covers": "Fort Collins signalized intersections",
    "site": "https://experience.arcgis.com/experience/c2060948252b45d78fb9a5a60b62371c",
    "terms": "https://www.arcgis.com/home/item.html?id=c2060948252b45d78fb9a5a60b62371c",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented GeoJSON FCTrip's map loads. JPEG stills, refreshed every few minutes; they are served with "
             "Cache-Control max-age=31536000, so a client must add a cache-busting query (FCTrip appends ?<unix time>) "
             "to see new pictures. The direction is the approach the picture looks along, as the feed labels it "
             "(e.g. 'Northbound').",
    "cache_bust": True,
}
LIST = "https://www.fcgov.com/webservices/gis/data/fctrip-cameras"
VIEWS = ("Northbound", "Southbound", "Eastbound", "Westbound")


def cameras(get, key=None):
    for feature in json.loads(get(LIST)).get("features") or []:
        props = feature.get("properties") or {}
        lon, lat = (feature.get("geometry") or {}).get("coordinates") or (None, None)
        for view in VIEWS:
            url = (props.get(f"{view} Image") or "").strip()
            if not url:
                continue
            url = url.split("?")[0]
            camera = {
                "id": urlparse(url).path.rsplit("/", 1)[-1],
                "name": f"{props.get('Intersection') or 'Intersection'} ({view})",
                "lat": lat,
                "lon": lon,
                "image": url,
                "approach": view,
                "city": "Fort Collins",
                "county": "Larimer",
                "extra": {"intersection": props.get("ID")},
            }
            if props.get("Status") != "ACTIVE":
                camera["online"] = False
            yield camera
