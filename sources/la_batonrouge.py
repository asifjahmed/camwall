"""Louisiana: the City of Baton Rouge-Parish of East Baton Rouge's traffic camera layer (EBRGIS, no key), which shows
LADOTD's Baton Rouge-area cameras by their older 511LA ids ("b24--1", "87.C2--1"), and whose pictures 511LA still
serves under those ids. The old id is the 511LA camera site's sourceId and view, so each camera is named, and matched
to its view in la_511la, from 511LA's own camera list. Nearly all are the same cameras as la_511la's."""

import json
import re
from urllib.parse import urlencode, urlparse

SOURCE = {
    "name": "City of Baton Rouge / East Baton Rouge Parish (EBRGIS)",
    "state": "LA",
    "covers": "Baton Rouge area interstates and arterials",
    "site": "https://ebrgis.maps.arcgis.com/apps/webappviewer/index.html?id=51b9452c63024a0d8ffd0b41989dc141",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "ArcGIS MapServer Transportation/Traffic_Camera (layer 0) on maps.brla.gov, used by the parish's "
             "\"Traffic Resources\" map, whose layer description calls them LADOTD traffic cameras. Pictures are "
             "511LA's /map/Cctv/<old id> JPEG stills (a 540x330 PNG placeholder when a camera is down). The old id "
             "is <511LA site sourceId>.C<view>--1 (or <sourceId>--1 for a one-view site): 114 of the 118 match a "
             "view on 511LA's list (same picture, checked byte for byte), and are named from it with that view's "
             "la_511la id in extra.same_as. The other four (297.C1, 297.C2, b31.C1, b31.C2) have no 511LA site "
             "and showed the placeholder in November 2026. If 511LA's list can't be read, cameras are named by id. "
             "The City-Parish's own 88 intersection PTZ cameras (layer PTZ_Cameras) are locations only.",
}
LIST = "https://www.511la.org/List/GetData/Cameras?"
LAYER = ("https://maps.brla.gov/gis/rest/services/Transportation/Traffic_Camera/MapServer/0/query?where=1%3D1"
         "&outFields=*&outSR=4326&orderByFields=ID&f=json&resultOffset=")


def _views(get):
    """511LA's views by old id: "<sourceId>.C<n>--1" (and "<sourceId>--1" for a site's first view) -> (name, id)."""
    views, start, total = {}, 0, None
    while total is None or start < total:
        query = {"columns": [{"data": None, "name": ""}], "order": [], "start": start, "length": 100,
                 "search": {"value": ""}}
        body = json.loads(get(LIST + urlencode({"query": json.dumps(query), "lang": "en-US"})))
        rows, total = body.get("data") or [], body.get("recordsTotal") or 0
        for site in rows:
            base = re.split(r"\.C\d+$", str(site.get("sourceId") or ""))[0]
            images = [v for v in site.get("images") or [] if v.get("imageUrl") or v.get("videoUrl")]
            name = (site.get("location") or site.get("roadway") or "").strip()
            for n, view in enumerate(images, 1):
                entry = (f"{name} ({n})" if len(images) > 1 else name, str(view.get("id")))
                views[f"{base}.C{n}--1"] = entry
                if n == 1:
                    views[f"{base}--1"] = entry
        if not rows:
            break
        start += len(rows)
    return views

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    try:
        views = _views(get)
    except (OSError, ValueError):
        views = {}
    offset, seen = 0, set()
    while True:
        body = json.loads(get(LAYER + str(offset)))
        features = body.get("features") or []
        for feature in features:
            a, g = feature.get("attributes") or {}, feature.get("geometry") or {}
            url = (a.get("IMAGE_VIEW") or "").strip()
            if not url.startswith("http") or g.get("x") is None:
                continue
            cam_id = urlparse(url).path.rsplit("/", 1)[-1]
            if cam_id in seen:
                continue
            seen.add(cam_id)
            name, same = views.get(cam_id) or (None, None)
            yield {
                "id": cam_id,
                "name": name or f"Baton Rouge traffic camera {cam_id.split('--')[0]}",
                "lat": g["y"],
                "lon": g["x"],
                "image": url.replace("://511la.org/", "://www.511la.org/"),
                "city": "Baton Rouge",
                "county": "East Baton Rouge",
                "extra": {"same_as": f"la_511la:{same}"} if same else {},
            }
        if not body.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
