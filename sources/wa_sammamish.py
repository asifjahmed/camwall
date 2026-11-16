"""Sammamish: the City of Sammamish's traffic cameras, from its traffic-camera page (www.sammamish.us/i-want-to/
trafficcams), which lists each camera as a heading and a picture on sammamish.azurewebsites.net. The page gives no
coordinates, so LOCATIONS places each intersection: King County GIS's public locator (gismaps.kingcounty.gov
Composite_locator) for the names on the page, which agree with the points Redmond's traffic map gives seven of them.
A camera is known by its picture's name without the page's running number ("228th_and_SE_24th")."""

import html
import re

SOURCE = {
    "name": "City of Sammamish",
    "state": "WA",
    "covers": "City of Sammamish arterials (228th Ave, Sahalee Way, NE 8th St)",
    "site": "https://www.sammamish.us/i-want-to/trafficcams/",
    "terms": "https://www.sammamish.us/i-want-to/trafficcams/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the city's camera page, read as HTML. Its terms (on the page) only disclaim accuracy. "
             "Pictures refresh every three minutes; in November 2026 the page warned of 'a server issue affecting "
             "traffic camera updates', so pictures may be stale. A camera added to the page and missing from "
             "LOCATIONS is skipped until it is placed.",
}
PAGE = "https://www.sammamish.us/i-want-to/trafficcams/"
LOCATIONS = {  # picture name -> (lat, lon), from King County's locator
    "228th_and_IPLR": (47.582623, -122.035504),
    "228th_and_SE_24th": (47.588262, -122.035472),
    "228th_and_SE_20th": (47.591758, -122.035432),
    "228th_and_SE_16th": (47.595472, -122.035421),
    "228th_and_SE_10th": (47.599178, -122.035460),
    "228th_and_SE_8th": (47.601781, -122.035510),
    "228th_and_SE_4th": (47.605494, -122.035464),
    "228th_and_E_Main": (47.609209, -122.035405),
    "228th_and_NE_4th": (47.612951, -122.035567),
    "228th_and_NE_8th": (47.616584, -122.035417),
    "228th_and_NE_12th": (47.620572, -122.035499),
    "228th_and_NE_25th": (47.631693, -122.035445),
    "Sahalee_and_NE_37th": (47.644497, -122.056584),
    "NE_8th_and_242nd": (47.616711, -122.017058),
}
CAMERA = re.compile(r'(?s)<h3>(.*?)</h3>\s*<p>\s*<img[^>]*?src="(https://sammamish\.azurewebsites\.net/[^"]+?\.jpg)"')


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", errors="replace")
    seen = set()
    for heading, image in CAMERA.findall(page):
        stem = image.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        cid = re.sub(r"^\d+_", "", stem)
        if cid not in LOCATIONS or cid in seen:
            continue
        seen.add(cid)
        lat, lon = LOCATIONS[cid]
        yield {
            "id": cid,
            "name": " ".join(html.unescape(re.sub(r"<[^>]+>", "", heading)).split()),
            "lat": lat,
            "lon": lon,
            "image": image,
            "city": "Sammamish",
            "refresh": 180,
        }
