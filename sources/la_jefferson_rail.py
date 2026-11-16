"""Louisiana: Jefferson Parish's railroad crossing cameras, which stream through ipcamlive.com. The parish lists them on
its "Rail Cameras" page (one ipcamlive player link per crossing, no positions and no list feed), so they are listed
here by their ipcamlive aliases, placed by hand at the grade crossings they're named for. They look along the road
across the tracks, so drivers can see whether a train is blocking it. Each run asks ipcamlive which of them are
streaming; a camera's still is ipcamlive's snapshot link for its alias, and resolve() looks up its current HLS
stream."""

import json

SOURCE = {
    "name": "Jefferson Parish (Rail Cameras)",
    "state": "LA",
    "covers": "Railroad grade crossings in Jefferson Parish: Harahan, River Ridge, Jefferson and Old Metairie on the east "
              "bank; Avondale and Waggaman on the west bank",
    "site": "https://www.jeffparish.gov/676/Rail-Cameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Hand-made list of the 14 ipcamlive players on the parish's Rail Cameras page (CivicPlus; "
             "www.jeffparish.gov answered with a Cloudflare block page when this was written, and the same page "
             "was read from the parish's CivicPlus host, la-jeffersonparish.civicplus.com/676/Rail-Cameras). "
             "Names are the page's. "
             "Positions are the named crossings from OpenStreetMap's level-crossing nodes; the page gives none. "
             "Central Avenue's three cameras share one crossing pair (CN McComb Subdivision and the Public Belt); the "
             "two Jefferson Hwy cameras are placed at the CN crossing by Iris Ave and Labarre Road at the Back Belt "
             "crossing north of Metairie Road, judged from their pictures. Each camera is checked against "
             "ipcamlive's getcamerastreamstate.php every run (online False when it isn't streaming). Still: "
             "https://g1.ipcamlive.com/player/snapshot.php?alias=<alias>, a redirect to the stream's current JPEG "
             "(1280x720 or 1920x1080, with the parish's logo and a timestamp). Video: resolve() asks for the current "
             "stream server and id, which change. The players aren't domain-locked and need no header. No terms "
             "page found for the cameras.",
}
PLAYER = "https://g1.ipcamlive.com/player/"
# alias, name (as the parish's page names it), lat, lon, road, city
CAMERAS = [
    ("635c0abb11126", "Avondale Garden Road Crossing", 29.91852, -90.20812, "Avondale Garden Rd", "Avondale"),
    ("6aaae63d530e6", "Central Avenue Crossing #1", 29.9706, -90.17375, "Central Ave", "Jefferson"),
    ("6aaae68b225d8", "Central Avenue Crossing #2", 29.9706, -90.17375, "Central Ave", "Jefferson"),
    ("63609c3400e64", "Central Avenue Crossing #3", 29.9706, -90.17375, "Central Ave", "Jefferson"),
    ("6529556348194", "Filmore Street Crossing", 29.97549, -90.23764, "Filmore St", "Harahan"),
    ("635c0c64414c1", "George Street Crossing", 29.91922, -90.21175, "George St", "Avondale"),
    ("6aaae498d22ac", "Jefferson Hwy Eastbound", 29.96515, -90.13663, "Jefferson Hwy", "Jefferson"),
    ("6aaae59f77ffa", "Jefferson Hwy Westbound", 29.96515, -90.13663, "Jefferson Hwy", "Jefferson"),
    ("6aaae2ff5b5bc", "Labarre Road", 29.97605, -90.15198, "Labarre Rd", "Metairie"),
    ("62b47da483e1f", "Little Farms Avenue Crossing", 29.97400, -90.21635, "Little Farms Ave", "River Ridge"),
    ("635c1059a967e", "Live Oak Boulevard Crossing", 29.93400, -90.24690, "Live Oak Blvd", "Waggaman"),
    ("62fa4c1fb9f5c", "Metairie Road Crossing", 29.98662, -90.12971, "Metairie Rd", "Metairie"),
    ("6aaacf1f0f0dc", "Taylor Street", 29.97558, -90.23905, "Taylor St", "Harahan"),
    ("635c112681056", "Willswood Lane Crossing", 29.92470, -90.22600, "Willswood Ln", "Waggaman"),
]


def _state(get, alias):
    return json.loads(get(f"{PLAYER}getcamerastreamstate.php?alias={alias}")).get("details") or {}


def cameras(get, key=None):
    for alias, name, lat, lon, road, city in CAMERAS:
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
            "city": city,
            "county": "Jefferson",
            "refresh": 10,
            "online": streaming is not False,
            "extra": {"player": f"{PLAYER}player.php?alias={alias}", "kind": "railroad crossing"},
        }


def resolve(get, camera, key=None):
    """The camera's current HLS stream (None when ipcamlive says it isn't streaming)."""
    state = _state(get, camera["id"])
    video = None
    if str(state.get("streamavailable")) == "1" and state.get("streamid") and state.get("address"):
        address = state["address"].replace("http://", "https://").rstrip("/")
        video = f"{address}/streams/{state['streamid']}/stream.m3u8"
    return {"image": camera.get("image"), "video": video, "video_type": "hls"}
