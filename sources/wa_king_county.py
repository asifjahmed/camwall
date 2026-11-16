"""King County: King County Road Services' cameras on county roads in unincorporated King County, from the public
ArcGIS layer its My Commute map (gismaps.kingcounty.gov/MyCommute) draws. Four City of Redmond cameras on the layer are
left to wa_redmond. The county's traffic-camera page also links a few cameras the My Commute layer lacks (in November
2026 one, 16th Ave SW at SW 100th St); those are taken from the county's documented open-data layer of the same
cameras (ArcGIS Online item 488167659ce544f3a525d0eb0bb9301c, "King County and WSDOT Traffic Cameras"). A camera is
known by the county's TrafficCameraID."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "King County Road Services",
    "state": "WA",
    "covers": "County roads in unincorporated King County (Woodinville-Duvall, Novelty Hill, Petrovitsky, Snoqualmie Valley)",
    "site": "https://kingcounty.gov/en/dept/local-services/transit-transportation-roads/roads-and-bridges/traffic-cameras",
    "terms": "https://kingcounty.gov/en/shared-topics/about-king-county/website/terms-of-use",
    "key": None,
    "headers": {},
    "restricted": "King County's terms: 'You may not publish, display, distribute or commercially exploit any of the "
                  "website or app or the content therein without the prior written permission of King County.'",
    "notes": "Undocumented: the layer My Commute draws (RoadAlerts/KingCo_Traffic_Cameras/MapServer), plus any camera "
             "the county's camera page links that the layer lacks, from the documented open-data layer "
             "TRAFFICCAMERA_POINT_2029. JPEG stills from info.kingcounty.gov's ImageHandler; the map reloads them "
             "every 10 s, the cameras update about every minute. The layer has CurrentStatus (all 'Active' when "
             "checked). Camera 79 (S 277th St at West Valley Hwy, SE corner) is listed with the picture name of a "
             "dead view; the county's page shows its live one, which is used instead.",
}
LIST = ("https://gismaps.kingcounty.gov/ArcGIS/rest/services/RoadAlerts/KingCo_Traffic_Cameras/MapServer/4/query"
        "?where=1%3D1&outFields=*&outSR=4326&f=json&orderByFields=OBJECTID&resultRecordCount=1000&resultOffset={offset}")
OPEN_DATA = ("https://services.arcgis.com/Ej0PsM5Aw677QF1W/arcgis/rest/services/TRAFFICCAMERA_POINT_2029/"
             "FeatureServer/0/query?where={where}&outFields=TrafficCameraID,Location,ImageURL,CamRegion,Owner,Jurisdiction,"
             "Description,CurrentStatus&outSR=4326&f=json")
# The layer's picture name -> the one the county's page shows for that camera (the layer's answers "unavailable")
PICTURE_FIX = {"277_WValley_nwc.jpg": "277_WValley_sec.jpg"}


def _camera(a, g):
    image = (a.get("ImageURL") or "").strip().replace("http://", "https://", 1)
    if not image or "redmond.gov" in image or "kingcounty.gov" not in image or g.get("x") is None:
        return None
    name = image.rsplit("id=", 1)[-1]
    if name in PICTURE_FIX:
        image = image[: -len(name)] + PICTURE_FIX[name]
    status = (a.get("CurrentStatus") or "").strip()
    return {
        "id": str(a.get("TrafficCameraID") or a["OBJECTID"]),
        "name": " ".join((a.get("Location") or image).split()),
        "lat": float(g["y"]),
        "lon": float(g["x"]),
        "image": image,
        "county": "King",
        "refresh": 60,
        "online": status in ("", "Active"),
        "extra": {k: v for k, v in {"region": a.get("CamRegion"), "owner": a.get("Owner"),
                                    "jurisdiction": (a.get("Jurisdiction") or "").strip(),
                                    "description": (a.get("Description") or "").strip()}.items() if v},
    }


def _page_only(get, listed):
    """Cameras the county's camera page links (MyCommute/?cameraid=N) that the My Commute layer doesn't have."""
    try:
        page = get(SOURCE["site"]).decode("utf-8", errors="replace")
        linked = set(re.findall(r"MyCommute/\?(?:[^\"'>]*&(?:amp;)?)?cameraid=(\d+)", page))
        wanted = sorted(linked - listed, key=int)
        if not wanted:
            return
        found = json.loads(get(OPEN_DATA.format(where=quote(f"TrafficCameraID IN ({','.join(wanted)})"))))
    except (OSError, ValueError):
        return
    for f in found.get("features") or []:
        cam = _camera(f.get("attributes") or {}, f.get("geometry") or {})
        if cam and cam["id"] not in listed:
            listed.add(cam["id"])
            yield cam


def cameras(get, key=None):
    listed, offset = set(), 0
    while True:
        page = json.loads(get(LIST.format(offset=offset)))
        features = page.get("features") or []
        for f in features:
            cam = _camera(f.get("attributes") or {}, f.get("geometry") or {})
            if cam and cam["id"] not in listed:
                listed.add(cam["id"])
                yield cam
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
    yield from _page_only(get, listed)
