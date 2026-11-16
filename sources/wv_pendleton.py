"""West Virginia: Pendleton County's mountain road webcams, which stream through ipcamlive.com. The county commission's
"Traffic Webcams" page (pencowv.com) embeds one ipcamlive player per view at four mountain crossings: US 33 on
Shenandoah Mountain (the Virginia line, shared with VDOT), US 33 on North Fork Mountain west of Franklin, US 33 on
Allegheny Mountain (the Randolph County line) and WV 28 on Elk Mountain (the Pocahontas County line). There is no list
feed and no positions beyond each site's map link, so the views are listed here by their ipcamlive aliases. Each run
asks ipcamlive which are streaming; a camera's still is ipcamlive's snapshot link for its alias, and resolve() looks up
its current HLS stream."""

import json
import time

SOURCE = {
    "name": "Pendleton County Commission (Mountain Traffic Webcams)",
    "state": "WV",
    "covers": "Mountain crossings in and around Pendleton County: US 33 on Shenandoah, North Fork and Allegheny "
              "Mountains, and WV 28 on Elk Mountain",
    "site": "https://pencowv.com/traffic-webcams/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Hand-made list of the ipcamlive players on the county's Traffic Webcams page (WordPress; no list feed). "
             "Names are the page's site and view names. Positions are the page's own 'Camera Location Map' links "
             "(Bing map pins). The page's two Hunting Ground Mountain cameras (Spruce Knob views) are left out: the "
             "page says they don't show the road, and their pictures show only mountainside. The Shenandoah Mountain "
             "views are the same cameras as VDOT's quad view 'US-33 / WVA line' (va_511va id 3589), here one view "
             "each at full size. Each camera is checked against ipcamlive's getcamerastreamstate.php every run "
             "(online False when it isn't streaming). Still: https://g1.ipcamlive.com/player/snapshot.php?alias="
             "<alias>, a redirect to the stream's current JPEG (1920x1080, or 672x480 for Allegheny Mountain). "
             "Video: resolve() asks for the current stream server and id, which change. The players aren't "
             "domain-locked and need no header. No terms page found.",
}
PLAYER = "https://g1.ipcamlive.com/player/"
SITES = {
    # site: (name, lat, lon, road, county), from the page's map link for that site
    "shenandoah": ("US 33 Shenandoah Mountain (Virginia/West Virginia border)", 38.579607, -79.172407, "US-33",
                   "Pendleton"),
    "northfork": ("US 33 North Fork Mountain (west of Franklin)", 38.711606, -79.40579, "US-33", "Pendleton"),
    "allegheny": ("US 33 Allegheny Mountain (Pendleton/Randolph County line)", 38.892202, -79.468731, "US-33",
                  "Randolph"),
    "elk": ("WV 28 Elk Mountain (Pendleton/Pocahontas County line)", 38.612748, -79.625703, "WV-28", "Pendleton"),
}
# alias, site, view (as the page names it), approach (the page's "Eastbound View"/"Westbound View" labels)
CAMERAS = [
    ("5a6f39f169482", "shenandoah", "Eastbound View", "Eastbound"),
    ("5a6f3a88ca9e9", "shenandoah", "Westbound View", "Westbound"),
    ("5a6f38e055974", "northfork", "Eastbound View", "Eastbound"),
    ("5a6f396d195e3", "northfork", "Westbound View", "Westbound"),
    ("5dc2ce1c6ccc4", "allegheny", "Allegheny-East View", None),
    ("5dc41b2f2af79", "allegheny", "Allegheny-West View", None),
    ("5dc2cfb872dcb", "allegheny", "Allegheny-Rt 33 Surface", None),
    ("67c85b355e9f9", "elk", "Elk Mtn. North (Pendleton View)", None),
    ("67c85a58262f1", "elk", "Elk Mtn. South (Pocahontas View)", None),
    ("67c859ae8497d", "elk", "Elk Mtn. Road Surface", None),
]


def _state(get, alias):
    return json.loads(get(f"{PLAYER}getcamerastreamstate.php?alias={alias}")).get("details") or {}


def cameras(get, key=None):
    for alias, site, view, approach in CAMERAS:
        name, lat, lon, road, county = SITES[site]
        time.sleep(0.75)  # about one request a second to ipcamlive
        try:
            streaming = str(_state(get, alias).get("streamavailable")) == "1"
        except (OSError, ValueError):
            streaming = None
        camera = {
            "id": alias,
            "name": f"{name}: {view}",
            "lat": lat,
            "lon": lon,
            "image": f"{PLAYER}snapshot.php?alias={alias}",
            "video": None,  # resolve() finds the current stream
            "video_type": "hls",
            "road": road,
            "county": county,
            "refresh": 10,
            "online": streaming is not False,
            "extra": {"player": f"{PLAYER}player.php?alias={alias}", "site": site},
        }
        if approach:
            camera["approach"] = approach
        if site == "shenandoah":
            camera["extra"]["same_camera_as"] = "va_511va 3589 (VDOT quad view)"
        yield camera


def resolve(get, camera, key=None):
    """The camera's current HLS stream (None when ipcamlive says it isn't streaming)."""
    state = _state(get, camera["id"])
    video = None
    if str(state.get("streamavailable")) == "1" and state.get("streamid") and state.get("address"):
        address = state["address"].replace("http://", "https://").rstrip("/")
        video = f"{address}/streams/{state['streamid']}/stream.m3u8"
    return {"image": camera.get("image"), "video": video, "video_type": "hls"}
