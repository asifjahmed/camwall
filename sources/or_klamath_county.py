"""Klamath County, Oregon: the county Public Works road cameras, from the small pages the county serves for each site
(www.co.klamath.or.us/publicworks/<site>/, each a heading and one or two pictures that the page reloads every minute).
They are the same cameras TripCheck shows as "Camera courtesy of Klamath County" (in or_odot), but these are the
county's own full-size pictures (1920x1080, where TripCheck shows a 328x336 crop) and carry no TripCheck terms. The
pages give no coordinates, so SITES places each one at the point TripCheck's inventory gives the same camera. A camera
is known by its picture's name ("clover20")."""

import re

SOURCE = {
    "name": "Klamath County Public Works",
    "state": "OR",
    "covers": "Klamath County roads: Dead Indian Memorial Rd at Clover Creek Rd, Sprague River Rd, Westside Rd",
    "site": "http://www.co.klamath.or.us/publicworks/clover/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the county's per-site camera pages, read as HTML (http only). Jackson County's road "
             "conditions page links the Clover Creek one. JPEG stills, 1920x1080, changing about every 2 minutes. "
             "The pages carry no terms, and the county's main site (klamathcounty.org) reset the connection when this "
             "was written, so no terms were found. All four cameras are also on TripCheck (or_odot), as "
             "'Dead Indian Memorial Rd at Clover Creek Rd' (2 views), 'Sprague River Rd at Lone Pine Rd' and "
             "'Klamath Falls - Westside Road'. A picture added to a known page is listed at that page's point.",
}
BASE = "http://www.co.klamath.or.us/publicworks/{site}/"
SITES = {  # page -> where it is (TripCheck's point for the same camera), its road, and its views' labels on TripCheck
    "clover": {"name": "Dead Indian Memorial Rd at Clover Creek Rd", "lat": 42.29946, "lon": -122.25116,
               "road": "Dead Indian Memorial Rd", "views": {"clover20": "EB", "clover123": "SB"}},
    "sprague": {"name": "Sprague River Rd at Lone Pine Rd", "lat": 42.55426, "lon": -121.61866,
                "road": "Sprague River Rd", "views": {}},
    "westside": {"name": "Westside Rd at MP 6.06", "lat": 42.5871, "lon": -122.087,
                 "road": "Westside Rd", "views": {}},
}
PICTURE = re.compile(r'(?i)<img[^>]*?\ssrc="([^"]+?\.jpe?g)"')


def cameras(get, key=None):
    for site, place in SITES.items():
        page_url = BASE.format(site=site)
        try:
            page = get(page_url).decode("windows-1252", errors="replace")
        except OSError:
            continue  # one site's page down shouldn't hide the others
        seen = set()
        for src in PICTURE.findall(page):
            image = src if src.startswith("http") else page_url + src.lstrip("./")
            cid = image.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if cid in seen:
                continue
            seen.add(cid)
            view = place["views"].get(cid)
            yield {
                "id": cid,
                "name": place["name"] + (f" ({view})" if view else ""),
                "lat": place["lat"],
                "lon": place["lon"],
                "image": image,
                "road": place["road"],
                "county": "Klamath",
                "refresh": 120,
                "extra": {k: v for k, v in {"page": page_url, "tripcheck_view": view}.items() if v},
            }
