"""Arkansas: the City of Rogers Fire Department's traffic camera, embedded on its "Traffic Cams" page (Fire Department >
Training Division) through a Weather Metrics (WetMet) player. Video only: the player page hands out an HLS link signed
for 30 minutes (wmsAuthSign), so resolve() asks it again for a fresh one. No still exists."""

import html
import re

SOURCE = {
    "name": "City of Rogers Fire Department (Weather Metrics player)",
    "state": "AR",
    "covers": "Rogers: I-49 by the Walmart AMP (Pinnacle Hills)",
    "site": "https://www.rogersar.gov/1231/Traffic-Cams",
    "terms": "https://www.rogersar.gov/copyright",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the WetMet iframes (api.wetmet.net/client-content/PlayerFrame.php?CAMERA=<id>) on the "
             "city's Traffic Cams page, which names no camera and gives no location. The player page embeds an HLS "
             "playlist on wmse-us-ea1.wetmet.net signed for 30 minutes (wmsAuthSign; validminutes=30) and answers "
             "403 without it; resolve() reads the player page again. 640x360 H.264, about 300 kbit/s; the player "
             "stops itself after 5 minutes. No snapshot URL was found. Location is estimated from the view (I-49 "
             "with the Walmart AMP's roadside sign in front); a camera the page adds later is placed at Rogers City "
             "Hall until it's identified. rogersar.gov (CivicPlus behind Cloudflare) answers 429 after a dozen or so "
             "requests in a few minutes; the list then falls back to the known camera. The player names no owner (Weather Metrics also runs broadcast weather "
             "cameras); the city publishes it as its own traffic cam. Neither the city's copyright notice nor "
             "Weather Metrics' site states terms for the camera.",
}
PAGE = "https://www.rogersar.gov/1231/Traffic-Cams"
PLAYER = "https://api.wetmet.net/client-content/PlayerFrame.php?CAMERA={}&CFVER=WM"
# What each camera shows and where, judged from its picture (the page says neither).
KNOWN = {
    "170-05-01": ("I-49 by the Walmart AMP (Pinnacle Hills)", 36.3042, -94.1866, "Interstate 49"),
}
CITY_HALL = (36.3343, -94.1186)  # 301 W Chestnut St


def cameras(get, key=None):
    try:
        page = html.unescape(get(PAGE).decode("utf-8", "replace"))
        found = re.findall(r"wetmet\.net/client-content/PlayerFrame\.php\?CAMERA=([\w-]+)", page)
    except OSError:  # (the city's site answers 429 when asked often; the known cameras still play)
        found = list(KNOWN)
    seen = set()
    for cam in found:
        if cam in seen:
            continue
        seen.add(cam)
        name, lat, lon, road = KNOWN.get(cam, (f"Rogers traffic cam {cam}", *CITY_HALL, None))
        yield {
            "id": cam,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": None,
            "video": None,
            "video_type": "hls",
            "road": road,
            "city": "Rogers",
            "county": "Benton",
            "extra": {"wetmet_camera": cam, "location": "estimated from the view" if cam in KNOWN
                      else "unknown: placed at City Hall"},
        }


def resolve(get, camera, key=None):
    """A freshly signed HLS link from the camera's WetMet player page."""
    page = get(PLAYER.format(camera["id"])).decode("utf-8", "replace")
    m = re.search(r"https://[\w.-]+\.wetmet\.net/live/[\w-]+/playlist\.m3u8\?wmsAuthSign=[\w=%+-]+", page)
    return {"image": None, "video": m.group(0) if m else None, "video_type": "hls"}
