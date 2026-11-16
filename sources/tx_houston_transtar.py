"""Texas: Houston TranStar's cameras, from the list its ESRI traffic map loads (no key). TranStar is the Houston region's
traffic center (TxDOT, Harris County, the City of Houston, METRO): freeway, toll road and city street cameras, the
Galveston and Bolivar ferries, and TxDOT's regional and construction cameras out to Beaumont and Columbus. Stills
only. TranStar's cameras are known by number ("1002"); the regional ones have no number and are known by the name in
their picture's path."""

import json
import re

SOURCE = {
    "name": "Houston TranStar",
    "state": "TX",
    "covers": "Houston region freeways, toll roads, city and county streets and ferries, with TxDOT regional cameras",
    "site": "https://traffic.houstontranstar.org/cctv/transtar/",
    "terms": "https://traffic.houstontranstar.org/disclaimer.aspx",
    "key": None,
    "headers": {},
    "restricted": "\"Except as otherwise expressly authorized in this site, no copying, reproduction, or distribution of "
                  "the information contained in this site is permitted without the prior written permission of the "
                  "Texas Department of Transportation. ... External framing or linking to specific images or graphics "
                  "is prohibited without the express written consent of TxDOT.\"",
    "notes": "Undocumented: the cctvSnapshots_json.js list the ESRI map (layers_ve.aspx) loads; TranStar's documented "
             "JSON feeds (api_doc.aspx) have no cameras and need permission. JPEG stills, changing about every "
             "2.5 minutes. direction is the source's own (North, South, ...), or none. The freeway cameras are TxDOT "
             "Houston district cameras, also on its.txdot.gov and DriveTexas.",
}
LIST = "https://traffic.houstontranstar.org/data/layers/cctvSnapshots_json.js"
SNAPSHOT = "https://www.houstontranstar.org/snapshots/cctv/{}.jpg"
REGIONAL = "https://traffic.houstontranstar.org/cctv_construction/txdot/{}_live_image.jpg"


def cameras(get, key=None):
    for cam in json.loads(get(LIST))["cameras"]:
        try:
            lat, lon = float(cam["lat"]), float(cam["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        number = (cam.get("id") or "").strip()
        regional = re.search(r"grcam\.aspx\?cam=([^&']+)", cam.get("url") or "")
        if number and number != "0":
            cam_id, image = number, SNAPSHOT.format(number)
        elif regional:
            cam_id, image = "regional/" + regional.group(1), REGIONAL.format(regional.group(1))
        else:
            continue
        direction = cam.get("dir")
        yield {
            "id": cam_id,
            "name": (cam.get("location") or cam_id).strip(),
            "lat": lat,
            "lon": lon,
            "image": image,
            "direction": direction if direction and direction != "None" else None,
            "refresh": 150,
        }
