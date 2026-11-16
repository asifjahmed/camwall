"""Tennessee: TDOT's SmartWay cameras, from the RoadwayCameras list in TDOT's open-data API, which wants an API key of
the user's own (TDOT gives them out on request). Each camera has a PNG still and an HLS stream."""

import json

SOURCE = {
    "name": "TDOT SmartWay",
    "state": ["TN", "AR"],
    "covers": "Tennessee's interstates in and around Nashville, Memphis, Knoxville and Chattanooga (TDOT's four "
              "regional TMCs), with some rural interstate cameras and portable trailer cameras, plus the Memphis TMC's "
              "I-40/I-55 cameras across the river in West Memphis, Arkansas (Crittenden County)",
    "site": "https://smartway.tn.gov/allcams",
    "terms": None,
    "key": "TDOT's SmartWay API Access Request Form: https://www.tn.gov/tdot/traffic-operations-division/"
           "motorist-information/smartway-api-request.html",
    "headers": {},
    "restricted": None,
    "notes": "https://www.tdot.tn.gov/opendata/api/public/RoadwayCameras, sent with the user's key in the ApiKey "
             "header; without one the API answers 401. TDOT's Swagger (https://www.tdot.tn.gov/opendata/index.html) "
             "says keys belong to 'TDOT Api Key Holder' accounts, which TDOT gives out through the request form. "
             "Stills (tnsnapshots.com, PNG) "
             "change about every minute; video is HLS from TDOT's skyvdn.com servers, not signed. The list marks "
             "every camera active; a camera that's down has a 'STREAM NOT AVAILABLE' still (a 21,107-byte 1920x1080 "
             "PNG) and a stream that times out, which the checker reports as a media failure. 20 of the Memphis "
             "cameras are in Crittenden County, Arkansas (the list's county), so they're given state AR; IDrive "
             "Arkansas shows many of the same West Memphis views. No terms page found.",
}
LIST = "https://www.tdot.tn.gov/opendata/api/public/RoadwayCameras"
ARKANSAS = {"Crittenden"}  # (counties in the list that are across the state line)


def cameras(get, key=None):
    if not key:
        raise OSError("TDOT's API needs a key of your own (see SOURCE['key'])")
    rows = json.loads(get(LIST, headers={"ApiKey": key}))
    for c in rows:
        if c.get("lat") is None or c.get("lng") is None:
            continue
        image = c.get("thumbnailUrl") or None
        video = c.get("httpsVideoUrl") or None
        if not image and not video:
            continue
        yield {
            "id": c.get("name") or str(c.get("id")),
            "name": c.get("title") or c.get("description") or c.get("name"),
            "lat": c["lat"],
            "lon": c["lng"],
            "image": image,
            "video": video,
            "video_type": "hls" if video else None,
            "road": c.get("route") or None,
            "county": c.get("county") or None,
            "state": "AR" if c.get("county") in ARKANSAS else "TN",
            "city": c.get("jurisdiction") or None,
            "refresh": 60,
            "online": str(c.get("active")).lower() != "false",
            "extra": {k: v for k, v in (("tdot_id", c.get("id")), ("region", c.get("region")),
                                         ("milemarker", c.get("mileMarker"))) if v},
        }
