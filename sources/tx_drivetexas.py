"""Texas: TxDOT's cameras on DriveTexas, from the MapLarge table its map queries (no key). Every TxDOT district is in
it; about 225 of its cameras (San Angelo's among them) aren't on its.txdot.gov (tx_txdot_its). The cameras are video
only: HLS from skyvdn.com whose playlist URLs carry a token that expires after 10 minutes, so resolve() asks the table
again for one camera. The table's own still (imageurl) points at localhost and doesn't work."""

import json
import re
from urllib.parse import urlencode

SOURCE = {
    "name": "TxDOT (DriveTexas)",
    "state": "TX",
    "covers": "Texas state highways, all 25 TxDOT districts (Houston, Dallas, Fort Worth, San Antonio, Austin, El Paso, ...)",
    "site": "https://drivetexas.org/",
    "terms": "https://www.txdot.gov/about/disclaimer.html",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the list DriveTexas's map loads from MapLarge (dtx-e-cdn.maplarge.com, table "
             "appgeo/cameraPoint). Video only, 320x240 HLS; the token in each playlist URL lasts 10 minutes, so call "
             "resolve(). direction is the source's road-direction label (EB, NB), not checked against the pictures. "
             "Most of these cameras are also on its.txdot.gov (tx_txdot_its), which has stills, under other ids.",
}
API = "https://dtx-e-cdn.maplarge.com/Api/ProcessDirect?"
TABLE = "appgeo/cameraPoint"
FIELDS = ["name", "description", "XY", "metadata", "active", "problemstream", "httpsurl"]


def _query(get, where=None, take=10000):
    query = {"sqlselect": FIELDS, "start": 0, "table": TABLE, "take": take}
    if where:
        query["where"] = where
    body = json.loads(get(API + urlencode({"request": json.dumps({"action": "table/query", "query": query})})))
    if not body.get("success"):
        raise OSError(f"MapLarge said {body.get('errors')}")
    columns = body["data"]["data"]
    rows = min((len(v) for v in columns.values()), default=0)
    return [{k: v[i] for k, v in columns.items()} for i in range(rows)]


def _camera(row):
    match = re.match(r"POINT \(([-\d.]+) ([-\d.]+)\)", row.get("XY") or "")
    if not match or not row.get("name"):
        return None
    try:
        meta = json.loads(row.get("metadata") or "{}")
    except ValueError:
        meta = {}
    name = row["name"]
    district = name.split("_")[1] if name.startswith("TX_") and name.count("_") >= 2 else None
    extra = {k: v for k, v in {"district": district, "jurisdiction": meta.get("jurisdiction"),
                                "milepost": meta.get("mrm")}.items() if v not in (None, "")}
    return {
        "id": name,
        "name": (row.get("description") or name).strip(),
        "lat": float(match.group(2)),
        "lon": float(match.group(1)),
        "image": None,
        "video": row.get("httpsurl") or None,
        "video_type": "hls",
        "road": meta.get("route") or None,
        "direction": meta.get("direction") or None,
        "online": row.get("active") == 1 and not row.get("problemstream"),
        "extra": extra,
    }

EXPIRING = ("video",)  # (shipped lists keep none of these: signed stream links; resolve() looks up fresh ones)


def cameras(get, key=None):
    for row in _query(get):
        cam = _camera(row)
        if cam and cam["video"]:
            yield cam


def resolve(get, camera, key=None):
    rows = _query(get, where=[{"col": "name", "test": "Equal", "value": camera["id"]}], take=1)
    return {"image": None, "video": rows[0].get("httpsurl") if rows else None}
