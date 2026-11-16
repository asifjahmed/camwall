"""Michigan: MDOT's cameras, from the lists its Mi Drive camera-list page and map load (no key). The camera list gives
each camera's picture, route, county and (in its "Go to" map link) place; the map's list adds the title it shows, and
is used when it answers. Pictures are JPEG stills served by micamerasimages.net (a few RWIS road-weather cameras come
from MDOT's own server)."""

import html
import json
import re

SOURCE = {
    "name": "MDOT (Mi Drive)",
    "state": "MI",
    "covers": "Michigan's freeways and state trunklines: Metro Detroit (SEMTOC), Grand Rapids, the statewide TOC "
              "(STOC), rural and Upper Peninsula sites and a few RWIS road-weather cameras",
    "site": "https://mdotjboss.state.mi.us/MiDrive/map",
    "terms": "https://www.michigan.gov/mdot/about/mi-drive-disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the JSON Mi Drive's own camera list (/MiDrive/camera/list) and map "
             "(/MiDrive/camera/AllForMap) load. The list alone is enough (its 'Go to' map link carries each camera's "
             "place); the map's list, which a community scraper reports was gone for a while in autumn 2026, only adds "
             "titles and places when it answers. Stills only, no video. The /thumbs/ pictures (Detroit, Grand Rapids, "
             "the statewide TOC) are grabbed live from the video and change every few seconds (the URL redirects to "
             "the snapshot service's 320x240 picture); the rural 'bucket=ftp' ones (800x450) are uploaded every few "
             "minutes and the RWIS ones about hourly. MDOT removes a camera from the site when it expects it to be out "
             "for more than a day, so there is no out-of-service flag. The source's 'direction' text says which way "
             "the nearest traffic travels, not which way the camera faces, so it becomes approach (Northbound...), "
             "with the full text in extra. A few cameras are listed twice (two map points, one picture: 806 entries, "
             "791 distinct pictures on 8 Nov 2026); both entries are kept and each names the other in "
             "extra.same_picture_as. The rural road-weather (ESS) cameras each cycle through 7-8 presets, all served "
             "by the same snapshot service with the last number changed (-00-00 ... -00-07); Mi Drive shows one of "
             "them, and so does this list.",
}
BASE = "https://mdotjboss.state.mi.us"
MAP = BASE + "/MiDrive/camera/AllForMap"
LIST = BASE + "/MiDrive/camera/list"


def _text(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split("Go to")[0].strip()


def cameras(get, key=None):
    found = list(_cameras(get))
    by_picture = {}
    for cam in found:
        by_picture.setdefault(cam["image"].split("?")[0], []).append(cam["id"])
    for cam in found:
        twins = [i for i in by_picture[cam["image"].split("?")[0]] if i != cam["id"]]
        if twins:
            cam["extra"]["same_picture_as"] = twins
        yield cam


def _cameras(get):
    try:  # the map's list: each camera's place and title (it was missing for a while in 2026, so it's optional)
        sites = {str(site.get("id")): site for site in json.loads(get(MAP))}
    except (OSError, ValueError):
        sites = {}
    for row in json.loads(get(LIST)):
        cam_id = (re.search(r'id="(\d+)Img"', row.get("image") or "")
                  or re.search(r"[?&]id=(\d+)", row.get("county") or ""))
        src = re.search(r'src="([^"]+)"', row.get("image") or "")
        if not cam_id or not src:
            continue
        cam_id = cam_id.group(1)
        site = sites.get(cam_id, {})
        lat, lon = site.get("latitude"), site.get("longitude")
        if lat is None or lon is None:  # the list's own "Go to" map link carries the place too
            place = re.search(r"lat=(-?[\d.]+)&(?:amp;)?lon=(-?[\d.]+)", row.get("county") or "")
            if not place:
                continue
            lat, lon = float(place.group(1)), float(place.group(2))
        image = html.unescape(src.group(1))
        if not image.startswith("http"):
            image = "https://" + image.lstrip("/")
        county = _text(row.get("county")).removesuffix(" County").strip() or None
        traffic = (row.get("direction") or "").strip()  # "Traffic closest to camera is traveling north."
        bound = re.search(r"traveling (north|south|east|west)", traffic, re.I)
        yield {
            "id": cam_id,
            "name": (site.get("title") or "").strip() or f"{row.get('route', '')}{row.get('location', '')}".strip(),
            "lat": lat,
            "lon": lon,
            "image": image,
            "road": (row.get("route") or "").strip() or None,
            "county": county,
            "approach": f"{bound.group(1).capitalize()}bound" if bound else None,
            "refresh": 15 if "/thumbs/" in image else 3600 if "/rwis/" in image else 300,
            "extra": {"traffic": traffic} if traffic else {},
        }
