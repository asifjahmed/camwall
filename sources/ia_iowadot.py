"""Iowa: Iowa DOT's cameras, from its open-data "Traffic Cameras" layer (ArcGIS, CC BY 4.0, no key), the same cameras
511ia.org shows. A camera site can have several views (an RWIS tower's four or five, a rest area's entry and exit), and
each view is a camera here, known by its picture's path. Traffic cameras have HLS video too; RWIS, rest-area and
wrong-way-driving cameras are stills only.

RWIS road-weather views take their pictures from a second open-data layer, RWIS_Camera_Info_View, which lists each
view's last ten pictures (timestamped files on cloud.iowadot.gov): the fixed RWIS stills the traffic layer gives
(atmsqf.iowadot.gov/snapshots/public/RWIS/...) answer empty or 404 for most views. A timestamped picture doesn't
expire, but a newer one comes every ~15 minutes, so resolve() asks the layer for the view's newest."""

import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse

SOURCE = {
    "name": "Iowa DOT",
    "state": "IA",
    "covers": "Iowa's interstates and highways: Des Moines, Cedar Rapids, Council Bluffs/Omaha, Quad Cities, "
              "Waterloo, Dubuque, Iowa City, Sioux City and Ames metros, I-80, RWIS road-weather sites, rest areas "
              "and truck parking, wrong-way-driving and work-zone cameras",
    "site": "https://511ia.org/",
    "terms": "https://iowadot.gov/policies_and_statements/terms-of-use#gis",
    "key": None,
    "headers": {},
    "restricted": None,
    "credit": "Iowa DOT (CC BY 4.0)",
    "notes": "Documented: Iowa DOT's open-data layer Traffic_Cameras_View "
             "(https://www.arcgis.com/home/item.html?id=c4063f200a7b4da5826e2ac86c677cf5), licensed CC BY 4.0, so "
             "credit Iowa DOT. The layer is rebuilt about once a day with each view's last picture time; a view more "
             "than 2 hours behind the newest is marked online: False (its picture is usually gone, a 404). Stills on "
             "atmsqf.iowadot.gov change about every 3 minutes. Video is HLS from video2-4.iowadot.gov:8888, not "
             "signed. The portable work-zone (IWZ) and wrong-way-driving (WWD) cameras' streams mostly fail (404 or "
             "empty) while their stills are fresh, so their stream URLs are in extra['video'] rather than video. "
             "RWIS views' pictures come from Iowa DOT's RWIS_Camera_Info_View layer (timestamped JPEGs on "
             "cloud.iowadot.gov, a new one about every 15 minutes; resolve() gets the newest), because the fixed "
             "RWIS stills on atmsqf answered 0 bytes or 404 for most views in November 2026 (kept in "
             "extra['atms_image']); a view whose newest picture there is over 2 hours old, or that the RWIS layer "
             "doesn't list (51 views in November 2026: six whole sites and single views at nine others, whose fixed "
             "stills 404), is online: False.",
}
LAYER = "https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/Traffic_Cameras_View/FeatureServer/0/query"
RWIS = "https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/RWIS_Camera_Info_View/FeatureServer/0/query"
PAGE = 1000
FLAKY = {"IWZ", "WWD"}  # portable work-zone and wrong-way-driving cameras
STALE = timedelta(hours=2)


def _when(a):
    try:
        local = datetime.strptime(f"{a['UpdateDate']} {int(a['UpdateTime']):06d}", "%Y%m%d %H%M%S")
    except (KeyError, TypeError, ValueError):
        return None
    return local - timedelta(minutes=(a.get("UTCoffset") or 0) * 60 // 100)


def _query(get, layer, where, fields, order):
    rows, offset = [], 0
    while True:
        page = json.loads(get(f"{layer}?where={quote(where)}&outFields={fields}&outSR=4326&orderByFields={order}"
                              f"&resultOffset={offset}&resultRecordCount={PAGE}&f=json"))
        rows += [f["attributes"] for f in page.get("features") or []]
        if not page.get("exceededTransferLimit") or not page.get("features"):
            return rows
        offset += PAGE


def _rwis_id(rpuid, position):
    """The id the traffic layer's fixed still gives an RWIS view: RPUID "07", position "2" -> .../rwis_7-02.jpg."""
    return f"snapshots/public/rwis/rwis_{int(rpuid)}-{int(position):02d}.jpg"


def _rwis_pictures(get, where="1=1"):
    """RWIS views' newest pictures: {id: (url, when (ms since 1970), "RPUID/position")}."""
    out = {}
    for a in _query(get, RWIS, where, "RPUID,CAMERA_POSITION,IMAGE_URL_SECURE,IMAGE_DATE", "OBJECTID"):
        url, rpuid, position = (a.get("IMAGE_URL_SECURE") or "").strip(), a.get("RPUID"), a.get("CAMERA_POSITION")
        if not re.fullmatch(r"\d+", rpuid or "") or not re.fullmatch(r"\d+", position or ""):
            continue
        if url.startswith("https://") and "not_available" not in url.lower() and a.get("IMAGE_DATE"):
            out[_rwis_id(rpuid, position)] = (url, a["IMAGE_DATE"], f"{rpuid}/{position}")
    return out


def cameras(get, key=None):
    rows = _query(get, LAYER, "1=1", "*", "FID")
    try:
        rwis = _rwis_pictures(get)
    except (OSError, ValueError):  # (the RWIS layer failing leaves those views with their fixed stills)
        rwis = {}
    newest = max((w for w in map(_when, rows) if w), default=None)
    rwis_newest = max((when for _, when, _ in rwis.values()), default=None)
    seen = set()
    for a in rows:
        image = (a.get("ImageURL") or "").strip()
        video = (a.get("VideoURL") or "").strip() or None
        flaky = video if a.get("FUNCTION") in FLAKY else None  # their streams are mostly down; see notes
        video = None if flaky else video
        if not image and not video:
            continue
        unavailable = "cameraunavailable" in image
        when = _when(a)
        stale = bool(newest and when and newest - when > STALE)
        site = (a.get("Desc_") or "").strip()
        view = (a.get("ImageName") or "").strip()
        name = site if not view or view == site else f"{site} ({view.split(': ', 1)[-1]})"
        cam_id = urlparse(image).path.lstrip("/").lower() if image and not unavailable else f"device/{a['device_id']}"
        if cam_id in seen:  # the same picture listed twice (its path's case differs)
            continue
        seen.add(cam_id)
        extra = {k: v for k, v in (("type", a.get("Type")), ("function", a.get("FUNCTION")),
                                   ("region", a.get("REGION")), ("device", a.get("device_id")),
                                   ("video", flaky)) if v}
        picture, refresh = (image if image and not unavailable else None), 600 if a.get("Type") == "RWIS" else 180
        if cam_id in rwis:  # (an RWIS view: its picture from the RWIS layer; see the module's docstring)
            picture, when_ms, extra["rwis"] = rwis[cam_id]
            extra["atms_image"] = image
            stale, refresh = rwis_newest - when_ms > STALE.total_seconds() * 1000, 900
        elif rwis and a.get("Type") == "RWIS":  # (an RWIS view the RWIS layer doesn't list: its fixed still 404s)
            stale = True
        yield {
            "id": cam_id,
            "name": name or "Camera",
            "lat": a.get("latitude"),
            "lon": a.get("longitude"),
            "image": picture,
            "video": video,
            "video_type": "hls" if video else None,
            "road": a.get("Route") or None,
            "refresh": refresh,
            "online": not (unavailable or stale),
            "extra": extra,
        }


def resolve(get, camera, key=None):
    """An RWIS view's newest picture (timestamped, so the listed one goes stale); other cameras' URLs don't change."""
    rpuid, _, position = ((camera.get("extra") or {}).get("rwis") or "").partition("/")
    if not re.fullmatch(r"\d+", rpuid) or not re.fullmatch(r"\d+", position):
        return {}
    hit = _rwis_pictures(get, f"RPUID='{rpuid}' AND CAMERA_POSITION='{position}'").get(_rwis_id(rpuid, position))
    return {"image": hit[0]} if hit else {}
