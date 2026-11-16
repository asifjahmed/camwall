"""North Dakota: city traffic-signal cameras whose pictures NDSU's Upper Great Plains Transportation Institute (its DOT
Support Center, dotsc.ugpti.ndsu.edu) collects for traffic analysis and publishes on its public ArcGIS server
("Traffic Analysis Images", traffic_data/traffic_analysis_images/MapServer/0). NDSU's public dashboard "NDDOT - Traffic
Cameras" shows them beside NDDOT's own cameras. Each row is one approach of a signalized intersection (the camera
watching the eastbound traffic, say), in Grand Forks, Bismarck, Minot, West Fargo, Fargo, Mandan, Dickinson and Watford
City, and at NDDOT's Fargo District signals; each is a camera here, known by the layer's LegID.

The layer is rewritten about every five minutes with a new picture per approach, at a new file name holding its time,
and the old picture is deleted, so a listed picture URL stops working within minutes: resolve() asks the layer for the
approach's current picture."""

import json
import time
from urllib.parse import quote, urlencode

SOURCE = {
    "name": "NDSU UGPTI DOT Support Center (Traffic Analysis Images)",
    "state": "ND",
    "covers": "Signalized intersections in Grand Forks, Bismarck, Minot, West Fargo, Fargo, Mandan, Dickinson and "
              "Watford City, and NDDOT Fargo District ramp signals",
    "site": "https://www.arcgis.com/apps/dashboards/e23039acd0454cfdaf8d643d111f13df",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: NDSU UGPTI's public ArcGIS layer dotsc.ugpti.ndsu.edu:6443/arcgis/rest/services/"
             "traffic_data/traffic_analysis_images/MapServer/0 (no token), used by NDSU's public web map 'Traffic "
             "Analysis Images' and dashboard 'NDDOT - Traffic Cameras'. The cameras are the cities' (and NDDOT's) "
             "signal cameras, one picture per approach; approach is the leg the source names (EB = Eastbound, LT/RT = "
             "left/right-turn lanes). JPEG stills 1280x720 (about 600 KB) with a time stamp, every 5 minutes; each "
             "picture has its own time-stamped file name and is deleted when the next is taken, so resolve() gives "
             "the current one. An approach whose latest picture is over a day old is online: False (on 2026-11-08: "
             "all of NDDOT Fargo's, last taken 30 Oct, and Mandan's, Dickinson's and Watford City's). Three of "
             "Dickinson's four approaches point at Mandan pictures (the folder is named for another agency), and "
             "such approaches are online: False too. Layer 2 "
             "(Snapshot_API_Hourly) lists an hourly archive whose files are also deleted. No terms on the layer or "
             "the items (empty licence fields); NDSU's site has a privacy page only.",
}
LAYER = "https://dotsc.ugpti.ndsu.edu:6443/arcgis/rest/services/traffic_data/traffic_analysis_images/MapServer/0/query"
FIELDS = "LegID,IntersectionID,IntersectionName,Direction,WebPath,CollectionDateTime,AgencyName"
PAGE = 1000
STALE = 24 * 3600  # (seconds: an approach whose latest picture is older than this is taken for out of service)
BOUND = {"NB": "Northbound", "SB": "Southbound", "EB": "Eastbound", "WB": "Westbound"}
LANE = {"LT": "left turn", "RT": "right turn", "ADV": "advance"}
PLACES = {  # AgencyName -> (city, county)
    "Grand Forks": ("Grand Forks", "Grand Forks"),
    "Bismarck": ("Bismarck", "Burleigh"),
    "Minot": ("Minot", "Ward"),
    "West Fargo": ("West Fargo", "Cass"),
    "Fargo": ("Fargo", "Cass"),
    "NDDOT Fargo": (None, "Cass"),
    "Mandan": ("Mandan", "Morton"),
    "Dickinson": ("Dickinson", "Stark"),
    "Watford City": ("Watford City", "McKenzie"),
}


def _query(get, where, offset=0):
    params = {"where": where, "outFields": FIELDS, "outSR": "4326", "orderByFields": "LegID", "f": "json",
              "resultOffset": offset, "resultRecordCount": PAGE}
    answer = json.loads(get(LAYER + "?" + urlencode(params)))
    if answer.get("error"):
        raise OSError(f"UGPTI's layer said {answer['error']}")
    return answer


def _picture(path):
    """The layer's WebPath ('https://dotsc.ugpti.ndsu.edu\\TrafficData_Snapshot\\...\\name.jpg') as a URL."""
    path = (path or "").strip().replace("\\", "/")
    if not path.startswith("https://") or "/" not in path[8:]:
        return None
    host, rest = path[8:].split("/", 1)
    return f"https://{host}/{quote(rest, safe='/')}"


def _approach(leg):
    leg = (leg or "").strip().upper()
    if leg[:2] not in BOUND:
        return leg or None
    lane = LANE.get(leg[2:])
    return BOUND[leg[:2]] + (f" ({lane})" if lane else "")


def cameras(get, key=None):
    now, offset, seen = time.time(), 0, set()
    while True:
        answer = _query(get, "1=1", offset)
        rows = answer.get("features") or []
        for row in rows:
            a, point = row.get("attributes") or {}, row.get("geometry") or {}
            image = _picture(a.get("WebPath"))
            if a.get("LegID") is None or point.get("x") is None or str(a["LegID"]) in seen:
                continue
            seen.add(str(a["LegID"]))
            approach = _approach(a.get("Direction"))
            agency = (a.get("AgencyName") or "").strip()
            city, county = PLACES.get(agency, (None, None))
            taken = a.get("CollectionDateTime")
            camera = {
                "id": str(a["LegID"]),
                "name": f"{(a.get('IntersectionName') or 'Intersection').strip()}" + (f" ({approach})" if approach else ""),
                "lat": float(point["y"]),
                "lon": float(point["x"]),
                "image": image,
                "approach": approach,
                "city": city,
                "county": county,
                "refresh": 300,
                "extra": {k: v for k, v in {
                    "agency": agency or None,
                    "intersection": a.get("IntersectionID"),
                    "taken": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(taken / 1000)) if taken else None,
                }.items() if v is not None},
            }
            folder = image.split("/TrafficData_Snapshot/", 1)[1].split("/", 1)[0] if "/TrafficData_Snapshot/" in (
                image or "") else ""
            if folder and folder != agency.replace(" ", ""):  # (another agency's picture: a mistake in the layer)
                camera["extra"]["folder"] = folder
                camera["online"] = False
            if not image or not taken or now - taken / 1000 > STALE:
                camera["online"] = False
            yield camera
        if not rows or not answer.get("exceededTransferLimit"):
            break
        offset += len(rows)


def resolve(get, camera, key=None):
    rows = _query(get, f"LegID={int(camera['id'])}").get("features") or []
    return {"image": _picture((rows[0].get("attributes") or {}).get("WebPath")) if rows else None}
