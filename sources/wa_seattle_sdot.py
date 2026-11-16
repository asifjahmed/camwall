"""Seattle: SDOT's city-street cameras, from the keyless list its Travelers map (web.seattle.gov/Travelers) loads. Each
camera has a still picture on www.seattle.gov/trafficcams and HLS video from SDOT's Wowza server, whose address the
map also asks for (api/Map/WowsaUrl). The map's list also shows WSDOT's Seattle cameras; those are left to wa_wsdot.
A camera is known by SDOT's unit id ("CMR-0162"), the same id as SDOT's open-data layer (SDOT_Traffic_Cameras)."""

import json

SOURCE = {
    "name": "Seattle Department of Transportation (SDOT)",
    "state": "WA",
    "covers": "City of Seattle arterial streets and bridges",
    "site": "https://web.seattle.gov/Travelers/",
    "terms": "https://www.seattle.gov/digital/terms-of-use",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the list SDOT's Travelers map loads. SDOT's documented open-data layer "
             "(services.arcgis.com/ZOyb2t4B0UYuYNYH/.../SDOT_Traffic_Cameras/FeatureServer/0) has the same 395 "
             "cameras and their status but no picture URLs. Pictures are JPEG stills (served with max-age=300, they "
             "change every few minutes); video is unsigned HLS (1280x720) from a streamlock.net Wowza server.",
}
BASE = "https://web.seattle.gov/Travelers/api/Map/"
IMAGES = {"sdot": "https://www.seattle.gov/trafficcams/images/",
          "port": "https://images.wsdot.wa.gov/portofseattle/"}
WOWZA = "https://61e0c5d388c2e.streamlock.net:443/live/{stream}/playlist.m3u8"


def cameras(get, key=None):
    try:
        wowza = json.loads(get(BASE + "WowsaUrl"))
        if not (isinstance(wowza, str) and "{stream}" in wowza):
            wowza = WOWZA
    except (OSError, ValueError):
        wowza = WOWZA
    seen = set()
    for feature in json.loads(get(BASE + "Data?zoomId=18&type=2"))["Features"]:
        lat, lon = feature["PointCoordinate"]
        for cam in feature.get("Cameras") or []:
            kind, picture = cam.get("Type"), (cam.get("ImageUrl") or "").strip()
            if kind not in IMAGES or not picture or cam["Id"] in seen:
                continue
            seen.add(cam["Id"])
            video = wowza.replace("{stream}", picture.replace(".jpg", ".stream")) if kind == "sdot" else None
            yield {
                "id": cam["Id"],
                "name": (cam.get("Description") or picture).strip(),
                "lat": float(lat),
                "lon": float(lon),
                "image": IMAGES[kind] + picture,
                "video": video,
                "video_type": "hls" if video else None,
                "city": "Seattle",
                "extra": {"owner": kind},
            }
