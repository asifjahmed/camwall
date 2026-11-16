"""Illinois: the Metro East (St. Louis area) cameras on stltraffic.org, the "St. Louis Metropolitan Area Traveler
Information" site that IDOT's Getting Around Illinois links to, which shows IDOT District 8's incidents and cameras
(no key). Most cameras have one view; a camera with several (northbound, southbound) gives a camera per view."""

import json
from urllib.parse import urljoin, urlparse

SOURCE = {
    "name": "St. Louis Metro East traveler information (IDOT District 8)",
    "state": "IL",
    "covers": "Illinois side of the St. Louis area: I-55/64/70, I-255, I-270 and the Mississippi River bridges "
              "(Clark, McKinley, Stan Musial, MLK, Jefferson Barracks)",
    "site": "https://stltraffic.org/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: https://stltraffic.org/geoFiles/geo.json, the GeoJSON the site's map loads (its config "
             "calls it the cameras file). Who runs the site isn't stated; it shows 'Incidents (IDOT-D8)' and is "
             "linked from IDOT's Getting Around Illinois, and its code credits university developers, so it is "
             "probably an IDOT District 8 project. JPEG stills, refreshed about every 10 minutes; no video. A camera "
             "that's down shows colour bars (a 100x75, ~2 KB JPEG); 5 of 8 sampled at 2 am did, and the list doesn't "
             "say which. 25 of its 71 cameras are also in il_idot (Travel Midwest ids IL-IDOTD4-8xx) under different "
             "picture URLs. No terms page.",
}
LIST = "https://stltraffic.org/geoFiles/geo.json"


def cameras(get, key=None):
    for f in json.loads(get(LIST)).get("features") or []:
        p, coords = f.get("properties") or {}, (f.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2 or p.get("id") is None:
            continue
        name = (p.get("description") or f"Camera {p['id']}").strip()
        views = p.get("views") or [{"label": "", "image": p.get("image")}]
        for view in views:
            image = urljoin(LIST, view.get("image") or "")
            if not urlparse(image).path.endswith((".jpg", ".jpeg", ".png")):
                continue
            label = (view.get("label") or "").strip()
            file = urlparse(image).path.rsplit("/", 1)[-1].removesuffix(".jpg")
            yield {
                "id": f"{p['id']}" if file == "snapshot" else f"{p['id']}/{file}",
                "name": f"{name} ({label})" if label and len(views) > 1 else name,
                "lat": coords[1],
                "lon": coords[0],
                "image": image,
                "approach": label or None,
                "refresh": 600,
            }
