"""Tennessee: the City of Clarksville Street Department's traffic cameras, which stream through ipcamlive.com. The city
lists them on its Traffic Cameras page, one sub-page per camera with an ipcamlive player; that site couldn't be reached
when this was written, so the cameras are listed here by their ipcamlive aliases, placed by hand at the
intersections they're named for. Each run asks ipcamlive which of them are streaming; a camera's still is ipcamlive's
snapshot link for its alias, and resolve() looks up its current HLS stream."""

import json

SOURCE = {
    "name": "City of Clarksville Street Department",
    "state": "TN",
    "covers": "Clarksville, Tennessee (Montgomery County): Wilma Rudolph Blvd, Peachers Mill Rd, Tiny Town Rd, Trenton "
              "Rd, 101st Airborne Division Pkwy, SR 76 and the I-24 interchanges at exits 4 and 11",
    "site": "https://www.clarksvilletn.gov/189/Traffic-Cameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Hand-made list: the city's page (clarksvilletn.gov, CivicPlus hosting) couldn't be reached when this "
             "was written, so the 14 ipcamlive aliases were taken from the city's camera players as embedded "
             "on local news sites (ClarksvilleNow, 'courtesy of the City of Clarksville'), named as the city's "
             "page names them; recheck them against clarksvilletn.gov/189 when it can be read. Positions are "
             "the named intersections, from OpenStreetMap. Each camera is checked against ipcamlive's "
             "getcamerastreamstate.php every run (online False when it isn't streaming). Still: "
             "https://g1.ipcamlive.com/player/snapshot.php?alias=<alias>, a redirect to the stream's current JPEG. "
             "Video: resolve() asks getcamerastreamstate.php for the current stream server and id, which change; the "
             "cameras aren't domain-locked and need no header. A city news release says the cameras are 'for the "
             "public to view real-time traffic and weather conditions' and are not recorded. No terms page reached.",
}
PLAYER = "https://g1.ipcamlive.com/player/"
# alias, name (as the city's Traffic Cameras page names it), lat, lon, road
CAMERAS = [
    ("61310c11c88f4", "Forrest Hills/Wilma Rudolph", 36.5764, -87.30162, "Wilma Rudolph Blvd"),
    ("61310bc852732", "Terminal/Wilma Rudolph", 36.58801, -87.29368, "Wilma Rudolph Blvd"),
    ("613a762a8184d", "Exit 4 (I-24 at Wilma Rudolph Blvd)", 36.60003, -87.28216, "I-24"),
    ("61310cec8872e", "Exit 11 (I-24 at SR 76)", 36.52565, -87.22132, "I-24"),
    ("614a400064a41", "Peachers Mill/101st", 36.58601, -87.39103, "Peachers Mill Rd"),
    ("61310c8c412d5", "Peachers Mill/Providence", 36.55136, -87.38244, "Peachers Mill Rd"),
    ("68396965be373", "Peachers Mill/Tiny Town", 36.62543, -87.37, "Peachers Mill Rd"),
    ("654bec1f29e78", "Trenton Road/Spring Creek Parkway", 36.61141, -87.32035, "Trenton Rd"),
    ("6839ce06c0b9c", "Trenton Road/Tiny Town", 36.62461, -87.31788, "Trenton Rd"),
    ("6839cd98c0e23", "Fort Campbell/Tiny Town", 36.62949, -87.43401, "Fort Campbell Blvd"),
    ("654becee17d17", "Whitfield/101st Parkway", 36.5807, -87.33654, "101st Airborne Division Pkwy"),
    ("6138e5bb22549", "Madison/Hwy 76", 36.50871, -87.27306, "SR 76"),
    ("64f77b13b6139", "Fire Station Road/Hwy 76", 36.52082, -87.23544, "SR 76"),
    ("61310b91aac5c", "2nd Street/Riverside Drive", 36.54052, -87.36541, "Riverside Dr"),
]


def _state(get, alias):
    return json.loads(get(f"{PLAYER}getcamerastreamstate.php?alias={alias}")).get("details") or {}


def cameras(get, key=None):
    for alias, name, lat, lon, road in CAMERAS:
        try:
            streaming = str(_state(get, alias).get("streamavailable")) == "1"
        except (OSError, ValueError):
            streaming = None
        yield {
            "id": alias,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": f"{PLAYER}snapshot.php?alias={alias}",
            "video": None,  # resolve() finds the current stream
            "video_type": "hls",
            "road": road,
            "city": "Clarksville",
            "county": "Montgomery",
            "refresh": 10,
            "online": streaming is not False,
            "extra": {"player": f"{PLAYER}player.php?alias={alias}"},
        }


def resolve(get, camera, key=None):
    """The camera's current HLS stream (None when ipcamlive says it isn't streaming)."""
    state = _state(get, camera["id"])
    video = None
    if str(state.get("streamavailable")) == "1" and state.get("streamid") and state.get("address"):
        address = state["address"].replace("http://", "https://").rstrip("/")
        video = f"{address}/streams/{state['streamid']}/stream.m3u8"
    return {"image": camera.get("image"), "video": video}
