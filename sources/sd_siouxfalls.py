"""South Dakota: the City of Sioux Falls's traffic cameras (Public Works), published through ipcamlive.com and shown in
the city's "Traffic Camera Viewer" (an ArcGIS Experience). The list is fixed: the twelve ipcamlive players the viewer
embeds, each matched to its intersection by the viewer's own labels, at the position of that camera in the city's
traffic-camera layer (gis.siouxfalls.gov Data/Traffic/MapServer/8), or of its signal (MapServer/0) for Arrowhead &
Veterans, which the layer lacks. The viewer's interstate cameras are SDDOT's, in sd_sd511. ipcamlive gives each stream a session id, so resolve() asks for fresh URLs."""

import json

SOURCE = {
    "name": "City of Sioux Falls Public Works",
    "state": "SD",
    "covers": "Sioux Falls arterial intersections and I-29 interchanges",
    "site": "https://experience.arcgis.com/experience/43e97c2a89d6450bb50bf6b3789b7f34",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "The twelve ipcamlive players in the city's viewer (no list feed, so they are listed here; the viewer's "
             "embeds were matched to intersections by their widget labels; 5c929f4330266, once taken for a second I-90 & "
             "Cliff view, is labelled Arrowhead Pkwy & Veterans Pkwy and its picture agrees). Live snapshot.jpg (4K) "
             "and HLS whose path holds a session id (resolve()). The city's layer lists the same intersections "
             "without picture URLs. No terms of use; the viewer says Traffic Cameras are provided by the City of "
             "Sioux Falls and the South Dakota DOT.",
}
STATE = "https://g1.ipcamlive.com/player/getcamerastreamstate.php?alias="
CAMERAS = [  # alias, name, lat, lon
    ("5af34fe194546", "I-90 & Cliff Ave", 43.604224, -96.711604),
    ("5c929f4330266", "Arrowhead Pkwy & Veterans Pkwy", 43.543930, -96.652230),
    ("5af35030415ac", "10th St & Cliff Ave", 43.546551, -96.711577),
    ("5af3504c42b80", "12th St & Marion Rd", 43.544065, -96.790783),
    ("5c92b5d925dd6", "26th St & Southeastern Ave", 43.529211, -96.694576),
    ("5af350816da1c", "41st St & Louise Ave", 43.514685, -96.770785),
    ("5af3506b0fd42", "41st St & Kiwanis Ave", 43.514926, -96.761229),
    ("5c92b6c6bb1ad", "41st St & Marion Rd", 43.514846, -96.791317),
    ("5d0d2393dc662", "41st St & I-29 (looking east)", 43.514846, -96.782033),
    ("5af34fc301ac4", "57th St & Minnesota Ave", 43.500473, -96.730971),
    ("5af34ffc250ec", "57th St & Veterans Pkwy", 43.500214, -96.64953),
    ("5c9407fa4edcb", "85th St & I-29 (looking east)", 43.475195, -96.796627),
]


def _urls(get, alias):
    details = json.loads(get(STATE + alias)).get("details") or {}
    if details.get("streamavailable") != "1" or not details.get("streamid") or not details.get("address"):
        return None, None
    base = details["address"].replace("http://", "https://") + "streams/" + details["streamid"] + "/"
    return base + "snapshot.jpg", base + "stream.m3u8"


def cameras(get, key=None):
    for alias, name, lat, lon in CAMERAS:
        try:
            image, video = _urls(get, alias)
        except (OSError, ValueError):
            image = video = None
        yield {
            "id": alias,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": image,  # (None while the stream is down; resolve() asks again when the camera is opened)
            "video": video,
            "video_type": "hls",
            "direction": "East" if "looking east" in name else None,
            "city": "Sioux Falls",
            "online": bool(image),
        }


def resolve(get, camera, key=None):
    image, video = _urls(get, camera["id"])
    return {"image": image, "video": video, "video_type": "hls" if video else None}
