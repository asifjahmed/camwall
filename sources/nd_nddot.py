"""North Dakota: NDDOT's cameras on its travel information map (travel.dot.nd.gov), from the camera GeoJSON the map
loads (no key). A site has three to five views (North, East, ..., Pavement); each is a camera here, known by its
picture's file name ("US2RP51Raywest.jpg"). JPEG stills on www.dot.nd.gov.

The list is the camera GeoJSON NDDOT publishes at a fixed path
(travelfiles.dot.nd.gov/geojson_nc/cameras.json), the same file its map loads."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "NDDOT (Travel Information Map)",
    "state": "ND",
    "covers": "North Dakota interstates and highways statewide",
    "site": "https://travel.dot.nd.gov/",
    "terms": "https://www.dot.nd.gov/policies-and-disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: travelfiles.dot.nd.gov/geojson_nc/cameras.json, the camera GeoJSON the map loads. The same 190 "
             "sites are NDDOT's ArcGIS layer gis.dot.nd.gov/arcgis/rest/services/external/rcrs_dynamic/MapServer/5; "
             "its 52 RWIS sites (external/rwis/MapServer/0, 228 views) are all among them. JPEG stills (50-500 KB, "
             "updated every 10-15 minutes); a few listed views answer 404 (dead). direction is the view's own label "
             "(North, East, ...; Pavement views have none). Snowplow cameras (moving, truck_images/) are left out. "
             "NDDOT's policies page has only an accuracy disclaimer, no rule on reuse.",
}
FIXED = "https://travelfiles.dot.nd.gov/geojson_nc/cameras.json"
COMPASS = {"north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"}


def _sites(get):
    sites = json.loads(get(FIXED)).get("features")
    if not sites:
        raise OSError("NDDOT's camera list is empty")
    return sites


def cameras(get, key=None):
    seen = set()
    for site in _sites(get):
        props, geometry = site.get("properties") or {}, site.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        lon, lat = geometry["coordinates"][:2]
        highways = props.get("Highways") or []
        for view in props.get("Cameras") or []:
            image = (view.get("FullPath") or view.get("LinkPath") or "").strip()
            if not image.startswith("http"):
                continue
            cam_id = urlparse(image).path.rsplit("/", 1)[-1]
            if cam_id in seen:
                continue
            seen.add(cam_id)
            label = (view.get("Direction") or "").strip()
            yield {
                "id": cam_id,
                "name": (view.get("Description") or cam_id).replace(" - NDDOT", "").strip(),
                "lat": float(lat),
                "lon": float(lon),
                "image": image,
                "road": highways[0].get("HwyDesc") if highways else None,
                "direction": label if label.lower() in COMPASS else None,
                "extra": {k: v for k, v in {"region": props.get("Region"), "view": label,
                                            "milepost": highways[0].get("MPFrom") if highways else None}.items()
                          if v not in (None, "")},
            }
