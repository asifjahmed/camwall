"""Illinois: the Gateway Traveler Information System's camera snapshots (IDOT's Travel Midwest), from Gateway's own
camera report list (cameras.json, one request per source agency) and IDOT's open-data layer "Illinois Gateway Traffic
Cameras" (ArcGIS), each of which lists some live views the other leaves out (no key). Besides IDOT's own cameras it
carries Lake County (PASSAGE), DuPage County, Kane County and Illinois Tollway cameras. Each view (a camera site can
show N, E, S and W) is a camera here, known by its Travel Midwest id and direction."""

import json
import time
from urllib.parse import parse_qs, quote, urlparse

SOURCE = {
    "name": "IDOT (Gateway / Travel Midwest)",
    "state": "IL",
    "covers": "Illinois: IDOT District 1 (Chicago expressways), downstate districts 3-9 (Peoria, Springfield, "
              "Champaign, Bloomington, Metro East...), Lake County PASSAGE, DuPage County and Kane County "
              "intersections, and some Illinois Tollway cameras",
    "site": "https://www.travelmidwest.com/",
    "terms": "https://travelmidwest.com/About/InfoReusePolicy",
    "key": None,
    "headers": {},
    "restricted": None,
    "cache_bust": True,
    "credit": "Gateway traffic information courtesy of the Illinois Department of Transportation",
    "notes": "Documented: Gateway's cameras.json (https://github.com/uic-gtis/gateway-docs, gateway-api/map-data.md; "
             "'may change at any time without notice ... cannot guarantee ... suitability for use in third-party "
             "applications'), asked once per source agency (IL-IDOTD1, IL-IDOTD4 = all downstate districts, "
             "IL-ISTHA, IL-DUPAGECOUNTY, IL-KANECOUNTY, IL-LAKECOUNTY; several prefixes in one request answer 500), "
             "plus IDOT's open-data layer TrafficCamerasTM_Public "
             "(https://gis-idot.opendata.arcgis.com/datasets/IDOT::illinois-gateway-traffic-cameras, CC BY-SA 2.0), "
             "a once-a-day copy that leaves out cameras that were down when it was made but keeps a few live views "
             "(I-57 FS cameras, UIC roof cameras) cameras.json omits. Travel Midwest's Traffic Information "
             "Access/Reuse Policy asks re-users of Gateway data to register and to credit \"Gateway traffic "
             "information courtesy of the Illinois Department of Transportation\"; IDOT 'reserves the right ... to "
             "restrict the distribution of information to third parties'; non-IDOT agencies' rules (Lake County, "
             "DuPage, Kane, the Tollway) also apply. `restricted` is left empty because IDOT publishes the same "
             "pictures under an open licence in the layer; a judgment call. JPEG stills only, refreshed about every "
             "5 minutes; a view whose site sent no picture for 30 minutes is online: False. cameras.json has a "
             "videoUrl field, empty for every camera so far. CameraDirection/direction is the way the camera faces. "
             "cache_bust is set because the Lake County pictures (lakecountypassage.com) are served with "
             "'Cache-Control: max-age=3600, immutable'. No IDOT District 2 (Rockford, Quad Cities) cameras are in "
             "Gateway.",
}
LIST = "https://travelmidwest.com/lmiga/cameras.json"
LAYER = "https://services2.arcgis.com/aIrBD8yn1TDTEXoz/arcgis/rest/services/TrafficCamerasTM_Public/FeatureServer/0/query"
PAGE = 1000
STALE = 30 * 60  # seconds without a new picture before a view counts as out of service
DIRECTIONS = {"N": "N", "E": "E", "S": "S", "W": "W", "NE": "NE", "NW": "NW", "SE": "SE", "SW": "SW"}
AGENCIES = {"IL-LAKECOUNTY": "Lake County", "IL-DUPAGECOUNTY": "DuPage County", "IL-KANECOUNTY": "Kane County",
            "IL-ISTHA": "Illinois Tollway", "IL-IDOTD1": "IDOT District 1", "IL-IDOTD4": "IDOT (downstate)"}


def cameras(get, key=None):
    layer = list(_layer(get))
    prefixes = list(AGENCIES) + sorted({"-".join(c["id"].split("-")[:2]) for c in layer} - set(AGENCIES))
    seen = set()
    for prefix in prefixes:
        try:
            report = json.loads(get(f"{LIST}?state=Illinois&idPrefix={quote(prefix)}"))
        except (OSError, ValueError):
            continue  # (the layer still has this agency's cameras)
        for camera in _report(report):
            if camera["id"] not in seen:
                seen.add(camera["id"])
                yield camera
    for camera in layer:
        if camera["id"] not in seen:
            seen.add(camera["id"])
            yield camera


def _id(raw):
    """The camera id as the layer's ImgPath query gives it (so ids stay the same whichever list a view comes from)."""
    return (parse_qs("id=" + raw).get("id") or [""])[0]


def _agency(cam):
    return next((v for k, v in AGENCIES.items() if cam.startswith(k + "-")), None)


def _report(report):
    now = time.time()
    for f in report.get("features") or []:
        p, coords = f.get("properties") or {}, (f.get("geometry") or {}).get("coordinates") or []
        raw = (p.get("id") or "").strip()
        cam = _id(raw)
        if not cam or len(coords) < 2 or coords[0] is None or coords[1] is None:
            continue
        name = (p.get("description") or cam).strip()
        updated = (p.get("lastUpdateTime") or 0) / 1000
        road, cross = (p.get("onRoad") or "").strip(), (p.get("crossRoad") or "").strip()
        mile = p.get("mileMarker")
        for view in p.get("urls") or []:
            image = (view.get("url") or "").strip()
            facing = (view.get("direction") or "NONE").strip()
            if not image:
                continue
            if image.startswith("http://") and urlparse(image).hostname.endswith("travelmidwest.com"):
                image = "https://" + image[len("http://"):]
            camera = {
                "id": f"{cam}/{facing}",
                "name": f"{name} ({facing})" if facing in DIRECTIONS else name,
                "lat": float(coords[1]),
                "lon": float(coords[0]),
                "image": image,
                "direction": DIRECTIONS.get(facing),
                "road": road if road and road.lower() != "unknown" else None,
                "county": (p.get("county") or "").strip() or None,
                "city": (p.get("city") or "").strip() or None,
                "refresh": 300,
                "online": bool(updated) and now - updated < STALE,
                "extra": {k: v for k, v in (
                    ("agency", _agency(cam)), ("district", p.get("district")),
                    ("cross_road", cross if cross and cross.lower() != "unknown" else None),
                    ("mile_marker", mile if isinstance(mile, (int, float)) and mile >= 0 else None),
                    ("bridge", True if p.get("bridge") is True else None),
                    ("page", f"https://travelmidwest.com/showCamera?id={quote(raw, safe='')}&direction={facing}"))
                    if v is not None},
            }
            if p.get("videoUrl"):
                camera["video"], camera["video_type"] = p["videoUrl"], "hls"
            yield camera


def _layer(get):
    offset = 0
    while True:
        page = json.loads(get(f"{LAYER}?where=1%3D1&outFields=*&outSR=4326&orderByFields=OBJECTID"
                              f"&resultOffset={offset}&resultRecordCount={PAGE}&f=json"))
        features = page.get("features") or []
        for f in features:
            a = f.get("attributes") or {}
            image = (a.get("SnapShot") or "").strip()
            cam = (parse_qs(urlparse(a.get("ImgPath") or "").query).get("id") or [""])[0]
            if not image or not cam or a.get("y") is None or a.get("x") is None:
                continue
            facing = a.get("CameraDirection") or "NONE"
            name = (a.get("CameraLocation") or cam).strip()
            yield {
                "id": f"{cam}/{facing}",
                "name": f"{name} ({facing})" if facing in DIRECTIONS else name,
                "lat": float(a["y"]),
                "lon": float(a["x"]),
                "image": image,
                "direction": DIRECTIONS.get(facing),
                "refresh": 300,
                "online": a.get("TooOld") != "true",
                "extra": {k: v for k, v in (("agency", _agency(cam)), ("age_minutes", a.get("AgeInMinutes")),
                                             ("page", a.get("ImgPath"))) if v},
            }
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += PAGE
