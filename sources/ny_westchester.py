"""New York: Westchester County DPW's traffic cameras, from the county GIS layer its Traffic Cameras map loads (no key).
They watch the Bronx River Parkway and county roads (Columbus Ave, Kensico Rd, Mamaroneck Ave, Westchester Ave, Harney
Rd, King St). Stills only, which the county says refresh every 8 seconds. 511NY (ny_511ny) shows about 30 of these as
copies Castle Rock refreshes every 10 minutes or so; this list has all of them, fresher. The layer keeps cameras whose
pictures are gone, so each picture gets one HEAD request and those answering 404 are marked out of service."""

import json
import re
import time
from urllib.parse import urlencode

SOURCE = {
    "name": "Westchester County DPW",
    "state": "NY",
    "covers": "Westchester County's own cameras: the Bronx River Parkway and county roads in White Plains, Valhalla, "
              "Yonkers, Scarsdale, Harrison, Rye Brook and Port Chester",
    "site": "https://www.westchestergov.com/trafficcamera",
    "terms": "https://www.westchestercountyny.gov/disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "cache_bust": True,
    "notes": "The list is the 'Traffic Cameras' layer of the county's Mapping Westchester County map service "
             "(giswww.westchestergov.com/arcgis/rest/services/MappingWestchesterCounty/MapServer/124), which the "
             "county's Traffic Cameras map (ArcGIS web map 7404a89a1e954cc799a194b973422b7d) shows; not documented as "
             "a feed. Pictures are JPEG stills at westchestergov.com/cctv/camera<N>.jpg (REFRESH_RATE '8 seconds'; "
             "the county's own viewer reloads them every second with a timestamp query, and a NetScaler cache sits in "
             "front, so cache_bust is set). The layer has no status field and lists cameras whose pictures are gone "
             "(404), so the adapter sends each picture one HEAD request, about a second apart, and marks those that "
             "answer 404 out of service. The county's disclaimer places no limits on reuse.",
}
LAYER = "https://giswww.westchestergov.com/arcgis/rest/services/MappingWestchesterCounty/MapServer/124/query"
PAGE = 1000
GOING = re.compile(r"going (North|South|East|West)", re.I)


def answers(get, url):
    """False if the picture is gone (404), True if it's there, None if the server didn't say."""
    time.sleep(0.75)  # (about a request a second to the county's server)
    try:
        get(url, method="HEAD")
        return True
    except OSError as e:
        return False if "HTTP 404" in str(e) else None


def cameras(get, key=None):
    found = list(listed(get))
    there = [answers(get, cam["image"]) for cam in found]
    if there.count(False) <= len(found) * 0.8:  # (most of them gone at once is the server, not the cameras)
        for cam, ok in zip(found, there):
            if ok is False:
                cam["online"] = False
    yield from found


def listed(get):
    offset = 0
    while True:
        query = urlencode({"where": "1=1", "outFields": "*", "outSR": 4326, "f": "json", "orderByFields": "OBJECTID",
                           "resultOffset": offset, "resultRecordCount": PAGE})
        answer = json.loads(get(f"{LAYER}?{query}"))
        features = answer.get("features") or []
        for feature in features:
            a = feature.get("attributes") or {}
            where = feature.get("geometry") or {}
            number = a.get("NATIVE_CCTV_ID")
            url = (a.get("URL") or "").strip()
            if number is None or not url or where.get("x") is None or where.get("y") is None:
                continue
            name = (a.get("CCTV_NAME") or a.get("LOCATION") or "").strip() or "Camera"
            going = GOING.search(a.get("DESCRIPTION") or "")
            rate = re.match(r"\s*(\d+)", a.get("REFRESH_RATE") or "")
            yield {
                "id": str(int(number)),
                "name": name,
                "lat": where["y"],
                "lon": where["x"],
                "image": re.sub(r"^http://", "https://", url),
                "road": "Bronx River Parkway" if re.search(r"Bronx River P|\bBRP\b", name) else None,
                "approach": f"{going.group(1).title()}bound" if going else None,
                "county": "Westchester",
                "refresh": int(rate.group(1)) if rate else None,
                "extra": {"description": a.get("DESCRIPTION"), "mile_point": a.get("MILE_POINT"),
                          "owner": a.get("OWNER_NAME")},
            }
        if not features or not answer.get("exceededTransferLimit"):
            break
        offset += len(features)
