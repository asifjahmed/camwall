"""Kenai, Alaska: the City of Kenai's dipnet-fishery cameras (kenai.city/dipnet/page/dipnet-cameras), live HLS from the
city's Wowza server (video.kenai.city). They watch the beach access roads, streets and parking lots at North Beach,
South Beach (Royal Ct.), the City Dock and Boat Launch Road, and run all year, not only in the July fishery. The
cameras that show only sand, water or the river (North Beach East and West End, South Beach North End, the boat launch,
the Kenai River) are left out.

Each camera's player page (stream.kenai.city/<page>.htm) names its playlist, which is read on every run because the
city moves streams between Wowza applications. The pages give no positions: these are where the views are, placed by
hand from the streets they show, to within a hundred metres or so."""

import re
import time

SOURCE = {
    "name": "City of Kenai (dipnet cameras)",
    "state": "AK",
    "covers": "Kenai: North Beach and South Beach access roads and parking, Kenai Avenue, Boat Launch Road and the City "
              "Dock parking lot",
    "site": "https://www.kenai.city/dipnet/page/dipnet-cameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the city's camera page and each camera's player page. Live HLS (Wowza, unsigned, 3 s "
             "segments, about 3 Mbit/s); no snapshot URL (the Wowza thumbnail service answers 404). The city's site "
             "has no terms of use or disclaimer. Positions are hand-placed from the streets in view. Camera ids are "
             "the player pages' names. Two of the city's cameras (Upper Spruce St, seasonal, and the Kenai River) "
             "had no stream in November 2026.",
}
PLAYERS = "https://stream.kenai.city"
PLAYLIST = re.compile(r"""src=["'](https?://[^"']+\.m3u8)["']""")

# player page -> (name, as the camera's own caption gives it; lat; lon; road)
CAMERAS = {
    "nb_park": ("North Beach Parking", 60.55186, -151.27380, "South Spruce Street"),
    "nb_west": ("North Beach West", 60.55230, -151.27520, "North Beach access road"),
    "kenaiave": ("Kenai Ave", 60.55100, -151.26960, "Kenai Avenue"),
    "llparking": ("Little League Parking", 60.55755, -151.27181, "South Spruce Street"),
    "sb_west": ("Royal Ct. Looking West", 60.53311, -151.27056, "Royal Street"),
    "sb_north": ("Royal Ct. Facing North", 60.53311, -151.27056, "Royal Street"),
    "sb_east": ("Royal Ct. Looking East", 60.53311, -151.27056, "Royal Street"),
    "dockrd": ("Boat Launch Road", 60.54200, -151.21500, "Boat Launch Road"),
    "dockpark": ("Dock Parking Lot", 60.54211, -151.21894, "Boat Launch Road"),
}


def cameras(get, key=None):
    first = True
    for page, (name, lat, lon, road) in CAMERAS.items():
        if not first:
            time.sleep(0.75)  # (about one request a second)
        first = False
        try:
            html = get(f"{PLAYERS}/{page}.htm").decode("utf-8", "replace")
        except OSError:
            continue  # (a camera the city has taken down)
        match = PLAYLIST.search(html)
        if not match:
            continue
        yield {
            "id": page,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": None,
            "video": match[1],
            "video_type": "hls",
            "road": road,
            "city": "Kenai",
            "county": "Kenai Peninsula Borough",
            "extra": {"player": f"{PLAYERS}/{page}.htm", "position": "approximate"},
        }
