"""West Virginia: WVDOT's cameras on WV511. The map's camera list (wsvc/gmap.asmx/buildCamerasJSONjs, a script that
sets camera_data) gives each camera's id, place and name; its HLS stream is named on the camera's player page
(flowplayeri.aspx?CAMID=<id>), on one of several roadsummary.com servers, so that page is fetched for each camera
(about 130, paced at one a second), and its playlist asked for once to see whether it is streaming. The cameras are
video only: the map has no still pictures."""

import html
import json
import re
import time

BASE = "https://wv511.org/"

SOURCE = {
    "name": "WVDOT (WV511)",
    "state": "WV",
    "covers": "West Virginia interstates (I-64, I-77, I-79, I-81, I-70, I-68, I-470) and some US and state routes, "
              "around Charleston, Morgantown, Wheeling, the Eastern Panhandle, Huntington and Beckley",
    "site": "https://wv511.org/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the map's camera script and each camera's player page. Video is unsigned HLS "
             "(720x480, 15 fps) on vtcN/sfsN.roadsummary.com; there are no stills (the map's static picture is "
             "commented out, and the Wowza thumbnail path answers 204). Names carry a county code in brackets "
             "([KAN] Kanawha), kept in extra and turned into the county's name. WV511 has no terms page. The "
             "Parkways Authority's I-77 Turnpike cameras are among these (its own camera site, camera.wvturnpike.com, "
             "reset the connection when this was written). The map's list matches the Camera Listing page (133 both, "
             "Nov 2026). Each camera's playlist is "
             "asked for once per run: a camera whose stream server answers 404 or empty (not streaming; 21 of 133 "
             "on 8 Nov 2026) is listed with online False.",
}
STREAM = re.compile(r"https://[a-z0-9.-]+\.roadsummary\.com/[^'\"\s]+?\.m3u8")
# The county codes the camera names carry, each checked against where its cameras stand (Census county lookup). A code
# not here is kept in extra only.
COUNTIES = {
    "BER": "Berkeley", "BOO": "Boone", "BRA": "Braxton", "CAB": "Cabell", "FAY": "Fayette", "GRA": "Grant",
    "GRE": "Greenbrier", "HAR": "Harrison", "JAC": "Jackson", "JEF": "Jefferson", "KAN": "Kanawha", "LEW": "Lewis",
    "LOG": "Logan", "MAR": "Marion", "MER": "Mercer", "MIN": "Mineral", "MON": "Monongalia", "OHI": "Ohio",
    "PRE": "Preston", "PUT": "Putnam", "RAL": "Raleigh", "TUC": "Tucker", "WEZ": "Wetzel", "WOO": "Wood",
}
BOUND = re.compile(r"\b(NB|SB|EB|WB)\b")
BOUNDS = {"NB": "Northbound", "SB": "Southbound", "EB": "Eastbound", "WB": "Westbound"}


def _player(get, cam_id):
    for attempt in range(3):
        try:
            return get(f"{BASE}flowplayeri.aspx?CAMID={cam_id}").decode("utf-8", "replace")
        except OSError:
            if attempt == 2:
                return ""
            time.sleep(3)


def _live(get, url):
    """False when the stream server says the camera isn't streaming (404, or an empty answer), None if unsure."""
    try:
        return b"#EXTM3U" in get(url)
    except OSError as e:
        return False if "HTTP 404" in str(e) else None


def cameras(get, key=None):
    script = get(BASE + "wsvc/gmap.asmx/buildCamerasJSONjs").decode("utf-8", "replace")
    start = re.search(r"var camera_data\s*=\s*", script)
    data, _ = json.JSONDecoder().raw_decode(script[start.end():])
    for cam in data.get("cams") or []:
        cam_id = cam.get("md5")
        if not cam_id:
            continue
        time.sleep(0.75)  # about one request a second
        stream = STREAM.search(_player(get, cam_id))
        if not stream:
            continue
        text = re.search(r'<div id="camDescription">(.*?)<span', cam.get("description") or "", re.S)
        text = html.unescape(re.sub(r"<[^>]+>", "", text.group(1))).strip() if text else ""
        county = re.match(r"\[([A-Z]+)\]\s*", text)
        name = text[county.end():] if county else text
        code = county.group(1) if county else None
        bound = BOUND.search(name)
        camera = {
            "id": cam_id,
            "name": name or cam.get("title") or cam_id,
            "lat": float(cam["start_lat"]),
            "lon": float(cam["start_lng"]),
            "image": None,
            "video": stream.group(0),
            "video_type": "hls",
            "road": cam.get("title"),
            "county": COUNTIES.get(code),
            "extra": {"county_code": code},
        }
        if bound:
            camera["approach"] = BOUNDS[bound.group(1)]
        if _live(get, stream.group(0)) is False:
            camera["online"] = False
        yield camera
