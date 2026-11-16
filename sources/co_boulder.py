"""Boulder: the City of Boulder's four major-intersection cameras, live video only. Each is a "quad" view (the four
approaches in one picture) streamed as open HLS from the City's Wowza server (videostream.bouldercolorado.gov). The
cameras and their locations come from the City's ArcGIS layer (maps.bouldercolorado.gov, IT/TrafficCameras layer 0,
used by its camera map); the streams from the City's webcam page, matched by name. The page's poster pictures are
static (from 2020), so no still is given."""

import json
import re
from html import unescape

SOURCE = {
    "name": "City of Boulder",
    "state": "CO",
    "covers": "Four major Boulder intersections (Broadway & Canyon, Foothills & Arapahoe, 28th & Colorado, 28th & Iris)",
    "site": "https://bouldercolorado.gov/traffic-cameras",
    "terms": "https://bouldercolorado.gov/privacy-policy",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Live HLS only (quad views of all four approaches), no token. Locations from the City's public ArcGIS "
             "MapServer; streams from https://webappsprod.bouldercolorado.gov/webcams/index.php. The City's site has "
             "a privacy policy but no terms of use.",
}
LAYER = "https://maps.bouldercolorado.gov/arcgis/rest/services/IT/TrafficCameras/MapServer/0"
PAGE = "https://webappsprod.bouldercolorado.gov/webcams/index.php"


def _key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower().replace(" and ", ""))


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", "replace")
    streams = {}
    for title, src in re.findall(r"<h3>\s*([^<]+?)\s*</h3>.*?<source src='([^']+\.m3u8)'", page, re.S):
        streams[_key(unescape(title))] = src
    data = json.loads(get(f"{LAYER}/query?where=1%3D1&outFields=*&outSR=4326&f=json"))
    for feature in data.get("features") or []:
        a, geometry = feature.get("attributes") or {}, feature.get("geometry") or {}
        name = (a.get("NAME") or "").strip()
        video = streams.get(_key(name))
        if not name or not video:
            continue
        yield {
            "id": re.search(r"smil:([^/]+)\.smil", video).group(1) if "smil:" in video else str(a.get("ID")),
            "name": name,
            "lat": geometry.get("y"),
            "lon": geometry.get("x"),
            "image": None,
            "video": video,
            "video_type": "hls",
            "city": "Boulder",
            "county": "Boulder",
            "extra": {"address": a.get("GEOCODEADDRESS"), "view": "quad (all four approaches)"},
        }
