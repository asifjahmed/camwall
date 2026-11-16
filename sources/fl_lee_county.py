"""Florida: Lee County DOT's live traffic cameras, the "Matlacha live traffic cameras" pilot on the county's Traffic
page (two cameras on the Pine Island Road drawbridge at Matlacha, and one at the Sanibel Causeway toll plaza). The page
embeds each camera as an HLS player and also links its playlist ("East Bound Camera for Mobile Users"); those links
are the list. The page gives no positions, so each camera is placed by its label from the table below (OpenStreetMap:
the Matlacha Pass movable span on CR 78, and Lee County's toll gantry on the causeway approach); a camera whose label
isn't in the table is left out. The county's signal cameras (CCTV at dozens of intersections, watched from its Traffic
Operations Center) aren't public."""

import html
import re

# The county's own page, then the same page on the county's CivicPlus host (www.leefl.gov sits behind Cloudflare and
# www.leegov.com behind Akamai, and both refuse some networks).
PAGES = ("https://www.leefl.gov/953/Traffic", "https://fl-leecounty.civicplus.com/953/Traffic")
LINK = re.compile(r'<a href="(https://cdn3\.wowza\.com/[^"]+\.m3u8)"[^>]*>\s*([^<]+?)\s+for Mobile Users\s*</a>', re.I)

SOURCE = {
    "name": "Lee County DOT",
    "state": "FL",
    "covers": "Pine Island Road (CR 78) at the Matlacha Pass drawbridge, and the Sanibel Causeway toll plaza",
    "site": "https://www.leefl.gov/953/Traffic",
    "terms": "https://www.leefl.gov/1210/Privacy-Security-Accessibility",
    "key": None,
    "headers": {},
    "restricted": "The county website's terms (Privacy, Security & Accessibility, \"Linking\"): \"Under no "
                  "circumstances may you 'frame' the website or any of its content. Each page within the website "
                  "must be displayed in full, without any accompanying frame, design, branding, advertising or "
                  "promotional materials.\"",
    "notes": "The playlist links on the county's Traffic page (a CivicPlus page; read from www.leefl.gov, or from the "
             "county's CivicPlus host fl-leecounty.civicplus.com when that refuses). A pilot program the county says "
             "it will evaluate, so the cameras may go away. Video only: unsigned HLS on Wowza Streaming Cloud "
             "(cdn3.wowza.com), 1920x1080 at 15-30 fps, with the camera's name and the county's logo burned in; the "
             "page's posters are fixed PNGs, and Wowza gives no snapshot. The county says none of its cameras record. "
             "Positions are from OpenStreetMap, not the county. 'Restricted' is a judgment call: the clause is the "
             "website's linking policy, read as covering its camera video shown inside another app.",
}

# label on the page (lower case) -> (name, lat, lon, road, city, approach)
PLACES = {
    "east bound camera": ("Matlacha Bridge Eastbound", 26.63256, -82.06783, "Pine Island Rd (CR 78)", "Matlacha",
                          "Eastbound"),
    "west bound camera": ("Matlacha Bridge Westbound", 26.63256, -82.06783, "Pine Island Rd (CR 78)", "Matlacha",
                          "Westbound"),
    "sanibel toll plaza camera": ("Sanibel Causeway Toll Plaza", 26.48465, -82.00855, "Sanibel Causeway", None, None),
}


def _links(get):
    """(playlist URL, label) pairs from the first copy of the page that has any."""
    error = None
    for page in PAGES:
        try:
            found = LINK.findall(get(page).decode("utf-8", "replace"))
        except OSError as e:
            error = e
            continue
        if found:
            return found
    if error:
        raise error
    return []


def cameras(get, key=None):
    seen = set()
    for url, label in _links(get):
        url = html.unescape(url)
        place = PLACES.get(" ".join(html.unescape(label).lower().split()))
        path = url.removeprefix("https://cdn3.wowza.com/1/").removesuffix("/hls/live/playlist.m3u8")
        if not place or path in seen:
            continue
        seen.add(path)
        name, lat, lon, road, city, approach = place
        camera = {
            "id": path,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": None,
            "video": url,
            "video_type": "hls",
            "road": road,
            "county": "Lee",
            "extra": {"label": html.unescape(label).strip()},
        }
        if city:
            camera["city"] = city
        if approach:
            camera["approach"] = approach
        yield camera
