"""New York: Nassau County DPW's traffic cameras (its Traffic Management Center in Westbury), from the ArcGIS layer the
county's Traffic Camera Viewer loads (no key). They watch county intersections: Old Country Rd, Merrick Rd, Peninsula
Blvd, Hempstead Tpke, Long Beach Rd and others. Stills only (352x240 JPEG). None of them is in 511NY, whose Long Island
cameras are NYSDOT's on the expressway and parkways."""

import json
from urllib.parse import urlencode

SOURCE = {
    "name": "Nassau County DPW (Traffic Management Center)",
    "state": "NY",
    "covers": "Nassau County's traffic signal cameras at county intersections across Long Island's Nassau County",
    "site": "https://app.nassaucountyny.gov/TrafficMgmt/trafficmap",
    "terms": "https://www.nassaucountyny.gov/1985/Disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "cache_bust": True,
    "notes": "Undocumented: the list is the NC_Traffic_Vidcam feature layer (services1.arcgis.com, owner Nassau "
             "County) that the viewer's script (nc_cam.*.js) queries. Pictures are app.nassaucountyny.gov/TrafficMgmt/"
             "trafficmap/autoimg/<Camera>, JPEG stills about a minute old, served 'Cache-Control: public'; the "
             "viewer reloads them every 2.5 s with a random query, so cache_bust is set. That server allows 60 "
             "requests a minute per client and answers 429 (with Retry-After) beyond it, and other clients on the same "
             "address may already be using most of that allowance: fetch each picture no more than about once a minute "
             "and back off on 429. The layer's 'Additional' field is a note ('Active', a cross street), not a status; "
             "an offline camera's picture is a 600x400 PNG reading 'CAMERA OFFLINE' (23,711 bytes, Last-Modified "
             "July 2025) where a working one is a 352x240 JPEG, and checking all 122 would take two minutes of that "
             "allowance, so they aren't marked here. "
             "The county's disclaimer places no limits on reuse.",
}
LAYER = "https://services1.arcgis.com/rsOafHhKLHpnpr4t/ArcGIS/rest/services/NC_Traffic_Vidcam/FeatureServer/0/query"
IMAGE = "https://app.nassaucountyny.gov/TrafficMgmt/trafficmap/autoimg/"
PAGE = 1000


def cameras(get, key=None):
    offset = 0
    while True:
        query = urlencode({"where": "1=1", "outFields": "OBJECTID,Camera,Intersection,Additional", "outSR": 4326,
                           "f": "json", "orderByFields": "OBJECTID",
                           "resultOffset": offset, "resultRecordCount": PAGE})
        answer = json.loads(get(f"{LAYER}?{query}"))
        features = answer.get("features") or []
        for feature in features:
            a = feature.get("attributes") or {}
            where = feature.get("geometry") or {}
            number = (a.get("Camera") or "").strip()
            if not number or where.get("x") is None or where.get("y") is None:
                continue
            name = " ".join((a.get("Intersection") or "").split()).replace(" ,", ",") or f"Camera {number}"
            place = name.rsplit(",", 1)[1].strip() if "," in name else None
            note = (a.get("Additional") or "").strip()
            yield {
                "id": number,
                "name": name,
                "lat": where["y"],
                "lon": where["x"],
                "image": IMAGE + number,
                "city": {"RVC": "Rockville Centre", "No Lawrence": "North Lawrence"}.get(place, place),
                "county": "Nassau",
                "refresh": 60,
                "extra": {"note": note} if note and note != "Active" else {},
            }
        if not features or not answer.get("exceededTransferLimit"):
            break
        offset += len(features)
