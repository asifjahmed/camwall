"""Texas: the City of Austin's traffic cameras (Austin Transportation & Public Works), from its documented open-data
list (Socrata dataset b4k4-adkb, public domain, no key). These are the city's signal cameras, on arterial streets;
TxDOT's Austin freeway cameras are in tx_drivetexas. Stills only. The list also holds cameras that are only planned
("DESIRED"), void or removed; those are left out."""

import json

SOURCE = {
    "name": "City of Austin Transportation & Public Works",
    "state": "TX",
    "covers": "City of Austin arterial and signal cameras",
    "site": "https://data.austintexas.gov/Transportation-and-Mobility/Traffic-Cameras/b4k4-adkb",
    "terms": "https://data.austintexas.gov/stories/s/ranj-cccq",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Documented open data (Socrata, public domain; the list updates daily). JPEG stills from "
             "cctv.austinmobility.io, about 150 KB, refreshed every few minutes.",
}
LIST = "https://data.austintexas.gov/resource/b4k4-adkb.json?$limit=50000&$order=camera_id"


def cameras(get, key=None):
    for cam in json.loads(get(LIST)):
        point = (cam.get("location") or {}).get("coordinates")
        if cam.get("camera_status") != "TURNED_ON" or not point or not cam.get("screenshot_address"):
            continue
        street = " ".join(p for p in ((cam.get("primary_st_block") or "").strip(), (cam.get("primary_st") or "").strip()) if p)
        yield {
            "id": cam["camera_id"],
            "name": (cam.get("location_name") or street or cam["camera_id"]).strip(),
            "lat": float(point[1]),
            "lon": float(point[0]),
            "image": cam["screenshot_address"],
            "road": (cam.get("primary_st") or "").strip() or None,
            "city": "Austin",
            "extra": {k: cam[k] for k in ("atd_location_id", "signal_eng_area", "jurisdiction_label", "camera_mfg")
                      if cam.get(k)},
        }
