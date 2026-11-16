"""Arizona: ADOT's cameras from AZ511 (az511.gov, Arcadis IBI's 511 platform): the Phoenix-area freeway cameras ADOT
runs (in the AZTech partnership), Tucson's and the statewide highway cameras, including those on message signs and
road-weather stations. A site can have more than one view; each view is a camera, known by its picture's id. The list
is the one the site's own camera list page loads (/List/GetData/Cameras, paged 100 at a time); the documented API
(/api/v2/get/cameras) needs a key from a sign-up. Stills only: AZ511 shows no video."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "ADOT (AZ511)",
    "state": "AZ",
    "covers": "Arizona's state highways and freeways, including metro Phoenix (AZTech) and Tucson",
    "site": "https://www.az511.gov/",
    "terms": "https://www.az511.gov/about/disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented list the site's camera list page loads; the documented API needs a key from an account "
             "(https://www.az511.gov/developers/doc, 10 calls a minute). JPEG stills (often 1920x1080) served with "
             "max-age 30. No city or MCDOT arterial cameras are published: AZTech's shared arterial cameras stay "
             "internal.",
}
BASE = "https://www.az511.gov"
PAGE = 100


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

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    for site in _sites(get):
        lat, lon = _point(site)
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
                "refresh": 30,
                "extra": {"site": site.get("id"), "type": site.get("type"), "source_id": site.get("sourceId")},
            }
            if image.get("disabled") or image.get("blocked"):
                camera["online"] = False
            if _clean(site.get("roadway")):
                camera["road"] = site["roadway"]
            if _clean(site.get("direction")):
                camera["direction"] = site["direction"]
            for field in ("county", "city"):
                if site.get(field):
                    camera[field] = site[field]
            yield camera
