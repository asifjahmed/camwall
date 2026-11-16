"""Utah: UDOT's cameras from UDOT Traffic (udottraffic.utah.gov, Arcadis IBI's 511 platform): the freeway and highway
cameras statewide, the RWIS road-weather cameras, and the signal cameras at intersections UDOT and the cities run
(Salt Lake City, St. George, Provo and the rest feed theirs in). The list is the one the site's own camera list page
loads (/List/GetData/Cameras, paged 100 at a time); the documented API (/api/v2/get/cameras) needs a key from a
sign-up. Stills only (UDOT shows no video): mostly JPEG (some GIF and PNG), 352x240 up to 1280x720.

Each location name ends in UDOT's place code: a three-letter city code (SLC, WVC, PVO, STG, ...) or, outside a city, a
two-letter county code (SL, UT, SU, ...). The tables below turn the code into city and county; they were built from the
City and County columns of UDOT's own ITS device inventory (UPlan `ITS_Existing_Devices`, 1,940 CCTV rows), with the
codes it lacks (or labels oddly) filled in from where their cameras are. The list's direction ("Northbound", ...) is
the way the road's traffic goes (it matches the NB/SB in the names), so it is given as approach."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "UDOT (UDOT Traffic)",
    "state": "UT",
    "covers": "Utah's interstates, state highways, RWIS stations and signalized intersections (UDOT's and the "
              "cities'), statewide",
    "site": "https://www.udottraffic.utah.gov/",
    "terms": "https://www.udottraffic.utah.gov/about/disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented list the site's camera list page loads; the documented API needs a key from an account "
             "(https://www.udottraffic.utah.gov/developers/doc, 10 calls a minute). Pictures are stills, mostly JPEG "
             "(some GIF and PNG), 352x240 up to 1280x720, served with max-age 60. The list flags no camera as out of "
             "service. City and county come from the place code that ends each name (SLC, WVC, SL, ...); the list's "
             "own city and county fields are empty. The list's direction is the traffic's (Northbound, ...), given "
             "as approach. Its robots.txt asks crawlers to leave this path alone: camwall fetches it once a day for "
             "someone using the app, as the site's own camera list does for each visitor, and the weekly source check "
             "(a crawler) skips it. The documented route is the keyed developer API "
             "(https://udottraffic.utah.gov/developers/doc).",
}
BASE = "https://www.udottraffic.utah.gov"
PAGE = 100

# UDOT's place codes (the end of each location name), from UDOT's ITS device inventory.
COUNTY_CODES = {
    "BE": "Box Elder", "BV": "Beaver", "CA": "Cache", "CC": "Carbon", "DA": "Davis", "DG": "Daggett",
    "DU": "Duchesne", "EM": "Emery", "GA": "Garfield", "GR": "Grand", "JU": "Juab", "KN": "Kane", "MD": "Millard",
    "MN": "Morgan", "PT": "Piute", "RI": "Rich", "RN": "Iron", "SE": "Sevier", "SJ": "San Juan", "SL": "Salt Lake",
    "SP": "Sanpete", "SU": "Summit", "TE": "Tooele", "UN": "Uintah", "UT": "Utah", "WA": "Wasatch", "WB": "Weber",
    "WE": "Wayne", "WN": "Washington",
}
CITY_CODES = {  # code: (city, county)
    "AFK": ("American Fork", "Utah"), "ALT": ("Alta", "Salt Lake"), "APV": ("Apple Valley", "Washington"),
    "BAL": ("Ballard", "Uintah"), "BCC": ("Bryce Canyon City", "Garfield"), "BHD": ("Brian Head", "Iron"),
    "BLA": ("Blanding", "San Juan"), "BLF": ("Bluffdale", "Salt Lake"), "BRC": ("Brigham City", "Box Elder"),
    "BTF": ("Bountiful", "Davis"), "BTN": ("Brighton", "Salt Lake"), "BVR": ("Beaver", "Beaver"),
    "CDC": ("Cedar City", "Iron"), "CDF": ("Cedar Fort", "Utah"), "CFD": ("Clearfield", "Davis"),
    "CHR": ("Charleston", "Wasatch"), "CLV": ("Coalville", "Summit"), "CTN": ("Clinton", "Davis"),
    "CVL": ("Centerville", "Davis"), "CWH": ("Cottonwood Heights", "Salt Lake"), "DCH": ("Duchesne", "Duchesne"),
    "DLT": ("Delta", "Millard"), "DPR": ("Draper", "Salt Lake"), "DUG": ("Dugway", "Tooele"),
    "EAG": ("Eagle Mountain", "Utah"), "ELK": ("Elk Ridge", "Utah"), "ELW": ("Elwood", "Box Elder"),
    "ENO": ("Enoch", "Iron"), "EPH": ("Ephraim", "Sanpete"), "ERD": ("Erda", "Tooele"), "EUR": ("Eureka", "Utah"),
    "FRF": ("Fairfield", "Utah"), "FRM": ("Farmington", "Davis"), "FRU": ("Fruit Heights", "Davis"),
    "FRW": ("Farr West", "Weber"), "FTD": ("Fort Duchesne", "Uintah"), "GNT": ("Granite", "Salt Lake"),
    "GRC": ("Garden City", "Rich"), "GRR": ("Green River", "Emery"), "GVL": ("Grantsville", "Tooele"),
    "HBR": ("Heber City", "Wasatch"), "HDY": ("Holladay", "Salt Lake"), "HKV": ("Hanksville", "Wayne"),
    "HLD": ("Highland", "Utah"), "HLP": ("Helper", "Carbon"), "HRC": ("Hurricane", "Washington"),
    "HRR": ("Herriman", "Salt Lake"), "HRV": ("Harrisville", "Weber"), "HTN": ("Huntington", "Emery"),
    "HWL": ("Howell", "Box Elder"), "HYD": ("Hyde Park", "Cache"), "HYR": ("Hyrum", "Cache"),
    "HYV": ("Honeyville", "Box Elder"), "KAY": ("Kaysville", "Davis"), "KMS": ("Kamas", "Summit"),
    "KNB": ("Kanab", "Kane"), "KRN": ("Kearns", "Salt Lake"), "LDL": ("Lynndyl", "Millard"),
    "LDN": ("Lindon", "Utah"), "LED": ("Leeds", "Washington"), "LEW": ("Lewiston", "Cache"),
    "LGN": ("Logan", "Cache"), "LHI": ("Lehi", "Utah"), "LKP": ("Lakepoint", "Tooele"), "LTN": ("Layton", "Davis"),
    "LVR": ("La Verkin", "Washington"), "MAB": ("Moab", "Grand"), "MAE": ("Maeser", "Uintah"),
    "MAG": ("Magna", "Salt Lake"), "MCK": ("Millcreek", "Salt Lake"), "MDV": ("Midvale", "Salt Lake"),
    "MGN": ("Morgan", "Morgan"), "MNA": ("Mona", "Juab"), "MNC": ("Monticello", "San Juan"),
    "MPL": ("Mapleton", "Utah"), "MSV": ("Marriott-Slaterville", "Weber"), "MTI": ("Manti", "Sanpete"),
    "MTP": ("Mt. Pleasant", "Sanpete"), "MTU": ("Mantua", "Box Elder"), "MUR": ("Murray", "Salt Lake"),
    "MWY": ("Midway", "Wasatch"), "MYT": ("Myton", "Duchesne"), "NIB": ("Nibley", "Cache"),
    "NLG": ("North Logan", "Cache"), "NOG": ("North Ogden", "Weber"), "NPH": ("Nephi", "Juab"),
    "NPL": ("Naples", "Uintah"), "NSL": ("North Salt Lake", "Davis"), "OGD": ("Ogden", "Weber"),
    "ORM": ("Orem", "Utah"), "PDS": ("Paradise", "Cache"), "PKC": ("Park City", "Summit"),
    "PLG": ("Pleasant Grove", "Utah"), "PLV": ("Pleasant View", "Weber"), "PRC": ("Price", "Carbon"),
    "PRY": ("Perry", "Box Elder"), "PSN": ("Payson", "Utah"), "PVD": ("Providence", "Cache"),
    "PVO": ("Provo", "Utah"), "RDL": ("Riverdale", "Weber"), "RFD": ("Richfield", "Sevier"),
    "RMD": ("Richmond", "Cache"), "ROY": ("Roy", "Weber"), "RSV": ("Roosevelt", "Duchesne"),
    "RVT": ("Riverton", "Salt Lake"), "SCL": ("Santa Clara", "Washington"), "SDL": ("Springdale", "Washington"),
    "SIG": ("Sigurd", "Sevier"), "SJO": ("South Jordan", "Salt Lake"), "SLA": ("Salina", "Sevier"),
    "SLC": ("Salt Lake City", "Salt Lake"), "SLM": ("Salem", "Utah"), "SMF": ("Smithfield", "Cache"),
    "SND": ("Sandy", "Salt Lake"), "SOG": ("South Ogden", "Weber"), "SPF": ("Spanish Fork", "Utah"),
    "SPV": ("Springville", "Utah"), "SSL": ("South Salt Lake", "Salt Lake"), "SSP": ("Saratoga Springs", "Utah"),
    "STG": ("St. George", "Washington"), "STP": ("Stansbury Park", "Tooele"), "STQ": ("Santaquin", "Utah"),
    "SUN": ("Sunset", "Davis"), "SWE": ("South Weber", "Davis"), "SYR": ("Syracuse", "Davis"),
    "TAY": ("Taylorsville", "Salt Lake"), "TLE": ("Tooele", "Tooele"), "TNT": ("Trenton", "Cache"),
    "TOQ": ("Toquerville", "Washington"), "TRE": ("Tremonton", "Box Elder"), "UIN": ("Uintah", "Weber"),
    "VIN": ("Vineyard", "Utah"), "VNL": ("Vernal", "Uintah"), "WAS": ("Washington", "Washington"),
    "WBN": ("West Bountiful", "Davis"), "WEN": ("Wendover", "Tooele"), "WHV": ("West Haven", "Weber"),
    "WIL": ("Willard", "Box Elder"), "WJD": ("West Jordan", "Salt Lake"), "WPT": ("West Point", "Davis"),
    "WTN": ("Wellington", "Carbon"), "WVC": ("West Valley City", "Salt Lake"), "WVL": ("Wellsville", "Cache"),
    "WXS": ("Woods Cross", "Davis"),
}


def _sites(get):
    start, seen = 0, set()
    while True:
        query = {"columns": [{"name": "id", "s": True}], "order": [{"column": 0, "dir": "asc"}],
                 "start": start, "length": PAGE, "search": {"value": ""}}
        data = json.loads(get(f"{BASE}/List/GetData/Cameras?query={quote(json.dumps(query))}&lang=en"))
        rows = data.get("data") or []
        for row in rows:
            if row.get("id") not in seen:
                seen.add(row.get("id"))
                yield row
        start += PAGE
        if not rows or start >= (data.get("recordsTotal") or 0):
            return


def _point(site):
    wkt = ((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or ""
    m = re.match(r"POINT \(([-\d.]+) ([-\d.]+)\)", wkt)
    return (float(m.group(2)), float(m.group(1))) if m else (None, None)


def _clean(text):
    text = (text or "").strip()
    return "" if text in ("N/A", "Unknown") else re.sub(r"\s+", " ", text)


def _place(name):
    """(city, county) from the place code that ends a location name ("..., SLC", "..., SL", "... MP 1 SLC (Tunnel)")."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name or "")
    m = re.search(r"(,\s*|\s)([A-Z]{2,3})$", name)
    if not m:
        return None, None
    code, comma = m.group(2), m.group(1).startswith(",")
    if code in CITY_CODES:
        return CITY_CODES[code]
    if comma and code in COUNTY_CODES:  # (a bare two-letter word could be a bound, "... WB")
        return None, COUNTY_CODES[code]
    return None, None

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    for site in _sites(get):
        lat, lon = _point(site)
        images = site.get("images") or []
        base = _clean(site.get("location")) or _clean(site.get("roadway")) or "Camera"
        city, county = _place(base)
        for n, image in enumerate(images, 1):
            name = _clean(image.get("description")) or base
            if len(images) > 1 and name == base:
                name = f"{base} (view {n})"
            camera = {
                "id": str(image["id"]),
                "name": name,
                "lat": lat,
                "lon": lon,
                "image": BASE + image["imageUrl"],
                "refresh": 60,
                "extra": {"site": site.get("id"), "source_id": site.get("sourceId")},
            }
            if image.get("disabled") or image.get("blocked"):
                camera["online"] = False
            if _clean(site.get("roadway")):
                camera["road"] = site["roadway"]
            if _clean(site.get("direction")):
                camera["approach"] = site["direction"]
            if site.get("city") or city:
                camera["city"] = site.get("city") or city
            if site.get("county") or county:
                camera["county"] = site.get("county") or county
            yield camera
