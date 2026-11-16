"""Texas: the City of Lubbock's traffic cameras, from the city's "Live Traffic Camera Viewer" (no key). Its web map
("Traffic Camera Map New", 76 intersections in November 2026) draws the city's signal layer filtered to the
intersections with cameras, and its popup shows TrafficCam/Images/<asset number>.jpg; this does the same, reading the
filter from the web map so it stays current. The older "Traffic Cameras in Lubbock" map's filter (49 intersections,
all also in the new one) is read too, so no camera drops out if the two drift apart."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "City of Lubbock Traffic Engineering",
    "state": "TX",
    "covers": "City of Lubbock signalized intersections",
    "site": "https://experience.arcgis.com/experience/87bbe335445b4e079d30743b9e9fdfac",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the ArcGIS web maps fc7fc98c (the Live Traffic Camera Viewer's) and da11fce9 (the older "
             "app's), their filters on ASSETNO, and MapServer pubgis.ci.lubbock.tx.us/server/rest/services/"
             "Traffic_Cameras. JPEG stills the viewer says update every 5-10 minutes; on 2026-11-08 every picture was "
             "from 2026-11-07 00:56 UTC, so the city's updater had stopped. TxDOT's Lubbock cameras are in tx_txdot_its.",
}
WEBMAPS = ["https://www.arcgis.com/sharing/rest/content/items/{}/data?f=json".format(i) for i in
           ("fc7fc98c77c344819e77622d99344227", "da11fce9e5414d38af8a3b595b09088a")]  # the new viewer's, the old app's
LAYER = "https://pubgis.ci.lubbock.tx.us/server/rest/services/Traffic_Cameras/MapServer/0/query"
IMAGE = "https://ewebmap.ci.lubbock.tx.us/TrafficCam/Images/{}.jpg"


def _filters(get):
    wheres = []
    for webmap in WEBMAPS:
        try:
            layers = json.loads(get(webmap)).get("operationalLayers") or []
        except (OSError, ValueError):
            continue
        for layer in layers:
            if "Traffic_Cameras" in (layer.get("url") or ""):
                for sub in layer.get("layers") or []:
                    where = (sub.get("layerDefinition") or {}).get("definitionExpression")
                    if where and where not in wheres:
                        wheres.append(where)
    if not wheres:
        raise OSError("the Lubbock web maps have no camera filter")
    return wheres


def cameras(get, key=None):
    where = " OR ".join(f"({w})" for w in _filters(get))
    body = json.loads(get(LAYER, data=f"where={quote(where)}&outFields=*&outSR=4326&f=json".encode(),
                          headers={"Content-Type": "application/x-www-form-urlencoded"}))
    seen = set()
    for feature in body.get("features") or []:
        a, g = feature.get("attributes") or {}, feature.get("geometry") or {}
        asset = a.get("ASSETNO")
        if asset is None or g.get("x") is None or asset in seen:
            continue
        seen.add(asset)
        streets = [s.strip() for s in (a.get("STREET"), a.get("AVENUE")) if s and s.strip()]
        yield {
            "id": str(asset),
            "name": " & ".join(streets) or f"Camera {asset}",
            "lat": g["y"],
            "lon": g["x"],
            "image": IMAGE.format(asset),
            "city": "Lubbock",
            "county": "Lubbock",
            "extra": {"txdot_name": a["TxDOTNAME"]} if a.get("TxDOTNAME") else {},
        }
