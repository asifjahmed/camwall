"""Beaufort County, SC: the county's ITMS traffic cameras (the pictures are captioned "BCSO Traffic Management"), from
the JSON list the county's camera map loads (apps.beaufortcountysc.gov/traffic-cameras/js/getCamerasJSON.php). They
cover US 278 to Hilton Head Island, SC 170, US 21, US 17, the Bluffton and Buckwalter parkways, and Beaufort, Port Royal
and Lady's Island, with a few just over the line in Jasper and Hampton counties. The Town of Hilton Head Island's site
links to the same map. None of them are on 511SC. Each camera's picture is a JPEG on Wasabi object storage."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "Beaufort County ITMS",
    "state": "SC",
    "covers": "Beaufort County: US 278 and the Hilton Head bridges, SC 170, US 21, US 17, Bluffton and Buckwalter "
              "parkways, Beaufort, Port Royal and Lady's Island (and a few cameras in Jasper and Hampton counties)",
    "site": "https://apps.beaufortcountysc.gov/traffic-cameras/",
    "terms": "https://beaufortcountysc.gov/legal-notice.html",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the list the county's camera map loads. Pictures are 1920x1080 JPEG stills on "
             "s3.us-east-1.wasabisys.com/itms/, replaced every 5-10 s (no Cache-Control; the map adds a timestamp "
             "query and reloads every 3 s). The list's 'display' flag (1 = shown) gives online. The county's legal "
             "notice has warranty and liability disclaimers only. The older picture host itmsweb.bcgov.net no longer "
             "answers.",
}
LIST = "https://apps.beaufortcountysc.gov/traffic-cameras/js/getCamerasJSON.php"
PICTURES = "https://s3.us-east-1.wasabisys.com/itms/"


def cameras(get, key=None):
    for c in json.loads(get(LIST)).get("cameras") or []:
        if not c.get("cameraID") or not c.get("imageURL"):
            continue
        desc = (c.get("cameraDesc") or "").strip()
        camera = {
            "id": str(c["cameraID"]),
            "name": desc or c.get("cameraName") or f"Camera {c['cameraID']}",
            "lat": float(c["Lat"]),
            "lon": float(c["Lon"]),
            "image": PICTURES + quote(c["imageURL"].strip()),
            "refresh": 5,
            "extra": {k: str(v).strip() for k, v in (("label", c.get("cameraName")),
                                                     ("address", c.get("cameraAddress")),
                                                     ("keywords", c.get("meta"))) if v and str(v).strip()},
        }
        if " / " in desc:
            camera["road"] = desc.split(" / ")[0].strip()
        if str(c.get("display")) != "1":
            camera["online"] = False
        yield camera
