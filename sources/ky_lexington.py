"""Kentucky: Lexington-Fayette Urban County Government's traffic cameras, from the camera list its public map page
embeds (no key). Stills are thumbnails from the city's Wowza server; the HLS links carry a token good for 15 minutes,
so resolve() reads the page again for a fresh one."""

import re

SOURCE = {
    "name": "LFUCG Traffic Engineering (Lexington)",
    "state": "KY",
    "covers": "Lexington's (Fayette County) arterial and downtown intersections, New Circle Road and Nicholasville "
              "Road",
    "site": "https://trafficvid.lexingtonky.gov/publicmap/",
    "terms": "https://www.lexingtonky.gov/terms-use",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the camMarker array in the public map page's HTML. The same cameras (fewer, without "
             "video) are in LFUCG's ArcGIS layer Traffic_Camera_Locations_Public_view. Stills change every few "
             "seconds; a camera whose stream is down gives a PNG placeholder instead of a JPEG, and the list doesn't "
             "say which (about half were down at 2 am). HLS URLs are Wowza-tokenized for 15 minutes; resolve() "
             "fetches the page (about 260 KB) for a fresh one and asks the camera's status URL, returning nothing "
             "when it says Error.",
}
PAGE = "https://trafficvid.lexingtonky.gov/publicmap/"


def _cameras(page):
    for name, body in re.findall(r"\{\s*\"camera\":\s*'([^']*)'(.*?)\}", page, re.S):
        yield name, dict(re.findall(r"\"(\w+)\":\s*'([^']*)'", body))

EXPIRING = ("video",)  # (shipped lists keep none of these: tokenized stream links; resolve() looks up fresh ones)


def cameras(get, key=None):
    for name, c in _cameras(get(PAGE).decode("utf-8", "replace")):
        try:
            lat, lon = float(c.get("lat")), float(c.get("lng"))
        except (TypeError, ValueError):
            continue
        still = (c.get("still") or "").replace("&amp;", "&")
        hls = (c.get("hls") or "").replace("&amp;", "&")
        if not still and not hls:
            continue
        yield {
            "id": name.lower(),
            "name": c.get("description") or name,
            "lat": lat,
            "lon": lon,
            "image": still or None,
            "video": hls or None,
            "video_type": "hls" if hls else None,
            "city": "Lexington",
            "county": "Fayette",
            "refresh": 5,
            "online": c.get("override") != "On",
        }


def resolve(get, camera, key=None):
    """A fresh HLS token, or nothing when the camera's stream is down (its still would be a placeholder)."""
    for name, c in _cameras(get(PAGE).decode("utf-8", "replace")):
        if name.lower() == camera["id"]:
            status = c.get("status", "").replace("&amp;", "&")
            if status and get(status).decode(errors="replace").strip().lower() == "error":
                return {"image": None, "video": None}
            return {"image": (c.get("still") or "").replace("&amp;", "&") or camera.get("image"),
                    "video": (c.get("hls") or "").replace("&amp;", "&") or None}
    return {"image": None, "video": None}
