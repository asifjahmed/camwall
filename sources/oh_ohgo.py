"""Ohio: ODOT's cameras, from the open list OHGO's map loads (no key). A camera site can have several views (a dome
camera's four directions), and each view is a camera here, known by its picture's path ("CMH/CCTV2208_East.jpg").
The list includes the Ohio River cameras Kentucky's TRIMARC runs at Cincinnati, whose pictures come from TRIMARC; those
are in Kentucky (and in ky_kytc too), so the source spans two states. A few picture paths have spaces in them, which
are percent-encoded here (Python's HTTP client refuses a URL with a space); the ids keep the path as the list gives it."""

import json
from urllib.parse import quote, unquote, urlparse

SOURCE = {
    "name": "ODOT (OHGO)",
    "state": ["OH", "KY"],
    "covers": "Ohio's interstates and state routes, with Cincinnati (ARTIMIS), Columbus, Cleveland, Dayton and Toledo",
    "site": "https://www.ohgo.com/",
    "terms": "https://publicapi.ohgo.com/docs/terms-of-use",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Pictures update about every 5-10 s. ODOT's documented API (publicapi.ohgo.com) needs a free key; this "
             "is the keyless list its own map uses (the terms are the documented API's: a key and rate limits, no "
             "reuse restrictions). No out-of-service flag: about 3% of pictures are stale at any time. It includes "
             "171 City of Columbus and 14 Franklin County cameras (named '(City of Columbus) ...') and 39 KYTC "
             "cameras in Northern Kentucky and at Maysville (Provider KYTC), which ky_kytc also has.",
}
LIST = "https://api.ohgo.com/roadmarkers/cameras"
HOSTS = {"itscameras.dot.state.oh.us": "", "www.trimarc.org": "trimarc/"}
FACING = {"North", "South", "East", "West"}  # (a view's Direction: the way it faces, or "View", "View 2", ...)


def cameras(get, key=None):
    for site in json.loads(get(LIST)):
        views = site.get("Cameras") or []
        for view in views:
            url = urlparse(view.get("LargeURL") or "")
            if url.hostname not in HOSTS or not url.path.startswith("/images/"):
                continue
            name = site.get("Description") or site.get("Location") or "Camera"
            if len(views) > 1:
                name = f"{name} ({view.get('Direction') or 'view'})"
            camera = {
                "id": HOSTS[url.hostname] + unquote(url.path).removeprefix("/images/"),
                "name": name,
                "lat": site.get("Latitude"),
                "lon": site.get("Longitude"),
                "image": f"https://{url.hostname}{quote(url.path, safe='/%()-_.~!$&*+,;=:@')}",
                "state": "KY" if site.get("Provider") == "KYTC" else "OH",
                "refresh": 10,
            }
            if view.get("Direction") in FACING:
                camera["direction"] = view["Direction"]
            yield camera
