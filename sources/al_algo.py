"""Alabama: ALDOT's cameras on ALGO Traffic, from the ALGO API that the University of Alabama's Center for Advanced
Public Safety runs for ALDOT (documented with Swagger at api.algotraffic.com, no key). It covers ALDOT's Southwest
(Mobile, Baldwin), West Central (Birmingham, Tuscaloosa), East Central and Southeast (Montgomery, Dothan) regions;
the North Region (Huntsville, Decatur, Florence) has no cameras in it. Cameras the API marks Hidden, ALDOT or
FirstResponder aren't shown to the public and are left out.

The API's location "direction" (North, South, East, West or Any) is the direction of the route the camera's mile
marker is measured on (I-65 is always North or South, I-10 East or West), not the way the camera faces or the traffic
it watches, so it goes in extra["route_direction"] rather than direction or approach."""

import json

SOURCE = {
    "name": "ALDOT (ALGO Traffic)",
    "state": "AL",
    "covers": "Alabama interstates and state routes around Birmingham, Tuscaloosa, Montgomery, Mobile, Dothan and "
              "the Gulf coast",
    "site": "https://algotraffic.com/",
    "terms": "https://api.algotraffic.com/index.html",
    "key": None,
    "headers": {},
    "restricted": "\"ALGO Traffic cameras are a public safety tool for use in real time and not intended to be "
                  "recorded or otherwise used for any commercial purpose. All unauthorized photography, recording, "
                  "storing, or transmitting of visual material, data, or information gathered from ALGO traffic "
                  "cameras without the permission of ALDOT is expressly prohibited.\" (ALGO API description)",
    "notes": "Documented: GET api.algotraffic.com/v4.0/Cameras returns every camera at once (Swagger at "
             "api.algotraffic.com/index.html; it also takes skip/take, region, city, county and a bounding box). "
             "Stills are JPEG snapshots of the stream (1920x1080, some 2560x1440), served with max-age 600 (one was "
             "11 minutes old, another changed within a minute or two; on 2026-11-08 a picture changed within 3 "
             "minutes while its Last-Modified stayed put, so that header isn't a guide); "
             "video is unsigned HLS (and DASH) on Wowza's CDN (cdn3.wowza.com). The API sits behind Imperva "
             "Incapsula. ALGO's own terms page says only that it doesn't guarantee the data. The location's direction "
             "is the route direction of its mile marker (I-65 North/South, or Any), kept in extra.route_direction. "
             "An id ALGO no longer has answers its grey 'No camera' PNG (3072x1920) with HTTP 200.",
}
LIST = "https://api.algotraffic.com/v4.0/Cameras"


def cameras(get, key=None):
    for cam in json.loads(get(LIST)):
        if cam.get("accessLevel") != "Public":
            continue
        loc = cam.get("location") or {}
        road = loc.get("displayRouteDesignator") or loc.get("routeDesignator")
        cross = loc.get("displayCrossStreet") or loc.get("crossStreet")
        name = " at ".join(v.strip() for v in (road, cross) if v and v.strip() and v != "Unknown") or "Camera"
        video = (cam.get("playbackUrls") or {}).get("hls")
        yield {
            "id": str(cam["id"]),
            "name": name,
            "lat": loc.get("latitude"),
            "lon": loc.get("longitude"),
            "image": cam.get("snapshotImageUrl"),
            "video": video,
            "video_type": "hls" if video else None,
            "road": road,
            "county": loc.get("county"),
            "city": loc.get("city"),
            "extra": {"region": cam.get("responsibleRegion"), "dash": (cam.get("playbackUrls") or {}).get("dash"),
                      "route_direction": loc.get("direction") if loc.get("direction") not in (None, "", "Unknown")
                      else None},
        }
