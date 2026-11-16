"""Maine: the Maine Turnpike Authority's cameras on the Turnpike (I-95, Kittery to Augusta), from its Traffic Cams page
(no key). Stills only, refreshed every minute or two. Each caption gives the milepost, the town and which way the
camera looks ("Mile 25.3 - Kennebunk Looking North"). New England 511 (nh_newengland511) shows only the Authority's
Kittery-area cameras, not these.

The page gives no positions, so each camera is placed by its milepost, between the Turnpike's mile markers as MaineDOT's
Interstate Mileposts layer locates them (extra["position"] = "milepost"; within about 100 m along the road). The
Authority's own Turnpike map has a pin per camera site too, but several of its pins are a mile or more from the
milepost the caption gives (its York toll pin is in Wells), so the mileposts are used instead.

The page doesn't say which cameras work, and a few pictures stop updating for months (the Androscoggin River camera's
was last changed in April 2026). So each picture is asked, politely, whether it has changed in the last day (a
conditional request for its first two bytes); one that hasn't, or that's missing, makes its camera online False, with
extra.picture saying which."""

import email.utils
import html
import re
import time
from urllib.parse import quote

SOURCE = {
    "name": "Maine Turnpike Authority",
    "state": "ME",
    "covers": "The Maine Turnpike (I-95) from Kittery to Augusta",
    "site": "https://www.maineturnpike.com/traveler-services/traffic-cams",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "The Traffic Cams page's pictures (/cameras/<name>.jpg) and captions; no list or positions are published, "
             "so positions are placed by the caption's milepost on MaineDOT's Interstate Mileposts layer "
             "(arcgisserver.maine.gov MaineDOT_Dynamic MapServer/76, I-95 miles 1 to 110; extra[\"position\"] = "
             "\"milepost\"). No terms of use are posted. Captions say which way each camera looks, which is given as "
             "its direction. A picture not changed in 24 hours, or missing, makes its camera online False "
             "(extra.picture).",
}
BASE = "https://www.maineturnpike.com"
PAGE = BASE + "/traveler-services/traffic-cams"
# I-95 mile -> lat, lon of its mile markers (the middle of the two carriageways' markers), from MaineDOT's Interstate
# Mileposts layer (https://arcgisserver.maine.gov/arcgis/rest/services/mdot/MaineDOT_Dynamic/MapServer/76, routes
# 0095X and 0095S), fetched 2026-11-08. Turnpike mileage is I-95's: the Gray plaza (mile 59) and the West Gardiner
# plaza (exits 102-103) fall within a quarter mile of those mileposts.
MILEPOSTS = {
    1: (43.10191, -70.75107), 2: (43.11217, -70.73779), 3: (43.12255, -70.72486), 4: (43.13395, -70.71316),
    5: (43.14190, -70.69692), 6: (43.14968, -70.68047), 7: (43.15727, -70.66430), 8: (43.16832, -70.65297),
    9: (43.18209, -70.64797), 10: (43.19612, -70.64482), 11: (43.21016, -70.64151), 12: (43.22404, -70.63708),
    13: (43.23773, -70.63181), 14: (43.25072, -70.62384), 15: (43.26437, -70.61937), 16: (43.27860, -70.61790),
    17: (43.29283, -70.61647), 18: (43.30704, -70.61502), 19: (43.32063, -70.60969), 20: (43.33386, -70.60228),
    21: (43.34748, -70.59474), 22: (43.36092, -70.58721), 23: (43.37454, -70.57959), 24: (43.38680, -70.57276),
    25: (43.40031, -70.56523), 26: (43.41348, -70.55790), 27: (43.42653, -70.55007), 28: (43.43910, -70.54081),
    29: (43.45164, -70.53147), 30: (43.46380, -70.52139), 31: (43.47363, -70.50711), 32: (43.48505, -70.49532),
    33: (43.49827, -70.48859), 34: (43.50983, -70.47626), 35: (43.52047, -70.46206), 36: (43.53034, -70.44998),
    37: (43.54161, -70.43793), 38: (43.55296, -70.42604), 39: (43.56428, -70.41412), 40: (43.57562, -70.40214),
    41: (43.58684, -70.39011), 42: (43.59854, -70.37879), 43: (43.61001, -70.36726), 44: (43.62141, -70.35531),
    45: (43.63276, -70.34355), 46: (43.64443, -70.33258), 47: (43.65853, -70.33169), 48: (43.67250, -70.32884),
    49: (43.68604, -70.32275), 50: (43.69985, -70.31575), 51: (43.71271, -70.30731), 52: (43.72670, -70.30362),
    53: (43.74078, -70.30242), 54: (43.75491, -70.30467), 55: (43.76798, -70.31224), 56: (43.78215, -70.31412),
    57: (43.79636, -70.31568), 58: (43.81057, -70.31699), 59: (43.82456, -70.32084), 60: (43.83856, -70.32464),
    61: (43.85274, -70.32278), 62: (43.86673, -70.32641), 63: (43.87987, -70.33389), 64: (43.89310, -70.34146),
    65: (43.90721, -70.34019), 66: (43.92139, -70.33761), 67: (43.93554, -70.33502), 68: (43.94967, -70.33241),
    69: (43.96333, -70.32672), 70: (43.97579, -70.31756), 71: (43.98824, -70.30973), 72: (44.00228, -70.30671),
    73: (44.01488, -70.29758), 74: (44.02754, -70.28852), 75: (44.03622, -70.27324), 76: (44.04178, -70.25497),
    77: (44.04860, -70.23773), 78: (44.05539, -70.22027), 79: (44.06602, -70.20569), 80: (44.07237, -70.18980),
    81: (44.06840, -70.17095), 82: (44.06673, -70.15158), 83: (44.07307, -70.13399), 84: (44.08076, -70.11747),
    85: (44.09011, -70.10261), 86: (44.09991, -70.08814), 87: (44.10808, -70.07188), 88: (44.11613, -70.05562),
    89: (44.12356, -70.03879), 90: (44.12447, -70.01904), 91: (44.12473, -69.99925), 92: (44.12517, -69.97947),
    93: (44.12887, -69.96080), 94: (44.13659, -69.94325), 95: (44.14379, -69.92704), 96: (44.15118, -69.91011),
    97: (44.15862, -69.89320), 98: (44.16607, -69.87629), 99: (44.17632, -69.86304), 100: (44.18811, -69.85186),
    101: (44.19992, -69.84076), 102: (44.21172, -69.82960), 103: (44.22356, -69.81857), 104: (44.23574, -69.80850),
    105: (44.24994, -69.80740), 106: (44.26418, -69.80676), 107: (44.27844, -69.80633), 108: (44.29268, -69.80714),
    109: (44.30815, -69.80826), 110: (44.32191, -69.81433),
}
LOOKS = {"north": "N", "south": "S", "east": "E", "west": "W"}
STALE = 24 * 3600  # a picture older than this is taken for a camera out of service
GAP = 1.0  # seconds between picture checks


def _place(mile):
    """lat, lon for a Turnpike milepost, between the mile markers on either side (beyond the ends, the nearest two)."""
    low = min(max(int(mile), min(MILEPOSTS)), max(MILEPOSTS) - 1)
    (lat1, lon1), (lat2, lon2) = MILEPOSTS[low], MILEPOSTS[low + 1]
    f = mile - low
    return lat1 + f * (lat2 - lat1), lon1 + f * (lon2 - lon1)


def _picture(get, url, since):
    """None if the picture has changed since `since`, else why not: "not updated in 24 hours", "missing" or "no
    answer" (a timeout or a server error)."""
    try:
        get(url, headers={"If-Modified-Since": since, "Range": "bytes=0-1"})
        return None
    except OSError as e:
        if "HTTP 304" in str(e):
            return "not updated in 24 hours"
        return "missing" if "HTTP 404" in str(e) or "HTTP 410" in str(e) else "no answer"


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", errors="replace")
    since = email.utils.formatdate(time.time() - STALE, usegmt=True)
    seen = set()
    for block in re.findall(r'<div class="item-box">(.*?<div class="item-box-desc">.*?)</div>', page, flags=re.S):
        picture = re.search(r'href="(/cameras/[^"?]+\.jpg)"', block)
        caption = re.search(r"<h4>\s*Mile\s+([\d.]+)\s*-\s*([^<]+?)\s*</h4>", block)
        if not picture or not caption or picture.group(1) in seen:
            continue
        seen.add(picture.group(1))
        mile, where = float(caption.group(1)), html.unescape(caption.group(2)).strip()
        look = re.search(r"<small>\s*Looking\s+(North|South|East|West)", block, flags=re.I)
        if look:
            where = f"{where} looking {look.group(1).lower()}"
        lat, lon = _place(mile)
        image = BASE + quote(picture.group(1))
        if len(seen) > 1:
            time.sleep(GAP)
        problem = _picture(get, image, since)
        yield {
            "id": picture.group(1).removeprefix("/cameras/"),
            "name": f"Maine Turnpike Mile {caption.group(1)} - {where}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "image": image,
            "road": "I-95 (Maine Turnpike)",
            "direction": LOOKS[look.group(1).lower()] if look else None,
            "refresh": 60,
            "online": problem is None,
            "extra": {"mile": mile, "position": "milepost", **({"picture": problem} if problem else {})},
        }
