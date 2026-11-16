"""Maryland: Anne Arundel County's traffic cameras on county roads, from the county's public ArcGIS layer of its
cameras (the one its Local Traffic Camera Feeds map draws; no key). The layer also has park, landfill and recycling
cameras, which are left out. Live HLS video only (untokenized); no stills."""

import json

SOURCE = {
    "name": "Anne Arundel County DPW",
    "state": "MD",
    "covers": "Anne Arundel County roads (Odenton, Severn, Glen Burnie, Annapolis area intersections)",
    "site": "https://www.aacounty.org/public-works/highways/traffic-engineering-maintenance/traffic-cameras",
    "terms": "https://www.aacounty.org/terms-and-conditions-use",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "The layer is OpenData/Structure_OpenData/MapServer/11 on gis.aacounty.org (CCTV Cameras); the county's "
             "viewer plays https://aaco-internetdmz-sfs-01.aacounty.org/rtplive/<CAMERA_ID>/playlist.m3u8. Streams are "
             "large (2560x1920). The stream server doesn't send its intermediate certificate (RapidSSL TLS RSA CA G1): "
             "browsers and curl play the streams, but Python's urllib (and so sources.check) fails to verify them.",
}
LAYER = ("https://gis.aacounty.org/arcgis/rest/services/OpenData/Structure_OpenData/MapServer/11/query"
         "?where=CAMERA_TYP%3D%27Traffic%27&outFields=*&outSR=4326&f=json")
STREAM = "https://aaco-internetdmz-sfs-01.aacounty.org/rtplive/{}/playlist.m3u8"
POINTS = "N NE E SE S SW W NW".split()


def cameras(get, key=None):
    for feature in json.loads(get(LAYER)).get("features") or []:
        cam = feature.get("attributes") or {}
        point = feature.get("geometry") or {}
        if not cam.get("CAMERA_ID") or not point.get("x") or not point.get("y"):
            continue
        if (cam.get("ACCESS") or "EXTERNAL").upper() != "EXTERNAL":
            continue
        heading = cam.get("HEADING")
        yield {
            "id": cam["CAMERA_ID"],
            "name": cam.get("SITE_NAME") or cam.get("ADDRESS") or cam["CAMERA_ID"],
            "lat": float(point["y"]),
            "lon": float(point["x"]),
            "image": None,
            "video": STREAM.format(cam["CAMERA_ID"]),
            "video_type": "hls",
            "county": "Anne Arundel",
            "city": (cam.get("CITY") or "").title() or None,
            "direction": POINTS[round(heading / 45) % 8] if isinstance(heading, (int, float)) else None,
        }
