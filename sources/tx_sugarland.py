"""Texas: the City of Sugar Land's traffic cameras, from the list its ITS map (its.sugarlandtx.gov, "Sugar Land, TX -
Current Traffic") loads (no key). Arterial intersections and the US 59 / US 90A frontage roads, with live JPEG stills
the city's server makes on request. A camera is known by the city's camera number."""

import json

SOURCE = {
    "name": "City of Sugar Land Traffic Management",
    "state": "TX",
    "covers": "City of Sugar Land signalised intersections and US 59 / US 90A frontage roads",
    "site": "https://its.sugarlandtx.gov/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the GeoJSON camera list its.sugarlandtx.gov's map loads (api/trafficcameras?f=geojson); the "
             "pictures are trafficcameraview/image/<id>, 512x288 JPEG made on request (Cache-Control max-age=1), so a "
             "new one at every fetch. A camera the server can't reach gets a 352x240 'CAMERA NOT AVAILABLE' PNG, and "
             "the list has no status field. The server sometimes times out in the TLS handshake (1-2 of 8 picture "
             "fetches in some checker runs). No terms on the ITS site; sugarlandtx.gov (the city's CivicPlus site, "
             "with its general disclaimer) reset the connection when this was written. About 15 of the US 59 / US 90A "
             "cameras sit within 150 m of TxDOT's (tx_txdot_its, tx_houston_transtar) but are the city's own.",
}
LIST = "https://its.sugarlandtx.gov/api/trafficcameras?f=geojson"
IMAGE = "https://its.sugarlandtx.gov/trafficcameraview/image/{}"


def cameras(get, key=None):
    for feature in json.loads(get(LIST)).get("features") or []:
        p, g = feature.get("properties") or {}, feature.get("geometry") or {}
        coords = g.get("coordinates") or [p.get("longitude"), p.get("latitude")]
        if p.get("id") is None or None in coords[:2]:
            continue
        name = " ".join((p.get("cameraName") or "Camera").split())
        camera = {
            "id": str(p["id"]),
            "name": name,
            "lat": float(coords[1]),
            "lon": float(coords[0]),
            "image": IMAGE.format(p["id"]),
            "city": "Sugar Land",
            "county": "Fort Bend",
            "refresh": 10,
        }
        road = name.split(" at ", 1)[0].split(" / ", 1)[0].strip() if " at " in name else None
        if road:
            camera["road"] = road
        yield camera
