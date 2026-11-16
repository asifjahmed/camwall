"""Larimer County: the County Road & Bridge department's road-weather station cameras, from its "Webcams & Real-Time
Weather" page (larimer.gov/roads/real-time-weather). The page is a small app that reads two kinds of station from
apps.larimer.org:

- older RWIS stations, listed (name, id, position) in apps.larimer.org/api/roads/rwis/getfile.php?file=data.json, each
  with four pictures (five at Pinewood Reservoir, one at a few single-camera sites) at
  rwis/images/<id>-cam-<n>.jpg; each picture is a camera here;
- newer camera-and-weather stations, one picture each at rwis2/images/<key>.jpg. Their keys and positions are only in
  the page's script, so they are listed below as the script had them on 8 Nov 2026.

JPEG stills (1280x720 or 800x450 Axis pictures on the RWIS stations, 1920x1080 on the newer ones), refreshed about
every 10 minutes."""

import json

SOURCE = {
    "name": "Larimer County Road & Bridge",
    "state": "CO",
    "covers": "Larimer County roads in the foothills and plains (Stove Prairie, Red Feather Lakes, Pinewood Reservoir, "
              "Masonville, Estes Park and county-road junctions near Fort Collins and Laporte)",
    "site": "https://www.larimer.gov/roads/real-time-weather",
    "terms": "https://www.larimer.gov/bocc/legal",
    "key": None,
    "headers": {},
    "restricted": "Larimer County's legal notice: \"no part of the materials available in this website may be copied; "
                  "downloaded; stored in a retrieval system\" or otherwise reproduced or disseminated without written "
                  "consent, and \"Re-use, reproduction, or distribution for commercial purposes is prohibited.\" It also "
                  "forbids \"creating frames ... around the Larimer County pages\".",
    "notes": "Undocumented: the station list the County's page loads from apps.larimer.org, plus the newer stations "
             "named in the page's script. www.larimer.gov may answer with a Cloudflare challenge; apps.larimer.org "
             "(the list and pictures) does not. The County notes the cameras are in remote spots with limited "
             "connectivity, so some pictures go stale (Ford Hill's was a month old on 8 Nov 2026).",
}
BASE = "https://apps.larimer.org/api/roads"
HIDDEN = {"Livermore Maintenance Shop", "Carter Lake", "Central City"}  # stations the County's page leaves out
ONE_PICTURE = {"Timberline @ County Road 32", "Timberline @ County Road 392", "Prospect @ BRT"}
# The newer stations, from the County page's script (rwis2/app.js): key -> (name, lat, lon, place)
NEWER = {
    "CR9-CR82": ("CR 9 & CR 82 (Buckeye)", 40.841502, -105.019343, "Buckeye"),
    "CR21-CR54G": ("CR 21 & CR 54G", 40.627037, -105.138006, "Laporte"),
    "CR37-State-Line": ("CR 37 at the State Line", 40.995393, -105.252326, "Laporte"),
    "CR70": ("CR 70", 40.754984, -105.114995, "Fort Collins"),
    "CR-43---Estes-Park": ("CR 43, Estes Park", 40.422366, -105.470905, "Estes Park"),
    "Fish-Creek-Road---Estes-Park": ("Fish Creek Road, Estes Park", 40.357074, -105.496235, "Estes Park"),
    "Ford-Hill": ("Ford Hill", 40.62535441, -105.34365852, "Bellvue"),
}


def cameras(get, key=None):
    for station in json.loads(get(f"{BASE}/rwis/getfile.php?file=data.json")):
        name = (station.get("Name") or "").strip()
        ids = station.get("id") or {}
        sid = ids.get("0") if isinstance(ids, dict) else (ids[0] if ids else None)
        info = station.get("Info") or {}
        try:
            lat, lon = (float(v) for v in (info.get("latlon") or "").split(","))
        except ValueError:
            continue
        if not sid or name in HIDDEN:
            continue
        count = 1 if name in ONE_PICTURE else 5 if name == "Pinewood Reservoir" else 4
        for n in range(1, count + 1):
            yield {
                "id": f"{sid}-cam-{n}",
                "name": f"{name} (camera {n})",
                "lat": lat,
                "lon": lon,
                "image": f"{BASE}/rwis/images/{sid}-cam-{n}.jpg",
                "refresh": 600,
                "city": info.get("city"),
                "county": "Larimer",
                "extra": {"station": name, "elevation_ft": info.get("elevation"), "kind": "RWIS"},
            }
    for key_, (name, lat, lon, place) in NEWER.items():
        yield {
            "id": key_,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": f"{BASE}/rwis2/images/{key_}.jpg",
            "refresh": 600,
            "city": place,
            "county": "Larimer",
            "extra": {"station": key_, "kind": "camera and weather station"},
        }
