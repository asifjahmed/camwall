"""Georgia: GDOT's cameras on 511GA (Arcadis IBI's 511 platform), from the camera list its List page loads (no key).
GDOT's Skyline/Navigator network covers metro Atlanta's freeways and signals (including many city and county
signal cameras GDOT's Regional Traffic Operations Program runs) and the state's interstates. Every camera has a still
at /map/Cctv/<id>, and HLS video whose URL must be signed by the site (see resolve)."""

import json
import re
import time
from urllib.parse import quote

BASE = "https://511ga.org"

SOURCE = {
    "name": "GDOT (511GA)",
    "state": "GA",
    "covers": "Georgia's interstates and state routes, metro Atlanta freeways and signalised arterials",
    "site": "https://511ga.org/cctv",
    "terms": "https://511ga.org/terms",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the DataTables list behind 511ga.org/cctv (/List/GetData/Cameras, 100 a page). 511GA also "
             "has a documented API (511ga.org/developers/doc, /api/v2/get/cameras) that needs a free key from a "
             "registered account and allows 10 calls a minute. Stills are 450x253 PNG with a GDOT caption, cached "
             "60 s by CloudFront (one picture didn't change over 2 minutes, so the real refresh is unknown). "
             "Video is HLS on sfs-msc-pub-lq-0N.navigator.dot.ga.gov; the listed URL answers 401 until signed "
             "by GET /Camera/GetVideoUrl?imageId=<id>, which returns it with a JWT that expires after 2 minutes. "
             "Cameras that are down aren't flagged: their still is a 'STREAM NOT AVAILABLE' PNG (about 7.5 KB) "
             "and their "
             "video doesn't answer. The terms page is empty. The list's direction (Northbound...) is the roadway "
             "direction, given as approach; county and city come from the bracketed place that ends each camera's "
             "name (the list's own county and city are empty; Gwinnett DOT's GWIN- cameras have none, so they get "
             "Gwinnett).",
}


# Georgia's 159 counties: a camera's name ends with its county or city in brackets ("... (BARTOW)", "... (Atlanta)")
COUNTIES = {c.upper(): c for c in (
    "Appling Atkinson Bacon Baker Baldwin Banks Barrow Bartow Berrien Bibb Bleckley Brantley Brooks Bryan Bulloch "
    "Burke Butts Calhoun Camden Candler Carroll Catoosa Charlton Chatham Chattahoochee Chattooga Cherokee Clarke Clay "
    "Clayton Clinch Cobb Coffee Colquitt Columbia Cook Coweta Crawford Crisp Dade Dawson DeKalb Decatur Dodge Dooly "
    "Dougherty Douglas Early Echols Effingham Elbert Emanuel Evans Fannin Fayette Floyd Forsyth Franklin Fulton Gilmer "
    "Glascock Glynn Gordon Grady Greene Gwinnett Habersham Hall Hancock Haralson Harris Hart Heard Henry Houston Irwin "
    "Jackson Jasper Jefferson Jenkins Johnson Jones Lamar Lanier Laurens Lee Liberty Lincoln Long Lowndes Lumpkin Macon "
    "Madison Marion McDuffie McIntosh Meriwether Miller Mitchell Monroe Montgomery Morgan Murray Muscogee Newton Oconee "
    "Oglethorpe Paulding Peach Pickens Pierce Pike Polk Pulaski Putnam Quitman Rabun Randolph Richmond Rockdale Schley "
    "Screven Seminole Spalding Stephens Stewart Sumter Talbot Taliaferro Tattnall Taylor Telfair Terrell Thomas Tift "
    "Toombs Towns Treutlen Troup Turner Twiggs Union Upson Walker Walton Ware Warren Washington Wayne Webster Wheeler "
    "White Whitfield Wilcox Wilkes Wilkinson Worth").split() + ["Ben Hill", "Jeff Davis"]}
COUNTIES["DOOLEY"] = "Dooly"  # (as some names spell it)
CITIES = {c.upper(): c for c in ("Atlanta", "Savannah", "Dunwoody", "Alpharetta", "Smyrna", "Brookhaven", "Marietta",
                                 "Chamblee", "Roswell", "Pooler")}


def _place(location):
    """The county and city a camera's name ends with, in brackets."""
    m = re.search(r"\(([^()]+)\)\s*$", location or "")
    label = m.group(1).strip().upper() if m else ""
    if not label and (location or "").startswith("GWIN-"):  # (Gwinnett DOT's cameras carry no bracketed place)
        label = "GWINNETT"
    return COUNTIES.get(label), CITIES.get(label)


def _page(get, start):
    query = json.dumps({"columns": [], "order": [], "start": start, "length": 100, "search": {"value": ""}})
    url = f"{BASE}/List/GetData/Cameras?query={quote(query)}&lang=en-US"
    for attempt in range(4):
        try:
            return json.loads(get(url))
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 + 2 * attempt)


def _point(site):
    wkt = (((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or "")
    try:
        lon, lat = (float(v) for v in wkt[wkt.index("(") + 1:wkt.index(")")].split())
    except ValueError:
        return None, None
    return lat, -lon if lon > 0 else lon  # a few are listed with the longitude's sign dropped

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    seen, start, total = set(), 0, None
    while total is None or start < total:
        page = _page(get, start)
        total, rows = page.get("recordsTotal") or 0, page.get("data") or []
        if not rows:
            break
        start += len(rows)
        for site in rows:
            lat, lon = _point(site)
            images = site.get("images") or []
            location = site.get("location") or ""
            county, city = _place(location)
            bound = site.get("direction")
            for image in images:
                if image.get("id") in seen or not image.get("imageUrl"):
                    continue
                seen.add(image.get("id"))
                name = location or image.get("description") or "Camera"
                if len(images) > 1 and image.get("description"):
                    name = f"{name} ({image['description']})"
                video = None if image.get("videoDisabled") else image.get("videoUrl") or None
                cam = {
                    "id": str(image["id"]),
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "image": BASE + image["imageUrl"],
                    "video": video,
                    "video_type": "hls" if video else None,
                    "road": site.get("roadway"),
                    "approach": None if bound in (None, "", "Unknown") else bound,
                    "county": site.get("county") or county,
                    "city": site.get("city") or city,
                    "extra": {"name": (site.get("jsonData") or {}).get("name"), "site": site.get("id")},
                }
                if image.get("disabled") or image.get("blocked"):
                    cam["online"] = False
                yield cam


def resolve(get, camera, key=None):
    """The camera's video URL signed for the next 2 minutes, asked for the way the 511GA map asks."""
    video = camera.get("video")
    if video:
        signed = json.loads(get(f"{BASE}/Camera/GetVideoUrl?imageId={camera['id']}"))
        if isinstance(signed, str) and signed.startswith("http"):
            video = signed
    return {"image": camera.get("image"), "video": video}
