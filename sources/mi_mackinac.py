"""Michigan: the Mackinac Bridge Authority's bridge cameras, from its Bridge Cam page (no key). The page names each
camera ("Camera #2 from dock in St. Ignace looking south") and links its picture; it gives no coordinates, so the
adapter places each camera by hand at the spot its name gives (to within a few hundred metres)."""

import html
import re

SOURCE = {
    "name": "Mackinac Bridge Authority",
    "state": "MI",
    "covers": "The Mackinac Bridge (I-75) and its approaches at St. Ignace and Mackinaw City",
    "site": "https://www.mackinacbridge.org/fares-traffic/bridge-cam/",
    "terms": "https://www.mackinacbridge.org/privacy-policy/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the img tags (id cam1..cam5) on the Bridge Cam page, whose headings name the camera. "
             "Pictures are 3840x2160 JPEGs of 0.6-4 MB, refreshed about every minute (the page itself adds ?x=123). "
             "The page has no coordinates: the adapter places cameras by their named spots (administration building, "
             "MBA dock and Bridge View Park in St. Ignace, the I-75/US-2 interchange, Mackinaw City), so positions "
             "are approximate. Not on Mi Drive. Only a privacy policy, no terms.",
}
PAGE = "https://www.mackinacbridge.org/fares-traffic/bridge-cam/"
PLACES = [  # (words in the camera's heading, lat, lon, which way it looks)
    ("administration", 45.8434, -84.7268, "S"),
    ("dock", 45.8421, -84.7238, "S"),
    ("bridge view park", 45.8455, -84.7365, "S"),
    ("i-75/us-2", 45.8597, -84.7287, "S"),
    ("mackinaw city", 45.7843, -84.7275, "N"),
]


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", "replace")
    for heading, number in re.findall(r"<h3>(?:<strong[^>]*>)?\s*(Camera #(\d)[^<]*)", page):
        img = re.search(rf'<img[^>]*id="cam{number}"[^>]*>', page)
        img = img and re.search(r'src="([^"]+)"', img.group(0))
        if not img:
            continue
        name = html.unescape(heading).strip()
        place = next((p for p in PLACES if p[0] in name.lower()), None)
        if not place:
            continue
        image = html.unescape(img.group(1)).split("?")[0]
        view = re.sub(r"^Camera #\d\s*", "", name)  # (outside the f-string: Python 3.11 allows no backslash there)
        yield {
            "id": f"cam{number}",
            "name": f"Mackinac Bridge: {view}",
            "lat": place[1],
            "lon": place[2],
            "image": image,
            "direction": place[3],
            "road": "I-75",
            "refresh": 60,
        }
