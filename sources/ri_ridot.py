"""Rhode Island: RIDOT's cameras, from the ArcGIS camera layer its traffic camera map draws (RIDOT's Rhodeways map
service on RISE GIS), the stream list the map loads beside it, and RIDOT's six regional camera pages (no key).

Every camera has a still on dot.ri.gov that changes every minute or so. Most also have HLS video on Wowza's CDN, but
it answers only RIDOT's own map (its Referer), so it isn't listed.

The layer and the stream list lag behind the regional pages, which are what RIDOT keeps current: for some cameras the
layer's picture is a file RIDOT stopped updating (or deleted), and the stream list has no stream, a dead one, or one
filed under the wrong camera. So a camera the regional pages show takes its picture from there, matched by the
picture's file name, or else by its stream."""

import html
import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "RIDOT",
    "state": "RI",
    "covers": "Rhode Island's interstates and state highways",
    "site": "https://www.dot.ri.gov/travel/traffic_camera_map/",
    "terms": "https://www.ri.gov/policies/copyright/",
    "key": None,
    "headers": {},
    "restricted": None,
    "credit": "RIDOT",
    "notes": "The camera layer is a public ArcGIS MapServer layer (risegis.ri.gov .../RIDOT/Rhodeways/MapServer/6); the "
             "stream list (cameras.php) and the regional camera pages' stream links are undocumented. "
             "ri.gov: the information \"is considered public information and may be distributed or copied. However, "
             "use of appropriate byline/photo/image credits is requested\" (credit RIDOT).",
}
LAYER = ("https://risegis.ri.gov/hosting/rest/services/RIDOT/Rhodeways/MapServer/6/query"
         "?where=1%3D1&outFields=*&outSR=4326&f=json")
STREAMS = "https://www.dot.ri.gov/travel/traffic_camera_map/cameras.php"
PAGES = [f"https://www.dot.ri.gov/travel/cameras_{region}.php"
         for region in ("metro", "eastbay", "ncounty", "bstonenorth", "scounty", "westbay")]
PICTURES = "https://www.dot.ri.gov/img/travel/camimages/"

ENTRY = re.compile(r'<li>\s*(<a[^>]*>)\s*<img src="[^"]*camimages/([^"]+)"(.*?)(?=<li>|</ul>)', re.S)
STREAM = re.compile(r"openSignedVideoPopup\('(/1/[^']+)'\)")


def _file(url):
    """A picture URL's file name ('95_26.0_S_CAM - Cowesett Rd.jpg')."""
    return (url or "").strip().rsplit("/camimages/", 1)[-1].strip()


def _pages(get):
    """(picture file, stream path or None) for each camera RIDOT's regional camera pages show."""
    for page in PAGES:
        try:
            text = get(page).decode("utf-8", "replace")
        except OSError:
            continue
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)  # (retired cameras are commented out)
        for link, picture, rest in ENTRY.findall(text):
            stream = STREAM.search(link) or STREAM.search(rest)
            yield html.unescape(picture).strip(), stream.group(1) if stream else None


def _is_picture(get, url):
    """False if RIDOT answers a picture's URL with something else (a missing file redirects to its home page)."""
    try:
        return get(url).startswith((b"\xff\xd8", b"\x89PNG", b"GIF8"))
    except OSError:
        return True  # (can't tell: keep it)


def cameras(get, key=None):
    streams = {}  # camera id -> its entries in the stream list, in order
    for s in json.loads(get(STREAMS)):
        if isinstance(s, dict):
            streams.setdefault(str(s.get("id")), []).append(s)
    by_path = {s["url"]: cid for cid, entries in streams.items() for s in entries if s.get("url")}
    layer = [(f.get("attributes") or {}, f.get("geometry") or {}) for f in json.loads(get(LAYER)).get("features") or []]
    by_file = {_file(cam.get("CCVEWebURL")): str(cam["EquipmentID"]) for cam, _ in layer
               if cam.get("EquipmentID") is not None and _file(cam.get("CCVEWebURL"))}

    shown = {}  # camera id -> (picture file, stream path) on the regional pages
    for picture, path in _pages(get):
        cid = by_file.get(picture) or by_path.get(path)
        if cid and cid not in shown:
            shown[cid] = (picture, path)
    claimed = {path: cid for cid, (_, path) in shown.items() if path}

    for cam, geometry in layer:
        lat, lon = geometry.get("y") or cam.get("Latitude"), geometry.get("x") or cam.get("Longitude")
        if cam.get("EquipmentID") is None or not lat or not lon:
            continue
        cid = str(cam["EquipmentID"])
        entries = streams.get(cid) or []
        picture, path = shown.get(cid) or (_file(cam.get("CCVEWebURL")), None)
        image = PICTURES + quote(picture, safe="()") if picture else None
        paths = [path] if path else []
        paths += [s["url"] for s in entries if s.get("url") and s["url"] not in paths
                  and claimed.get(s["url"], cid) == cid]  # (not a stream the pages show for another camera)
        if image and shown and cid not in shown and not _is_picture(get, image):
            image = None  # (a camera the pages leave out: its picture is checked, and may be gone)
        if not image:
            continue
        named = next((s for s in entries if s.get("url") in paths), entries[0] if entries else {})
        yield {
            "id": cid,
            "name": cam.get("Description") or named.get("name") or "Camera",
            "lat": float(lat),
            "lon": float(lon),
            "image": image,
            "video": None,
            "road": named.get("Roadway"),
            "refresh": 60,
            "online": cam.get("Enabled") != 0 and (not entries or any(s.get("state", "activated") == "activated"
                                                                      for s in entries)),
            "extra": {k: v for k, v in {"traffic_direction": cam.get("Direction"),
                                        "alias": named.get("alias")}.items() if v},
        }

