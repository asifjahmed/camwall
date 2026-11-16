"""South Carolina: SCDOT's cameras on 511SC (Iteris ATIS), from the GeoJSON camera layer its map loads (no key).
Video and stills are served by SkyVDN (Skyline): an HLS playlist per camera and a PNG still."""

import json

SOURCE = {
    "name": "SCDOT (511SC)",
    "state": "SC",
    "covers": "South Carolina interstates and major routes around Columbia, Charleston, Greenville-Spartanburg, "
              "Florence, Rock Hill, Myrtle Beach, Gaffney and the coastal bridges",
    "site": "https://www.511sc.org/",
    "terms": "https://www.511sc.org/static/disclaimer.html",
    "key": None,
    "headers": {},
    "restricted": "\"You may not modify, publish, transmit, display, participate in the transfer or sale, create "
                  "derivative works or in any way exploit, any of the content, in whole or in part, without the "
                  "express written permission of SCDOT.\" (SCDOT Disclaimer)",
    "notes": "Undocumented: the map's layer sc.cdn.iteris-atis.com/geojson/icons/metadata/icons.cameras.geojson. "
             "Stills are 720x480 PNG (the listed URL redirects to scdotsnap.us-east-1.skyvdn.com/<name>.png, "
             "served no-cache); video is unsigned HLS on sNN.us-east-1.skyvdn.com (720x480). The list has "
             "'active' and 'problem_stream' flags, used for online, but they are always true/false: a camera that "
             "is down still serves a 1920x1080 'STREAM NOT AVAILABLE' PNG. The list's direction (NB, SB, EB, WB) "
             "is the carriageway the camera watches (it matches the bound in the name for 750 of 759), so it is "
             "given as approach. Its jurisdiction is the SCDOT TMC region (Columbia, Charleston, Coastal Bridges, "
             "...), not a city, and is kept in extra.region. The CDN also serves an older layer, "
             "icons.cctv.geojson (496 cameras); its 85 extra ids are renumbered duplicates or dead streams.",
}
LIST = "https://sc.cdn.iteris-atis.com/geojson/icons/metadata/icons.cameras.geojson"
BOUND = {"N": "Northbound", "S": "Southbound", "E": "Eastbound", "W": "Westbound"}


def cameras(get, key=None):
    for feature in json.loads(get(LIST)).get("features") or []:
        p = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
        video = p.get("https_url") or None
        bound = (p.get("direction") or "").strip().upper()
        cam = {
            "id": str(p.get("name") or p.get("id")),
            "name": p.get("description") or p.get("name") or "Camera",
            "lat": coords[1],
            "lon": coords[0],
            "image": p.get("image_url") or None,
            "video": video,
            "video_type": "hls" if video else None,
            "road": p.get("route"),
            "approach": BOUND.get(bound.removesuffix("B")) if bound in ("N", "S", "E", "W", "NB", "SB", "EB", "WB")
            else None,
            "refresh": 60,
            "extra": {k: v for k, v in (("uuid", p.get("id")), ("milepost", p.get("mrm")),
                                         ("region", p.get("jurisdiction")), ("label", p.get("direction")))
                      if v not in (None, "")},
        }
        if p.get("active") is False or p.get("problem_stream"):
            cam["online"] = False
        yield cam
