"""Kentucky: KYTC's cameras as its GoKY map shows them (no key). Traffic cameras come from KYTC's public ArcGIS layer
(TRIMARC's statewide camera set); RWIS road-weather and rest-area truck-parking cameras come from the Firestore
collection GoKY reads. RWIS picture links are signed and expire, so resolve() fetches a fresh one."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "KYTC (GoKY / TRIMARC)",
    "state": "KY",
    "covers": "Kentucky's interstates and parkways: Louisville and Southern Indiana (TRIMARC), Northern Kentucky, "
              "Lexington, the 12 KYTC districts, RWIS road-weather sites and rest-area truck parking",
    "site": "https://goky.ky.gov/",
    "terms": "https://www.kentucky.gov/policies/Pages/disclaimer.aspx",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Traffic cameras: KYTC's ArcGIS layer trafficCamerasCur_Prd "
             "(https://www.arcgis.com/home/item.html?id=00715d24d2bf42e5abc1fab8a08d45eb; locations updated nightly, "
             "pictures about every 2 minutes), JPEG stills on trimarc.org, no video (a few listed Online are 404s). "
             "RWIS: undocumented, the 'realtime' Firestore collection (project kytc-goky) GoKY's map listens to, "
             "readable without a key; pictures are S3 links signed for 48 hours that change with each new picture "
             "(about every 10-15 minutes), so resolve() reads the camera's document again. The layer's 'direction' "
             "(North, East-West...) is given as approach, since it isn't clearly the way the camera faces. The layer "
             "also has 9 legacy rows with no id or status for Indiana cameras at Louisville (pws.trafficwise.org and "
             "old trimarc.org/images/snapshots pictures); all 9 pictures are dead (404, or a redirect to 511in.org), "
             "so they are left out; INDOT's 511in has those cameras. Truck parking: the same Firestore collection's "
             "'trkprk' documents, a dozen rest-area cameras on trimarc.org that aren't in the ArcGIS layer (a "
             "'private property' placeholder is skipped). TRIMARC's own list (www.trimarc.org/dat/WebCameras.json, "
             "undocumented, what trimarc.org's map loads) has a few Online cameras the layer lacks; they have no "
             "position there (so neither map shows them), and the two whose pictures work are added with positions "
             "worked out by hand (POSITIONS), as is any such camera that gains a position in TRIMARC's list.",
}
LAYER = ("https://services2.arcgis.com/CcI36Pduqd0OR4W9/ArcGIS/rest/services/trafficCamerasCur_Prd/FeatureServer/0/"
         "query?where=1%3D1&outFields=*&returnGeometry=false&orderByFields=OBJECTID&resultRecordCount=2000&f=json")
TRIMARC = "https://www.trimarc.org/dat/WebCameras.json"
# TRIMARC cameras missing from the layer and without a position in TRIMARC's list (checked 2026-11-08): lat, lon, county
POSITIONS = {
    # KY 841 at MP 38.1 (Lewis and Clark Bridge approach): between the layer's CCTV05117 (MP 38.0) and CCTV05118 (38.4)
    "CCTV05306": (38.33612, -85.63578, "Jefferson"),
    # 2nd St and Market St, downtown Louisville (the intersection in OpenStreetMap)
    "CCTV05066": (38.25487, -85.75355, "Jefferson"),
}
FIRESTORE = "https://firestore.googleapis.com/v1/projects/kytc-goky/databases/(default)/documents"


def _value(v):
    if not isinstance(v, dict):
        return v
    if "mapValue" in v:
        return {k: _value(x) for k, x in (v["mapValue"].get("fields") or {}).items()}
    if "geoPointValue" in v:
        return v["geoPointValue"]
    for kind in ("stringValue", "doubleValue", "integerValue", "booleanValue", "timestampValue"):
        if kind in v:
            return v[kind]
    return None


def _doc(doc):
    f = {k: _value(v) for k, v in (doc.get("fields") or {}).items()}
    src, where = f.get("source") or {}, f.get("location") or {}
    return f, src, where

EXPIRING = ("image",)  # (shipped lists keep none of these: pre-signed picture links; resolve() looks up fresh ones)


def cameras(get, key=None):
    names = set()
    for a in (f["attributes"] for f in json.loads(get(LAYER)).get("features") or []):
        image = (a.get("snapshot") or "").strip()
        if not image or not a.get("name") or a.get("latitude") is None or a.get("longitude") is None:
            continue  # the rows with no name are 9 legacy Indiana cameras whose pictures are gone
        names.add(a["name"])
        yield {
            "id": a["name"],
            "name": a.get("description") or a.get("name") or "Camera",
            "lat": float(a["latitude"]),
            "lon": float(a["longitude"]),
            "image": image.replace("http://www.trimarc.org/", "https://www.trimarc.org/"),
            "road": a.get("highway") or None,
            "county": a.get("county") or None,
            "refresh": 120,
            "online": a.get("status") != "Offline",
            "approach": a.get("direction") or None,
            "extra": {k: v for k, v in (("district", a.get("district")), ("milemarker", a.get("milemarker"))) if v is not None},
        }
    yield from _trimarc_only(get, names)
    for kind in ("rwis", "trkprk"):
        for doc in _realtime(get, kind):
            f, src, where = _doc(doc)
            image = (src.get("imageUrl") or "").replace("http://www.trimarc.org/", "https://www.trimarc.org/")
            if not image or "latitude" not in where or "privateProperty" in image:
                continue
            signed = "X-Amz-Signature" in image
            route = src.get("route") or src.get("Route")
            mp = src.get("mile_post", src.get("Mile_Point"))
            name = src.get("description") or (f"RWIS {route or ''} MP {mp}" if mp is not None else f"RWIS {src.get('id')}")
            yield {
                "id": f"{kind}/" + (src.get("id") or doc["name"].rsplit("/", 1)[-1]),
                "name": re.sub(r"^\d+\)\s*", "", " ".join(name.split())),  # "06) I-65 NB @ MP 59 Rest Area"
                "lat": where["latitude"],
                "lon": where["longitude"],
                "image": image,
                "road": route or None,
                "county": f.get("county") or None,
                "refresh": 900 if kind == "rwis" else 120,
                "extra": {k: v for k, v in (("doc", doc["name"].split("/documents/", 1)[-1] if signed else None),
                                             ("type", "RWIS" if kind == "rwis" else "truck parking"),
                                             ("published", src.get("published"))) if v},
            }


def _float(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v or None


def _trimarc_only(get, names):
    """Online cameras in TRIMARC's own list that the layer lacks (with a position, from the list or POSITIONS)."""
    try:
        rows = json.loads(get(TRIMARC))
    except (OSError, ValueError):
        return  # an extra; the layer has the rest
    for t in rows if isinstance(rows, list) else []:
        name, image = t.get("name"), (t.get("snapshot") or "").strip()
        if not name or name in names or t.get("status") != "Online" or not image:
            continue
        if (t.get("state") or "Kentucky") != "Kentucky":
            continue  # (none today; the module's cameras are all labelled KY)
        lat, lon = _float(t.get("latitude")), _float(t.get("longitude"))
        county = None
        if lat is None or lon is None:
            lat, lon, county = POSITIONS.get(name, (None, None, None))
        if lat is None:
            continue  # no position anywhere (its picture was dead too, when checked)
        names.add(name)
        try:
            mile = float(t.get("mileMarker"))
        except (TypeError, ValueError):
            mile = None
        yield {
            "id": name,
            "name": t.get("description") or name,
            "lat": lat,
            "lon": lon,
            "image": image.replace("http://www.trimarc.org/", "https://www.trimarc.org/").replace("&", "%26"),
            "road": (t.get("highway") or "").strip() or None,
            "county": county,
            "refresh": 120,
            "approach": t.get("direction") or None,
            "extra": {k: v for k, v in (("milemarker", mile or None), ("list", "trimarc"),
                                         ("position", "worked out by hand" if name in POSITIONS else None)) if v},
        }


def _realtime(get, kind):
    query = {"structuredQuery": {"from": [{"collectionId": "realtime"}], "where": {"fieldFilter": {
        "field": {"fieldPath": "type"}, "op": "EQUAL", "value": {"stringValue": kind}}}}}
    return [row["document"] for row in json.loads(get(FIRESTORE + ":runQuery", data=query)) if row.get("document")]


def resolve(get, camera, key=None):
    doc = (camera.get("extra") or {}).get("doc")
    if not doc:
        return {"image": camera.get("image"), "video": camera.get("video")}
    _, src, _ = _doc(json.loads(get(f"{FIRESTORE}/{quote(doc)}")))
    return {"image": src.get("imageUrl") or camera.get("image"), "video": None}
