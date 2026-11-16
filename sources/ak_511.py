"""Alaska: DOT&PF's cameras on Alaska 511 (an Arcadis IBI site), from the keyless list its camera table loads
(/List/GetData/Cameras, DataTables-style, paged with start/length). It includes the road-weather (RWIS) sites, most of
which have several views, and the traffic cameras around Anchorage, the Mat-Su and Fairbanks. A camera site can have
several pictures (/map/Cctv/<id>); each picture is a camera here, known by its image id.

DOT&PF's road-weather site (roadweather.alaska.gov) shows the same camera sites with every view named, and some views
511 leaves out (University Avenue in Fairbanks shows 1 of its 8 on 511, Thane Road 1 of 3). 511 shows a site's views
in the road-weather site's view order, stopping short at some sites, so a 511 picture takes the name of the road-weather
view in its place, and the views past 511's last are added from the road-weather site (ids "rw<site>-<view>"). Their
pictures are timestamped files, so resolve() looks up the latest one."""

import calendar
import json
import re
import time
from urllib.parse import quote

SOURCE = {
    "name": "Alaska DOT&PF (Alaska 511)",
    "state": "AK",
    "covers": "Alaska's highways: RWIS road-weather cameras statewide and traffic cameras in Anchorage, the Mat-Su, "
              "Kenai, Juneau and Fairbanks",
    "site": "https://511.alaska.gov/cctv",
    "terms": "https://dot.alaska.gov/copyright.shtml",
    "key": None,
    "headers": {},
    "restricted": "DOT&PF's copyright notice (linked from 511.alaska.gov/about/disclaimer): 'any unauthorized copying, "
                  "downloading, republication, or other use of the above-referenced material, without the prior written "
                  "authorization of DOT&PF, is strictly prohibited' (images included).",
    "notes": "Undocumented: the list behind 511's camera table. The documented API (511.alaska.gov/developers/doc, "
             "/api/v2/get/cameras) needs a free key. JPEG stills; the site gives a 30 s refresh for most of them "
             "(RWIS views change less often). The source's 'direction' is the direction of travel, kept in "
             "extra['travel']. View names, and the RWIS views 511 leaves out (ids 'rw<site>-<view>'), come from "
             "DOT&PF's road-weather site (roadweather.alaska.gov/api/sites and /api/cameras/<site>, undocumented, "
             "keyless); those pictures are timestamped JPEGs on Azure blob storage (served as "
             "application/octet-stream), new about every 8-9 minutes, found by resolve(). An RWIS view the "
             "road-weather site has had no picture from for 24 hours is listed out of service (511 shows a 14 KB "
             "PNG placeholder for it).",
}
BASE = "https://511.alaska.gov"
RW = "https://roadweather.alaska.gov"
PAGE = 100
POINT = re.compile(r"POINT \(([-\d.]+) ([-\d.]+)\)")
TAG = re.compile(r"#(\d+)\b")  # DOT&PF's site number, in both sites' names: "... @ Birch Lake (#22)", "#68 Mt. Roberts ..."
RW_ID = re.compile(r"rw(\d+)-(\d+)")
STALE = 24 * 3600  # s: a road-weather view whose latest picture is older than this is out of service

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    rows, start = [], 0
    while True:
        query = quote(json.dumps({"columns": [], "start": start, "length": PAGE}, separators=(",", ":")))
        page = json.loads(get(f"{BASE}/List/GetData/Cameras?query={query}&lang=en"))
        rows += page.get("data") or []
        start += len(page.get("data") or [])
        if not page.get("data") or start >= (page.get("recordsTotal") or 0):
            break
    views = road_weather_views(get, rows)
    for row in rows:
        match = POINT.search(((row.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or "")
        if not match:
            continue
        lon, lat = float(match[1]), float(match[2])
        images = [i for i in row.get("images") or [] if i.get("imageUrl")]
        site = " ".join((row.get("location") or "").split()) or row.get("roadway") or f"Camera {row.get('id')}"
        rw_site, rw_views = views.get(row.get("id"), (None, []))
        several = max(len(images), len(rw_views)) > 1
        common = {
            "lat": lat,
            "lon": lon,
            "road": row.get("roadway") or None,
            "city": row.get("city") or None,
            "county": row.get("county") or None,
        }
        extra = {k: v for k, v in {"site": row.get("id"), "type": row.get("type"),
                                   "travel": (row.get("direction") or "").strip(), "area": row.get("area"),
                                   "source": row.get("source")}.items() if v}
        for n, image in enumerate(images, 1):
            view = rw_views[n - 1] if n <= len(rw_views) else None
            label = (image.get("description") or "").strip()
            if label.lower() in ("n/a", "test data"):
                label = ""
            label = label or (view["name"] if view else "") or f"view {n}"
            refresh = image.get("refreshRateMs")
            yield {
                "id": str(image["id"]),
                "name": f"{site} ({label})" if several else site,
                **common,
                "image": BASE + image["imageUrl"],
                "refresh": refresh / 1000 if refresh else None,
                # (511 shows a placeholder for a view the road-weather site has had no picture from for a day)
                "online": not (image.get("disabled") or image.get("blocked") or (view and view["age"] >= STALE)),
                "extra": dict(extra),
            }
        for view in rw_views[len(images):]:  # (the views 511 leaves out)
            if not view["image"]:
                continue
            yield {
                "id": f"rw{rw_site}-{view['number']}",
                "name": f"{site} ({view['name']})",
                **common,
                "image": view["image"],
                "online": view["age"] < STALE,
                "extra": {**extra, "rwis_site": rw_site, "view": view["number"], "from": "roadweather.alaska.gov"},
            }


def road_weather_views(get, rows):
    """The road-weather site's views for the 511 camera sites it also shows: {511 site id: (its road-weather site id,
    [{"number", "name", "image", "age"}, ...] in view order)}. Empty if the road-weather site doesn't answer."""
    try:
        sites = json.loads(get(f"{RW}/api/sites"))
    except (OSError, ValueError):
        return {}
    by_tag = {}
    for s in sites:
        tag = TAG.search(s.get("description") or "")
        if tag and s.get("isDotCamera") and not s.get("isDecommissioned"):
            by_tag[tag[1]] = s["siteId"]
    found, asked = {}, False
    for row in rows:
        tag = TAG.search(row.get("location") or "")
        rw_site = by_tag.get(tag[1]) if tag else None
        if rw_site is None:
            continue
        if asked:
            time.sleep(0.75)  # (about one request a second)
        asked = True
        try:
            latest = json.loads(get(f"{RW}/api/cameras/{rw_site}")).get("latestImages") or {}
        except (OSError, ValueError):
            continue
        views = []
        for view in sorted(latest.values(), key=lambda v: v.get("viewNumber", 0)):
            image = view.get("latestImage") or {}
            views.append({"number": view.get("viewNumber"), "name": " ".join((view.get("viewName") or "").split()),
                          "image": image.get("downloadUrl"), "age": age(image.get("dateTime"))})
        found[row.get("id")] = (rw_site, views)
    return found


def age(stamp):
    """How old a road-weather picture is, in seconds, from its UTC stamp ("20261108171500")."""
    try:
        return time.time() - calendar.timegm(time.strptime(stamp, "%Y%m%d%H%M%S"))
    except (TypeError, ValueError):
        return float("inf")


def resolve(get, camera, key=None):
    match = RW_ID.fullmatch(str(camera.get("id")))
    if not match:
        return {}  # (511's own pictures keep their URLs)
    latest = json.loads(get(f"{RW}/api/cameras/{match[1]}")).get("latestImages") or {}
    for view in latest.values():
        if str(view.get("viewNumber")) == match[2] and (view.get("latestImage") or {}).get("downloadUrl"):
            return {"image": view["latestImage"]["downloadUrl"]}
    return {}
