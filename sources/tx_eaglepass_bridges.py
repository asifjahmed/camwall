"""Texas: the City of Eagle Pass's international bridge cameras (Bridge I and Bridge 2, Camino Real), published through
ipcamlive.com. The list is fixed: the six ipcamlive players the city's bridge pages embed. ipcamlive gives each
stream a session id, so the picture and video URLs change when a stream restarts; resolve() asks again."""

import json

SOURCE = {
    "name": "City of Eagle Pass International Bridges",
    "state": "TX",
    "covers": "Eagle Pass's two international bridges to Piedras Negras",
    "site": "https://www.eaglepasstx.gov/307/International-Bridge-Cameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "The six ipcamlive players on the city's bridge pages (no list feed, so they are listed here). Each has "
             "a live snapshot.jpg and an HLS stream whose path holds a session id; resolve() fetches fresh ones. "
             "Positions are the bridges' (from Wikipedia), not each camera's.",
}
STATE = "https://g1.ipcamlive.com/player/getcamerastreamstate.php?alias="
BRIDGE_1 = ("International Bridge I", 28.70556, -100.51194)
BRIDGE_2 = ("International Bridge 2 (Camino Real)", 28.69778, -100.51056)
CAMERAS = [
    ("bridge1trafficplaza", BRIDGE_1, "traffic plaza"),
    ("bridge1platform", BRIDGE_1, "platform"),
    ("67231a475ead1", BRIDGE_2, "camera 1"),
    ("639ba5d96b3f6", BRIDGE_2, "camera 2"),
    ("639ba81bb4b49", BRIDGE_2, "camera 3"),
    ("68f3f8b846277", BRIDGE_2, "camera 4"),
]


def _urls(get, alias):
    details = json.loads(get(STATE + alias)).get("details") or {}
    if details.get("streamavailable") != "1" or not details.get("streamid") or not details.get("address"):
        return None, None
    base = details["address"].replace("http://", "https://") + "streams/" + details["streamid"] + "/"
    return base + "snapshot.jpg", base + "stream.m3u8"


def cameras(get, key=None):
    for alias, (bridge, lat, lon), view in CAMERAS:
        try:
            image, video = _urls(get, alias)
        except (OSError, ValueError):
            image = video = None
        yield {
            "id": alias,
            "name": f"{bridge} {view}",
            "lat": lat,
            "lon": lon,
            "image": image or STATE + alias,
            "video": video,
            "video_type": "hls" if video else None,
            "city": "Eagle Pass",
            "county": "Maverick",
            "online": bool(image),
        }


def resolve(get, camera, key=None):
    image, video = _urls(get, camera["id"])
    return {"image": image, "video": video}
