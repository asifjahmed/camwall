"""Louisiana: the Lake Pontchartrain Causeway's traffic cameras (Greater New Orleans Expressway Commission). The
Causeway's Traffic page shows them as still pictures in three groups (North Shore, Mid Bridge, South Shore), each a
Dropbox share link the cameras' uploads overwrite about once a minute. The page is read every run; each picture is
known by its Dropbox file id, and the cameras seen when this was written are named and placed here from the labels
burned into their pictures. A picture the page adds later is named from its alt text or its group."""

import html
import re

SOURCE = {
    "name": "Greater New Orleans Expressway Commission (Lake Pontchartrain Causeway)",
    "state": "LA",
    "covers": "The Lake Pontchartrain Causeway: the north toll plaza at Mandeville and the mid-lake crossover",
    "site": "https://thecauseway.us/traffic/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the <img> tags on thecauseway.us/traffic/ (WordPress), whose sources are Dropbox share "
             "links with raw=1 (www.dropbox.com answers 302 to a dl.dropboxusercontent.com JPEG, max-age 60; "
             "1280x720 with a label and timestamp). An earlier check found these links returning HTML and "
             "uploads.thecauseway.us failing TLS; the page now uses only Dropbox links, which work. The South Shore "
             "picture's Dropbox file had been deleted when this was written (Dropbox answers 'File Deleted'), so "
             "that camera is listed out of service. Positions: the toll plaza from OpenStreetMap's toll booth; "
             "'Mid-Bridge' at the Causeway's Crossover 4 (the crossover nearest the middle, assumed); the South "
             "Shore camera at the bridge's south end in Metairie. No terms of use found on the site.",
}
PAGE = "https://thecauseway.us/traffic/"
TOLL_PLAZA = (30.36519, -90.09402)
MID_BRIDGE = (30.19977, -90.12270)
SOUTH_SHORE = (30.02165, -90.15392)
GROUPS = {"north shore": ("North Shore", TOLL_PLAZA), "mid bridge": ("Mid-Bridge", MID_BRIDGE),
          "south shore": ("South Shore", SOUTH_SHORE)}
# Dropbox file id -> name (as its picture labels it), position, the way it looks, online
KNOWN = {
    "wcq6cwmqib4zx66": ("North Toll Plaza - Looking South", TOLL_PLAZA, "South", True),
    "3ad8va2rmpgcyjk": ("North Toll Plaza - Looking North", TOLL_PLAZA, "North", True),
    "m4164d1i2x9yqi3vzmoys": ("Mid-Bridge - Looking North", MID_BRIDGE, "North", True),
    "c2wbyjqzwqm0nsea1b1ri": ("Mid-Bridge - Looking South", MID_BRIDGE, "South", True),
    "6z7erh7dpmtf2tkba2217": ("Mid-Bridge - Looking West", MID_BRIDGE, "West", True),
    "r0f5jpzvd9p572h5o6lwl": ("Mid-Bridge - Looking East", MID_BRIDGE, "East", True),
    "qhi87zlf2vus41tmu6im7": ("South Shore - Looking South", SOUTH_SHORE, "South", False),  # Dropbox: file deleted
}
DROPBOX_ID = re.compile(r"dropbox\.com/(?:s|scl/fi)/([A-Za-z0-9]+)/")


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", "replace")
    page = page[max(page.find("<body"), 0):]  # (the head's og:image repeats the first picture)
    marks = sorted((m.start(), GROUPS[m.group(1).lower()]) for m in
                   re.finditer(r"(North Shore|Mid Bridge|South Shore) Cams", page, re.I))
    seen = set()
    for tag in re.finditer(r"<img\b[^>]*>", page):
        src = re.search(r"""\ssrc=["']([^"']+)["']""", tag.group(0))
        url = html.unescape(src.group(1)) if src else ""
        found = DROPBOX_ID.search(url)
        if not found or found.group(1) in seen:
            continue
        file_id = found.group(1)
        seen.add(file_id)
        group = ([g for at, g in marks if at < tag.start()] or [("Causeway", MID_BRIDGE)])[-1]
        alt = re.search(r"""\salt=["']([^"']*)["']""", tag.group(0))
        name, (lat, lon), looks, online = KNOWN.get(file_id) or (
            html.unescape(alt.group(1)).strip() if alt and alt.group(1).strip() else f"{group[0]} camera",
            group[1], None, True)
        if "raw=1" not in url:
            url += ("&" if "?" in url else "?") + "raw=1"
        yield {
            "id": file_id,
            "name": f"Causeway {name}",
            "lat": lat,
            "lon": lon,
            "image": url,
            "video": None,
            "road": "Lake Pontchartrain Causeway",
            "direction": looks,
            "county": {TOLL_PLAZA: "St. Tammany", SOUTH_SHORE: "Jefferson"}.get((lat, lon)),
            "refresh": 60,
            "online": online,
            "extra": {"group": group[0]},
        }
