"""Maine: MaineDOT's own camera pages on maine.gov, "All MaineDOT Traffic Cameras" (/mdot/cams/all/, linked from
MaineDOT's Traffic Cameras page) and the Wiscasset traffic page (/mdot/maps/wiscasset/). Stills only
(/mdot/maps/cameras/<file>), from MaineDOT's interstate cameras on I-295 and I-95 north of the Turnpike, plus a few on
Routes 1, 11 and 161.

About half of them are also on New England 511 (nh_newengland511), where the same camera's picture is larger and newer;
those are given extra.duplicate_of ("nh_newengland511:<id>", matched by name through the New England Compass feed on
2026-11-08 and spot-checked by picture). The rest aren't on 511, which leaves out some of MaineDOT's cameras: those
Compass calls offline even though their pictures here still update (I-295 in Falmouth and Freeport, Soucy Hill), and
a few Compass calls online (I-95 at Island Falls, Oakfield and Smyrna).

The pages give no positions except the Wiscasset page's map. Each camera's caption ("Falmouth 9 NB") names its town,
mile and direction, so it's placed at the camera MaineDOT's Compass feed lists on that road, direction and mile
(extra.position = "compass"), or failing that at that milepost from MaineDOT's Interstate Mileposts layer
("milepost"). Cameras whose captions name no mile have positions written here ("fixed").

The page doesn't say which cameras work, and many of its pictures are months old or gone. So each picture is asked,
politely, whether it has changed in the last day (a conditional request for its first two bytes): a picture that
hasn't, or that's missing, makes the camera online False, with extra.picture saying which."""

import email.utils
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

SOURCE = {
    "name": "Maine Department of Transportation (MaineDOT)",
    "state": "ME",
    "covers": "MaineDOT's cameras on I-295, I-95 from Augusta to Houlton, and a few on Routes 1, 11 and 161",
    "site": "https://www.maine.gov/dot/publications/traffic-engineering/traffic-cameras",
    "terms": "https://www.maine.gov/portal/policies/disclaimer.html",
    "key": None,
    "headers": {},
    "restricted": None,
    "credit": "MaineDOT",
    "notes": "Undocumented: the camera list is MaineDOT's \"All MaineDOT Traffic Cameras\" page (linked from its "
             "Traffic Cameras page) and its Wiscasset page, read from www1.maine.gov, which serves the same files as "
             "www.maine.gov; www.maine.gov's CloudFront answers 403 to user agents that aren't browsers, camwall's "
             "included. Pictures change every 1 to 15 minutes; a picture not changed in 24 hours, or "
             "missing, makes its camera online False (extra.picture). Positions come from MaineDOT's documented New "
             "England Compass feed (https://nec-por.ne-compass.com/DeveloperPortal, cctvStatusData) or its Interstate "
             "Mileposts layer (arcgisserver.maine.gov MaineDOT_Dynamic/76); see extra.position. Cameras also on New "
             "England 511 have extra.duplicate_of. Maine.gov's content disclaimer sets no limits on reuse; Compass's "
             "terms ask that the data's source be acknowledged (credit MaineDOT).",
}
BASE = "https://www1.maine.gov"
PAGES = (BASE + "/mdot/cams/all/", BASE + "/mdot/maps/wiscasset/")
COMPASS = "https://nec-por.ne-compass.com/NEC.XmlDataPortal/api/c2c?networks=Maine&dataTypes=cctvStatusData"
MILEPOSTS = ("https://arcgisserver.maine.gov/arcgis/rest/services/mdot/MaineDOT_Dynamic/MapServer/76/query"
             "?where={}&outFields=latitude,longitude&returnGeometry=false&f=json")
C2C = "{http://its.gov/c2c_icd}"
STALE = 24 * 3600  # a picture older than this is taken for a camera out of service
GAP = 1.0  # seconds between picture checks
# Cameras whose captions give no interstate mile: file -> lat, lon, road (positions from the New England Compass feed's
# cameras of the same names: "Rt 11 Soucy Hill (Rwis)", "Rt 161 Mile 89 (Dickey Bridge, Allagash)", "RT1 Mile 6.7 SB
# Bath"), and the Wiscasset page's map, for when that page doesn't load.
FIXED = {
    "souciehill.jpg": (46.91515, -68.515699, "ME-11"),
    "dickey_Public.jpg": (47.112566, -69.089445, "ME-161"),
    "bathrt1wb.jpg": (43.911781, -69.843772, "US-1"),
    "wiscassetnb.jpg": (44.001309, -69.678776, "US-1"),
    "wiscassetsb.jpg": (43.999519, -69.67693, "US-1"),
    "edgecomb.jpg": (44.001171, -69.634708, "US-1"),
}
# Cameras New England 511 also shows (its view ids), matched by name through Compass on 2026-11-08.
DUPLICATES = {
    "VC0091.jpg": "2138", "VC0101.jpg": "2117", "VC0152.jpg": "2125", "VC0151.jpg": "2123", "VC0172.jpg": "2129",
    "VC0171.jpg": "2179", "VC03701.jpg": "2238", "VC0492.jpg": "2121", "VC0491.jpg": "2126", "VC0512.jpg": "2122",
    "MM1091.jpg": "2119", "MM1122.jpg": "2149", "MM1270.jpg": "2136", "MM1382.jpg": "2081", "MM1381.jpg": "2098",
    "MM1501.jpg": "2082", "MM1502.jpg": "2145", "MM1572.jpg": "2099", "MM1611.jpg": "2084", "MM1671.jpg": "2100",
    "MM1742.jpg": "2077", "MM1740.jpg": "2085", "MM1801.jpg": "2086", "MM1870.jpg": "2111", "MM1912.jpg": "2151",
    "cr1912_Public.jpg": "2087", "MM1932.jpg": "2114", "MM1971.jpg": "2105", "MM1972.jpg": "2108",
    "MM1992.jpg": "2107", "MM2272.jpg": "2101", "MM2270.jpg": "2106", "cr2412_Public.jpg": "2088",
    "MM2852.jpg": "2103",
}
WAYS = {"NB": "Northbound", "SB": "Southbound", "EB": "Eastbound", "WB": "Westbound"}


def _listed(get):
    """[(file, caption, lat, lon)] from the pages, in page order; lat and lon only where a page gives them."""
    out, seen = [], {}
    for url in PAGES:
        try:
            page = get(url).decode("utf-8", errors="replace")
        except OSError:
            if url == PAGES[0]:
                raise
            continue  # (the Wiscasset page only adds positions, and one camera)
        page = re.sub(r"<!--.*?-->", "", page, flags=re.S)  # (the all-cameras page keeps retired cameras in comments)
        found = [(m.group(1), m.group(2), None, None) for m in re.finditer(
            r'data-img="/mdot/maps/cameras/([^"]+)"[^>]*>\s*</a>\s*<p class="local-caption">([^<]*)</p>', page)]
        found += [(m.group(4), m.group(3), float(m.group(1)), float(m.group(2))) for m in re.finditer(
            r"\[\s*(-?\d+\.\d+),\s*(-?\d+\.\d+),\s*'([^']+)',\s*'https?://(?:www1?\.)?maine\.gov/mdot/maps/cameras/"
            r"([^'?]+)'", page)]
        for file, caption, lat, lon in found:
            caption = html.unescape(caption).strip()
            if file in seen:  # (on both pages: the Wiscasset page's position)
                if lat is not None:
                    out[seen[file]] = (file, out[seen[file]][1], lat, lon)
                continue
            seen[file] = len(out)
            out.append((file, caption, lat, lon))
    return out


def _compass(get):
    """[(road, mile, way, lat, lon, retired)] for Compass's interstate cameras, whose names give road, mile and way."""
    try:
        root = ET.fromstring(get(COMPASS))
    except (OSError, ET.ParseError):
        return []
    out = []
    for cam in root.iter(C2C + "cctvStatus"):
        names = (cam.get("id") or "", cam.findtext(C2C + "name") or "")
        for name in names:
            m = re.search(r"I-?\s?(95|295|395)\s+Mile\s+(\d+(?:\.\d+)?)\s+(NB|SB|EB|WB)", name)
            if m:
                break
        try:
            lat, lon = int(cam.findtext(C2C + "lat")) / 1e6, int(cam.findtext(C2C + "lon")) / 1e6
        except (TypeError, ValueError):
            continue
        if m and lat and lon:
            retired = any(n.strip().lower().startswith(("retired", "zretired")) for n in names)
            out.append(("I-" + m.group(1), float(m.group(2)), m.group(3), lat, lon, retired))
    return out


def _milepost(get, road, mile, way):
    """lat, lon of an interstate milepost on that carriageway, from MaineDOT's Interstate Mileposts layer, or None."""
    route = "0{}{}".format(road[2:].zfill(3), "S" if way in ("SB", "WB") else "X")
    try:
        found = json.loads(get(MILEPOSTS.format(quote(f"route='{route}' AND milepost={round(mile)}"))))["features"]
        return found[0]["attributes"]["latitude"], found[0]["attributes"]["longitude"]
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None


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
    compass = _compass(get)
    since = email.utils.formatdate(time.time() - STALE, usegmt=True)
    for n, (file, caption, lat, lon) in enumerate(_listed(get)):
        road, city, approach, position = (FIXED.get(file) or (None, None, None))[2], None, None, "page"
        m = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)\s+(NB|SB)$", caption)
        if m and re.search(r"\b(Rt|Route|US)\b", m.group(1), flags=re.I):
            m = None  # ("Bath Rt 1 NB" would be a route number, not an interstate mile)
        if m:  # "Falmouth 9 NB": MaineDOT's own interstate cameras are on I-295 (miles 1-52) and I-95 above mile 108
            city, mile, way = m.group(1), float(m.group(2)), m.group(3)
            road, approach = ("I-295" if mile < 60 else "I-95"), WAYS[way]
            near = sorted((c for c in compass if c[0] == road and c[2] == way and abs(c[1] - mile) <= 1.5),
                          key=lambda c: (c[5], abs(c[1] - mile)))
            if lat is None and near:
                lat, lon, position = near[0][3], near[0][4], "compass"
            elif lat is None and (spot := _milepost(get, road, mile, way)):
                (lat, lon), position = spot, "milepost"
        if lat is None and file in FIXED:
            lat, lon, position = FIXED[file][0], FIXED[file][1], "fixed"
        if lat is None:
            continue  # (a camera with nothing to place it by)
        if not approach:
            way = re.search(r"\b(NB|SB|EB|WB|Northbound|Southbound|Eastbound|Westbound)\b", caption)
            approach = WAYS.get(way.group(1), way.group(1)) if way else None
        image = f"{BASE}/mdot/maps/cameras/{quote(file)}"
        if n:
            time.sleep(GAP)
        problem = _picture(get, image, since)
        yield {
            "id": file,
            "name": f"{caption} ({road})" if m else caption,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "image": image,
            "road": road,
            "approach": approach,
            "city": city,
            "online": problem is None,
            "extra": {k: v for k, v in {"position": position, "picture": problem,
                                        "duplicate_of": f"nh_newengland511:{DUPLICATES[file]}"
                                        if file in DUPLICATES else None}.items() if v},
        }
