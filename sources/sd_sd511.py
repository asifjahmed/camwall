"""South Dakota: SDDOT's cameras on SD511 (Iteris SafeTravel), from the two GeoJSON layers its map loads (no key): the
camera sites and the road-weather (RWIS) stations, which carry most of the cameras. A site has several views
("Camera Looking South", "Road Surface View"); each view is a camera here, known by site and view
("CSDATY/1"). JPEG stills on Iteris's CDN, each URL always the latest picture."""

import json
import re

SOURCE = {
    "name": "SDDOT (SD511)",
    "state": "SD",
    "covers": "South Dakota interstates and highways, with road-weather station cameras statewide",
    "site": "https://www.sd511.org/",
    "terms": "https://www.sd.gov/cs?id=kb_article_view&sysparm_article=KB0010221",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: sd.cdn.iteris-atis.com/geojson/icons/metadata/icons.cameras.geojson and "
             "icons.rwis.geojson, the layers the map loads. JPEG stills (camera_images/<site>/<view>/latest.jpg), "
             "most updated within the hour; the update time is in extra. direction is from the view's name "
             "(\"Camera Looking South\"). Terms: SD511's Disclaimer link is the State's online disclaimer, which says "
             "\"Anyone may view, copy or distribute information found on the State's website for personal or "
             "informational use without owing an obligation to the State\" (no ban on apps or automated access).",
}
LAYERS = ["https://sd.cdn.iteris-atis.com/geojson/icons/metadata/icons.cameras.geojson",
          "https://sd.cdn.iteris-atis.com/geojson/icons/metadata/icons.rwis.geojson"]
LOOKING = re.compile(r"looking\s+(north|south|east|west|northeast|northwest|southeast|southwest)\b", re.I)


def cameras(get, key=None):
    seen = set()
    for layer in LAYERS:
        for site in json.loads(get(layer)).get("features") or []:
            props, geometry = site.get("properties") or {}, site.get("geometry") or {}
            if geometry.get("type") != "Point" or not site.get("id"):
                continue
            lon, lat = geometry["coordinates"][:2]
            for view in props.get("cameras") or []:
                image = view.get("image")
                cam_id = f"{site['id']}/{view.get('id')}"
                if not image or cam_id in seen:
                    continue
                seen.add(cam_id)
                label = (view.get("name") or "").strip()
                looking = LOOKING.search(label) or LOOKING.search(view.get("description") or "")
                place = (props.get("name") or site["id"]).strip()
                yield {
                    "id": cam_id,
                    "name": f"{place}: {label}" if label else (view.get("description") or place),
                    "lat": float(lat),
                    "lon": float(lon),
                    "image": image,
                    "road": props.get("route") or None,
                    "direction": looking.group(1).title() if looking else None,
                    "extra": {k: v for k, v in {"description": view.get("description"), "milepost": props.get("mrm"),
                                                "updated": view.get("updateTime")}.items() if v},
                }
