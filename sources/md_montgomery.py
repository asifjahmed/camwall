"""Maryland: Montgomery County DOT's traffic cameras, from the camera list its traffic-camera map carries (no key).
The map also shows 95 MDOT SHA (CHART) cameras (marked extra["owner"] = "SHA"): most in and around the county, but
also Prince George's County, the Nice/Middleton bridge and SHA road-weather sites as far as Sideling Hill. md_chart has
them too, with thumbnails a few minutes old: here they have live stills. TrafficLand answers "This image is
temporarily unavailable" (a fixed 8 KB PNG) for a camera it has no picture from, and a black "NO VIDEO" frame for some.

The stills are TrafficLand's, refreshed every 2 s. Each picture URL carries a pubtoken the page hands out; they stayed
the same across page loads, but resolve() reads the page again for a fresh one in case they change."""

import json

SOURCE = {
    "name": "Montgomery County DOT",
    "state": "MD",
    "covers": "Montgomery County, Maryland: county roads and intersections, plus MDOT SHA cameras in and beyond "
              "the county",
    "site": "https://atms.montgomerycountymd.gov/jpgcap/TL/",
    "terms": "https://atms.montgomerycountymd.gov/use_of_materials.htm",
    "key": None,
    "headers": {},
    "restricted": "\"You may not, under any circumstances, reproduce, record, publish, publicly exhibit, or distribute "
                  "any media files (including, but not limited to TARS radio and Traffic camera snapshot and streaming "
                  "video files) made available for playback on the MCDOT Web site without MCDOT's express written "
                  "consent. You may not link directly to any .jpg or .gif file located on a MCDOT server\"",
    "notes": "Undocumented: the LoadCameras([...]) list in the map page. Pictures are served by TrafficLand "
             "(ie.trafficland.com, system dpwt) with a per-camera pubtoken from the page. MCDOT points its cameras "
             "where it needs them and says which way in the picture's caption (camtitling.html).",
}
PAGE = "https://atms.montgomerycountymd.gov/jpgcap/TL/"


def _cameras(get):
    page = get(PAGE).decode("utf-8", errors="replace")
    start = page.find("LoadCameras([")
    if start < 0:
        return []
    return json.JSONDecoder().raw_decode(page, start + len("LoadCameras("))[0]


def cameras(get, key=None):
    for cam in _cameras(get):
        if not cam.get("id") or not cam.get("image") or not cam.get("lat") or not cam.get("lng"):
            continue
        yield {
            "id": str(cam["id"]),
            "name": cam.get("name") or "Camera",
            "lat": float(cam["lat"]),
            "lon": float(cam["lng"]),
            "image": cam["image"],
            "county": "Montgomery" if cam.get("provider") == "Montgomery" else None,  # (SHA's reach other counties)
            "refresh": (cam.get("refresh") or 2000) / 1000,
            "extra": {"owner": cam.get("provider")},
        }


def resolve(get, camera, key=None):
    for cam in _cameras(get):
        if str(cam.get("id")) == camera["id"]:
            return {"image": cam.get("image"), "video": None}
    return {"image": camera.get("image"), "video": None}
