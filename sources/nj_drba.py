"""New Jersey and Delaware: the Delaware River and Bay Authority's traffic cameras at the Delaware Memorial Bridge
(I-295 approaches on both banks and the toll plaza) and at the Cape May-Lewes Ferry terminals (toll booths, staging
lanes, Freeman Highway). The two public pages embed JW Player items; JW Player's media API resolves each to an
unsigned Wowza HLS stream (no key). Video only."""

import html
import json
import re

SOURCE = {
    "name": "Delaware River and Bay Authority",
    "state": ["NJ", "DE"],
    "covers": "Delaware Memorial Bridge (I-295) approaches and toll plaza; Cape May-Lewes Ferry terminal approaches "
              "at North Cape May NJ and Lewes DE",
    "site": "https://www.delawarememorialbridge.com/dmb-travel",
    "terms": "https://www.drba.net/privacy-policy",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the cameras are the JW Player embeds on delawarememorialbridge.com/dmb-travel and "
             "cmlf.com/check-traffic-live-webcam-feeds/; cdn.jwplayer.com/v2/media/<id> gives each one's HLS URL "
             "(5b18e54927a82.streamlock.net/live/<name>.stream/playlist.m3u8, unsigned). No stills: JW Player's "
             "poster is a fixed picture from years ago. The ferry page's scenic views (osprey nest, lawns, the Grain "
             "on the Rocks restaurant) are left out. The pages give no positions, so these are placed by hand from "
             "OpenStreetMap (bridge ends, toll plaza, terminals); treat them as approximate. DRBA's terms of use "
             "(on its privacy page) reserve copyright and forbid getting material 'through any means not "
             "intentionally made available'; they don't mention cameras or redistribution.",
}
PAGES = [
    ("dmb", "https://www.delawarememorialbridge.com/dmb-travel"),
    ("ferry", "https://www.cmlf.com/check-traffic-live-webcam-feeds/"),
]
MEDIA = "https://cdn.jwplayer.com/v2/media/{}"
SCENIC = re.compile(r"osprey|green|grain|on the rocks", re.I)  # ferry views that show no road

# Where each stream is (by its Wowza stream name), with its state, county and road; looked up on OpenStreetMap.
PLACES = {
    "83A": (39.6952, -75.5395, "DE", "New Castle", "I-295"),
    "92A": (39.6948, -75.5385, "DE", "New Castle", "I-295"),
    "gantry20": (39.6840, -75.5040, "NJ", "Salem", "I-295"),
    "Gantry0ne": (39.6843, -75.5030, "NJ", "Salem", "I-295"),
    "gantry10": (39.6963, -75.5454, "DE", "New Castle", "I-295"),
    "TollplazaFront": (39.6961, -75.5458, "DE", "New Castle", "I-295"),
    "CapeMayTollBooth": (38.9680, -74.9585, "NJ", "Cape May", "Lincoln Blvd"),
    "CapeMayParkingLot": (38.9689, -74.9600, "NJ", "Cape May", None),
    "CapeMayParkingLot-2": (38.9687, -74.9594, "NJ", "Cape May", None),
    "LewesTollBooth": (38.7815, -75.1210, "DE", "Sussex", "Cape Henlopen Dr"),
    "LewesParkingLot": (38.7825, -75.1200, "DE", "Sussex", None),
    "FreemanHighway": (38.7759, -75.1296, "DE", "Sussex", "Theodore C Freeman Hwy"),
}
FALLBACK = {  # a stream not in PLACES goes at its site: the bridge, or the ferry terminal its label names
    "dmb": (39.6899, -75.5207, "DE", "New Castle", "I-295"),
    "cape may": (38.9689, -74.9606, "NJ", "Cape May", None),
    "lewes": (38.7825, -75.1197, "DE", "Sussex", None),
}


def _embeds(page):
    """(label, JW media id) for each player on the page, the label being the heading or table cell before it."""
    out, label = [], None
    for m in re.finditer(r"<h[2-6][^>]*>(.*?)</h[2-6]>|<td[^>]*>([^<]+)</td>|cdn\.jwplayer\.com/players/([A-Za-z0-9]{8})-",
                         page, re.S | re.I):
        if m.group(3):
            out.append((label, m.group(3)))
        else:
            text = html.unescape(re.sub(r"<[^>]+>|\s+", " ", m.group(1) or m.group(2))).strip()
            if text:
                label = text
    return out


def cameras(get, key=None):
    seen = set()
    for site, url in PAGES:
        page = get(url).decode("utf-8", errors="replace")
        for label, media in _embeds(page):
            if media in seen:
                continue
            seen.add(media)
            item = (json.loads(get(MEDIA.format(media))).get("playlist") or [{}])[0]
            hls = next((s["file"] for s in item.get("sources") or [] if ".m3u8" in s.get("file", "")), None)
            name = label or item.get("title") or media
            if not hls or (site == "ferry" and SCENIC.search(name)):
                continue
            stream = re.search(r"/live/([^/]+?)\.stream/", hls)
            stream = stream.group(1) if stream else media
            where = PLACES.get(stream) or FALLBACK["dmb" if site == "dmb" else "lewes" if "lewes" in name.lower()
                                                    else "cape may"]
            lat, lon, state, county, road = where
            cam = {
                "id": stream,
                "name": name if site == "ferry" else f"Delaware Memorial Bridge: {name}",
                "lat": lat,
                "lon": lon,
                "image": None,
                "video": hls,
                "video_type": "hls",
                "state": state,
                "county": county,
                "extra": {"jwplayer": media, "title": item.get("title"), "page": url, "position": "approximate"},
            }
            if road:
                cam["road"] = road
            bound = re.search(r"\b(North|South) ?Bound\b", name, re.I)
            if bound:
                cam["approach"] = bound.group(1).capitalize() + "bound"
            yield cam
