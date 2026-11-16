"""New Mexico: NMDOT's cameras from NMRoads (nmroads.com), including the Albuquerque metro freeway and arterial cameras
(ABQRoads, abqroads.com, shows the same NMDOT list). The list is the one NMRoads' map loads
(servicev5.nmroads.com/RealMapWAR/GetCameraInfo). Each camera has a JPEG snapshot on ss.nmroads.com, which is served
over plain HTTP only, at the camera's native size (up to 1024x576), refreshed about once a minute; the map itself
shows a 360x240 HTTPS copy (RealMapWAR/GetCameraImage), given in extra as image_https. The list names RTMP streams on
video.nmroads.com, but the site plays no video and offers no HLS. road is the numbered route a camera's title starts
with ("I-25 NB @ Lohman" -> I-25); the list has no road field. ABQRoads also lists the City of Albuquerque's own
signal cameras, from the City's GIS: those are nm_albuquerque."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "NMDOT (NMRoads)",
    "state": "NM",
    "covers": "New Mexico's interstates and highways, with the Albuquerque, Las Cruces and Santa Fe metro areas",
    "site": "https://www.nmroads.com/",
    "terms": "https://www.nmroads.com/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented list NMRoads' map loads. The disclaimer is a dialog on the map page (information only, no "
             "guarantee; no use restrictions). Snapshots are HTTP-only (ss.nmroads.com refuses HTTPS); the HTTPS "
             "360x240 copy is extra.image_https. NMRoads' public GeoJSON feed (nmroads.com/nmroads.json, CC0) is "
             "WZDx work zones only, with no cameras. A few snapshots are dead with no flag in the list (Nov 2026: "
             "pojoaque.jpg answers 404 and its HTTPS copy is empty). NMDOT's ITS inventory (ArcGIS 'Statewide CCTV "
             "View', 186) has three rest-area cameras (Anthony, Gage, Yucca) that NMRoads doesn't show.",
}
LIST = "https://servicev5.nmroads.com/RealMapWAR/GetCameraInfo"
THUMB = "https://servicev5.nmroads.com/RealMapWAR/GetCameraImage?ts=0&cameraName="
ROAD = re.compile(r"^(I|US|NM)[ -]?(\d+(?:/\d+)?)(?!\d)")  # "I-25NB @ Central", "US 64/87 @ Capulin", "NM 528 @ ..."


def cameras(get, key=None):
    for cam in json.loads(get(LIST)).get("cameraInfo") or []:
        if cam.get("mobile") or not cam.get("name"):
            continue
        thumb = THUMB + quote(cam["name"])
        camera = {
            "id": cam["name"],
            "name": cam.get("title") or cam["name"],
            "lat": cam.get("lat"),
            "lon": cam.get("lon"),
            "image": cam.get("snapshotFile") or thumb,
            "refresh": 60,
            "extra": {"image_https": thumb, "area": cam.get("grouping"), "district": cam.get("district"),
                      "type": cam.get("cameraType")},
        }
        if road := ROAD.match(cam.get("title") or ""):
            camera["road"] = {"I": "I-", "US": "US ", "NM": "NM "}[road[1]] + road[2]
        if cam.get("enabled") is False:
            camera["online"] = False
        yield camera
