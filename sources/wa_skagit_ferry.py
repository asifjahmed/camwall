"""Skagit County: the Guemes Island Ferry's cameras, which Skagit County Public Works shows on its "Ferry Tracking
Cameras" page: the Anacortes terminal's holding lane, the Anacortes dock, and a long view of the Guemes Island landing
and its lane across the channel. Like the Washington State Ferries terminal cameras in wa_wsdot, they show the vehicle
lanes drivers wait in. The page is read for the pictures it shows; the three known views are placed at the Anacortes
terminal (500 I Ave), where the cameras are, located with the US Census Bureau's public geocoder. A camera is known by
its picture's name ("ferryline")."""

import re

SOURCE = {
    "name": "Skagit County Public Works (Guemes Island Ferry)",
    "state": "WA",
    "covers": "The Guemes Island Ferry's Anacortes terminal lane and dock, and its Guemes Island landing",
    "site": "https://www.skagitcountywa.gov/services/roads-and-transportation/ferry/ferry-tracking-cameras/",
    "terms": "https://www.skagitcountywa.gov/privacy-policy/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the county's camera page, read as HTML. JPEG stills (about 1920x1080) that change every "
             "30 s or so; the page reloads them every 30 s. The old skagitcounty.net picture links redirect to "
             "classic.skagitcountywa.gov, which is used directly. The county's privacy policy only disclaims accuracy.",
}
PAGE = SOURCE["site"]
IMAGES = "https://classic.skagitcountywa.gov/PublicWorksFerry/Images/"
VIEWS = {  # picture name -> (name, lat, lon, way the camera faces)
    "ferryline": ("Guemes Island Ferry: Anacortes terminal lane", 48.518071, -122.623557, None),
    "ferrycam": ("Guemes Island Ferry: Anacortes dock", 48.518071, -122.623557, None),
    "guemescam": ("Guemes Island Ferry: Guemes Island landing and lane (from Anacortes)", 48.518071, -122.623557, "N"),
}
PICTURE = re.compile(r'/PublicWorksFerry/Images/([A-Za-z0-9_-]+)\.jpg', re.I)


def cameras(get, key=None):
    try:
        shown = PICTURE.findall(get(PAGE).decode("utf-8", errors="replace")) or list(VIEWS)
    except OSError:
        shown = list(VIEWS)
    seen = set()
    for picture in shown:
        cid = picture.lower()
        if cid not in VIEWS or cid in seen:
            continue
        seen.add(cid)
        name, lat, lon, way = VIEWS[cid]
        yield {
            "id": cid,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": IMAGES + picture + ".jpg",
            "direction": way,
            "city": "Anacortes",
            "county": "Skagit",
            "refresh": 30,
        }
