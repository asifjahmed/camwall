"""Florida: Bay County's Traffic Management Center cameras (Panama City area; Bay County's and FDOT's), from the map
page tmc.baycountyfl.gov, which lists them in its own script (addIcon(IconType.Camera, lat, lon, name, ...)). Each
camera's picture path is only named on its popup page (CameraImage.aspx?CameraID=N), so that page is fetched for
each camera (about 170, paced at one a second).

NOTE: the server leaves out its intermediate certificate, and the chain ends at GoDaddy's 2025 "GoDaddy TLS Root R1",
which isn't in every CA bundle; where it's missing, get (even with tls.py fetching the intermediate) and headless
Chrome refuse it. It works where that root is trusted. Plain http answers 403."""

import html
import re
import time
from urllib.parse import unquote

BASE = "https://tmc.baycountyfl.gov/"

SOURCE = {
    "name": "Bay County TMC",
    "state": "FL",
    "covers": "Panama City, Panama City Beach, Lynn Haven and the rest of Bay County: county signal cameras and FDOT "
              "cameras on US 98, US 231 and SR 77",
    "site": "https://tmc.baycountyfl.gov/",
    "terms": "https://tmc.baycountyfl.gov/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the map page's own script and each camera's popup page. Stills are 768x432 JPEG at "
             "/cameraimages/<n>/snap_c1.jpg (the popup reloads them every 2 s through GetPic.aspx); the popup also "
             "offers video through an ASP.NET postback, not used here. The page says: 'Video is live only, not "
             "recorded, and used soley for traffic management purposes.' UNTESTED with the checker: the site's "
             "TLS chain is incomplete and ends at a new GoDaddy root (see the module docstring); parsing was "
             "verified with an unverified fetch of a few pages only.",
}
ICON = re.compile(r'addIcon\(IconType\.Camera,\s*([-\d.]+),\s*([-\d.]+),\s*"((?:[^"\\]|\\.)*)",'
                  r'\s*"[^"]*",\s*\w+,\s*(\d+)\)')
PICTURE = re.compile(r'GetPic\.aspx\?imgurl=([^"&#]+)')


def cameras(get, key=None):
    page = get(BASE).decode("utf-8", "replace")
    seen = set()
    for lat, lon, name, cam_id in ICON.findall(page):
        if cam_id in seen:
            continue
        seen.add(cam_id)
        time.sleep(0.75)  # about one request a second
        try:
            popup = get(f"{BASE}CameraImage.aspx?CameraID={cam_id}").decode("utf-8", "replace")
        except OSError:
            continue
        picture = PICTURE.search(popup)
        if not picture:
            continue
        path = re.sub(r"^https?://tmc\.baycountyfl\.gov/", "", unquote(picture.group(1)).split("#")[0])
        yield {
            "id": cam_id,
            "name": html.unescape(name.replace('\\"', '"')).strip() or cam_id,
            "lat": float(lat),
            "lon": float(lon),
            "image": BASE + path,
            "video": None,
            "county": "Bay",
        }
