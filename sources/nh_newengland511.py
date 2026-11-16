"""Maine, New Hampshire and Vermont: the three states' cameras on New England 511 (IBI's 511 platform), from the camera
list its Cameras page pages through (no key). That includes the Maine Turnpike Authority's cameras (named "... MTA")
and NHDOT's turnpike ones. Stills only, served by New England 511 at /map/Cctv/<id> and refreshed about every 10 s.

The 511 list calls every camera in service, including dead ones whose picture is a "No live camera feed at this time"
card. The three states' documented, keyless feed (the New England Compass developer portal) gives each camera's real
status, so a camera Compass lists as "Device Offline" is given online False (matched by name, else by position).
Compass's own pictures come base64-encoded inside one XML file per state, not as picture URLs, so the pictures and the
list come from New England 511. Seven cameras the list gives twice (see DUPLICATES) are kept, ids unchanged, with the
second copy marked."""

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

SOURCE = {
    "name": "New England 511 (MaineDOT, NHDOT, VTrans)",
    "state": ["ME", "NH", "VT"],
    "covers": "Maine, New Hampshire and Vermont state highways and interstates, the Maine Turnpike and NH turnpikes",
    "site": "https://newengland511.org/cctv",
    "terms": "https://newengland511.org/terms",
    "key": None,
    "headers": {},
    "restricted": None,
    "credit": "Tri-State: MaineDOT, NHDOT and VTrans",
    "notes": "Undocumented: the list newengland511.org's Cameras page loads (/List/GetData/Cameras). Its terms "
             "(one PDF per state at newengland511.org/terms, the same text for all three) are disclaimers only: no "
             "limit on apps, automated access or redistribution. In-service status comes from the states' documented "
             "feed, https://nec-por.ne-compass.com/DeveloperPortal (cctvStatusData; no key), whose terms grant rights "
             "\"to use, reproduce, and redistribute the Data\" if you \"Clearly acknowledge Tri-State as the "
             "provider\" (credit MaineDOT, NHDOT and VTrans). Compass also lists cameras the 511 site leaves out "
             "(about 30 online in Maine, 1 in New Hampshire), but their pictures exist only as base64 inside each "
             "state's whole snapshot XML (6.6 MB for New Hampshire), so they aren't included. Seven cameras are listed "
             "twice, once under each state's network (the Maine Turnpike's six Kittery cameras, and NHDOT's I-95 "
             "mile 13.4 camera); the second copy has extra.duplicate_of, so 356 of the 363 are distinct.",
}
# Cameras the list gives twice, once from each state's network: the Maine Turnpike Authority's six Kittery cameras
# (also listed, with "MTA" names, under New Hampshire) and NHDOT's I-95 mile 13.4 camera in Portsmouth (also listed
# under Maine). Matched by their pictures (the same frame and caption) on 2026-11-08. The second copy keeps its id, but
# gets the state it's really in and extra.duplicate_of naming the first.
DUPLICATES = {"1264": ("2212", "ME"), "1261": ("759", "ME"), "1270": ("2189", "ME"), "1260": ("2210", "ME"),
              "1269": ("2188", "ME"), "1271": ("2190", "ME"), "2191": ("1382", "NH")}
BASE = "https://newengland511.org"
COMPASS = "https://nec-por.ne-compass.com/NEC.XmlDataPortal/api/c2c?networks={}&dataTypes=cctvStatusData"
C2C = "{http://its.gov/c2c_icd}"
PAGE = 100
STATES = {"Maine": "ME", "New Hampshire": "NH", "NewHampshire": "NH", "Vermont": "VT"}
NETWORKS = {"ME": "Maine", "NH": "NewHampshire", "VT": "Vermont"}


def _query(start):
    return quote(json.dumps({
        "columns": [{"data": None, "name": ""}, {"name": "sortOrder", "s": True}, {"name": "roadway", "s": True}],
        "order": [{"column": 1, "dir": "asc"}, {"column": 2, "dir": "asc"}],
        "start": start, "length": PAGE, "search": {"value": ""}}))


def _norm(name):
    """A camera name as both lists can be matched on: the 511 list and Compass mangle some characters differently."""
    return re.sub(r"[^A-Za-z0-9]", "", name or "").upper()


def _compass_status(get):
    """{state: ({name: [statuses]}, {(lat, lon): [statuses]})} from Compass; a state is left out if its feed fails."""
    out = {}
    for state, network in NETWORKS.items():
        try:
            root = ET.fromstring(get(COMPASS.format(network)))
        except (OSError, ET.ParseError):
            continue
        names, points = {}, {}
        for cam in root.iter(C2C + "cctvStatus"):
            status = cam.findtext(C2C + "status") or ""
            names.setdefault(_norm(cam.findtext(C2C + "name")), []).append(status)
            try:
                point = (round(int(cam.findtext(C2C + "lat")) / 1e6, 4), round(int(cam.findtext(C2C + "lon")) / 1e6, 4))
            except (TypeError, ValueError):
                continue
            points.setdefault(point, []).append(status)
        out[state] = (names, points)
    return out


def _offline(status, state, name, lat, lon):
    """True if Compass lists exactly one camera with this name (or, failing that, at this spot) and it's offline."""
    if state not in status:
        return False
    names, points = status[state]
    found = names.get(_norm(name)) or points.get((round(lat, 4), round(lon, 4))) or []
    return len(found) == 1 and found[0] == "Device Offline"

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    status = _compass_status(get)
    start, total = 0, None
    while total is None or start < total:
        page = json.loads(get(f"{BASE}/List/GetData/Cameras?query={_query(start)}&lang=en-US"))
        total = page.get("recordsTotal") or 0
        rows = page.get("data") or []
        if not rows:
            break
        start += PAGE
        for site in rows:
            state = STATES.get(site.get("state")) or STATES.get(site.get("source"))
            wkt = ((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or ""
            point = re.match(r"POINT \((-?[\d.]+) (-?[\d.]+)\)", wkt)
            if not state or not point or not float(point.group(1)) or not float(point.group(2)):
                continue
            lat, lon = float(point.group(2)), float(point.group(1))
            offline = _offline(status, state, site.get("location"), lat, lon)
            views = site.get("images") or []
            for view in views:
                if not view.get("imageUrl"):
                    continue
                name = (site.get("location") or site.get("roadway") or "Camera").strip()
                if len(views) > 1 and view.get("description"):
                    name = f"{name} ({view['description']})"
                same_as, where = DUPLICATES.get(str(view["id"]), (None, state))
                yield {
                    "id": str(view["id"]),
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "image": BASE + view["imageUrl"],
                    "state": where,
                    "road": site.get("roadway"),
                    "city": site.get("city"),
                    "county": site.get("county"),
                    "refresh": (view.get("refreshRateMs") or 10000) / 1000,
                    "online": bool(site.get("visible", True)) and not view.get("blocked") and not view.get("disabled")
                              and not offline,
                    "extra": {k: v for k, v in {"site_id": site.get("id"), "traffic_direction": site.get("direction"),
                                                "owner": "Maine Turnpike Authority" if name.endswith("MTA") else None,
                                                "compass_status": "Device Offline" if offline else None,
                                                "duplicate_of": same_as,
                                                "listed_state": state if where != state else None,
                                                }.items() if v},
                }
