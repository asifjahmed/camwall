"""Illinois: the City of Chicago's own intersection cameras (CDOT), from the camera list its Chicago Traffic Tracker map
loads (no key). They are CDOT's Miovision signal cameras, one fisheye picture per intersection, known by CDOT's camera
number."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "Chicago DOT (Chicago Traffic Tracker)",
    "state": "IL",
    "covers": "City of Chicago: signalized intersections on arterial streets, citywide",
    "site": "https://chicagotraffictracker.com/",
    "terms": "https://www.chicago.gov/city/en/general/disclaimer.html",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: https://chicagotraffictracker.com/rest/cctvCameras, the list the tracker's Cameras layer "
             "loads (the same vendor platform as Lake County PASSAGE). Pictures are at /snapshots/<snapshotFilename>: "
             "2992x2992 fisheye JPEGs (about 0.6-1 MB) with CDOT's caption and capture time burned in, replaced about "
             "every 10-15 minutes and served 'Cache-Control: max-age=5'. No video (the app has a /video path, but no "
             "camera lists a stream). The list has no out-of-service flag. Four intersections appear twice with the "
             "same picture; each picture is listed once, under the lower camera number. The site's disclaimer and "
             "chicago.gov's disclaimer set no reuse limits (only 'unreasonable load' is called misuse). These are not "
             "in IDOT's Gateway (il_idot), which has only the expressways in the city.",
}
SITE = "https://chicagotraffictracker.com"
LIST = SITE + "/rest/cctvCameras"


def cameras(get, key=None):
    pictures = {}
    for cam in json.loads(get(LIST)):
        file = (cam.get("snapshotFilename") or "").strip()
        where = cam.get("startLocation") or cam.get("iconPoint") or {}
        number = str(cam.get("displayId") or cam.get("id") or "").strip()
        if not file or not number or not where.get("latitude") or not where.get("longitude"):
            continue
        have = pictures.get(file)
        if have is None or _order(number) < _order(have[0]):
            pictures[file] = (number, cam, where)
    for file, (number, cam, where) in pictures.items():
        yield {
            "id": number,
            "name": (cam.get("description") or f"Camera {number}").strip(),
            "lat": float(where["latitude"]),
            "lon": float(where["longitude"]),
            "image": f"{SITE}/snapshots/{quote(file)}",
            "city": "Chicago",
            "county": "Cook",
            "refresh": 900,
            "extra": {k: v for k, v in (("agency", cam.get("agency")),
                                         ("miovision_id", cam.get("miovisionIntersectionId"))) if v},
        }


def _order(number):
    return (0, int(number), "") if number.isdigit() else (1, 0, number)
