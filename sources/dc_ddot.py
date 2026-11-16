"""District of Columbia: DDOT's traffic cameras, as the public TrafficView map shows them. TrafficView
(www.trafficview.org) is the traveler map the University of Maryland's CATT Lab runs for MATOC, the National Capital
Region's partnership of DDOT, MDOT, VDOT, WMATA and others; DDOT's own "Live Traffic Cameras" link no longer works (its
old domain, dctrafficinfo.org, now belongs to someone else). The map's Traffic Cameras layer loads the camera list
from accessGeoData.php (a POST with a bounding box, type device_cctv), which has every camera in the box: DDOT's
(ids DDOT_CAPTOP_<DDOT camera number>) and VDOT's, MDOT SHA's (CHART) and Alexandria's near the District. Only DDOT's
are taken here; the others are in va_511va and md_chart. Each camera's still is a 320x240 JPEG at
cctv.trafficview.org/thumbnail/<id>. The map's live video is fragmented MP4 over a WebSocket (CATT Lab's EvoStream
player), neither HLS nor MJPEG, so the cameras are given as stills."""

import json
from urllib.parse import urlencode

SOURCE = {
    "name": "DDOT (TrafficView, MATOC)",
    "state": "DC",
    "covers": "District of Columbia: DDOT's intersection, bridge and freeway cameras (I-295, I-395, I-695, Suitland "
              "Parkway, South Capitol Street and the downtown arterials)",
    "site": "https://www.trafficview.org/live_traffic/#13/38.9/-77.02",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: https://www.trafficview.org/map/accessGeoData.php, the list TrafficView's own map loads "
             "when its Traffic Cameras layer is turned on (no login). TrafficView has no terms of use; its FAQ "
             "(https://www.trafficview.org/introduction/) says the data comes from state and local DOTs and that "
             "providers take some feeds offline at times. MATOC's Traveler Information page "
             "(https://matoc.org/travel-info/) presents TrafficView to drivers for its 'live camera feeds'. "
             "TrafficView lists 137 DDOT cameras, all 'on'; DDOT's own inventory (DC GIS, DDOT/TrafficOperations "
             "MapServer layer 2) has 259, 235 of them operational, so about 100 working cameras aren't shown "
             "publicly. A still is TrafficView's cached frame, renewed about every 5 minutes (the first request after "
             "that waits while a new frame is taken, a few seconds). About half the listed cameras' stills never "
             "answer (their feeds are down, though the list says 'on'; the same ones on 2026-11-03 and 2026-11-08), "
             "and the list has no other flag, so they can't be marked out of service here. "
             "The documented TrafficView API needs an account. Live video (WebSocket, not HLS) isn't given.",
}
LIST = "https://www.trafficview.org/map/accessGeoData.php"
BOX = "-77.15,38.77,-76.88,39.02"  # (west, south, east, north: the District with a margin)
THUMBNAIL = "https://cctv.trafficview.org/thumbnail/"


def cameras(get, key=None):
    form = {"box-within": "true", "box-loc": BOX, "pf": "formatted", "system": "all", "type": "device_cctv",
            "params": "hideInactive", "attempt_num": "0"}
    answer = json.loads(get(LIST, data=urlencode(form).encode(),
                            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}))
    for feature in answer.get("features") or []:
        attributes, where = feature.get("attributes") or {}, feature.get("geometry") or {}
        ident = attributes.get("id") or ""
        if not ident.startswith("DDOT_") or where.get("lat") is None or where.get("lon") is None:
            continue
        camera = {
            "id": ident,
            "name": (attributes.get("Location") or "").strip() or ident,
            "lat": float(where["lat"]),
            "lon": float(where["lon"]),
            "image": THUMBNAIL + ident,
            "city": "Washington",
            "refresh": 300,
        }
        if attributes.get("status") != "on":
            camera["online"] = False
        if ident.rsplit("_", 1)[-1].isdigit():
            camera["extra"] = {"ddot_camera": int(ident.rsplit("_", 1)[-1])}
        yield camera
