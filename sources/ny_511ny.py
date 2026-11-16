"""New York: 511NY's cameras, from the list its map loads (Castle Rock's 511x platform, which replaced IBI's in 2026;
no key). It has NYSDOT's cameras across the state, the Thruway's, Westchester County's and a few Ontario MTO ones at
the Niagara crossings (marked extra["country"] = "CA"), plus NYC DOT's (which ny_nyc_dot also gives, from NYC DOT;
the hundred-odd NYC DOT cameras 511NY lists that NYC DOT has retired are marked out of service). Westchester County's
cameras here are Castle Rock's slower copies of some of ny_westchester's.

A camera site can have several views (a handful do), and each view is a camera here, known by the site's id, plus its
picture's file name when the site has more than one. Most NYSDOT cameras are HLS
video with a preview still that Castle Rock refreshes every 10 minutes or so; NYC DOT's are stills."""

import json
import re

SOURCE = {
    "name": "NYSDOT (511NY)",
    "state": "NY",
    "covers": "New York's state highways, the Thruway, Westchester County and New York City (NYC DOT)",
    "site": "https://511ny.org/",
    "terms": "https://511ny.org/help/7",
    "key": None,
    "headers": {},
    "restricted": "\"You may not ... Sell, reproduce, modify, publicly display, perform, distribute, or otherwise use the "
                  "content for any personal, public, or commercial purpose, including use of the content on any other "
                  "website, without the express written consent of NYSDOT\"; \"[nor] Use any robot, spider, or other "
                  "automated program or device ... to monitor, copy, summarize, or otherwise extract information from "
                  "511NY, except as permitted under the 511NY Developer Access Agreement\" (feeds by approved request "
                  "only: https://511ny.org/help/24)",
    "notes": "Undocumented: the list the 511ny.org map loads. NYSDOT's documented camera feed (XML) needs an approved "
             "request (https://511ny.org/help/24). HLS streams aren't tokenized. A few cameras have no usable position "
             "(0, 0) and are left out; some have their longitude's sign flipped, which is fixed. 511NY still lists "
             "about 120 NYC DOT cameras that NYC DOT has retired (their pictures answer 404, and NYC DOT's own list, "
             "webcams.nyctmc.org/api/cameras, leaves them out), all as working: the adapter fetches NYC DOT's list "
             "once and marks those out of service (extra['retired']); if that list can't be had, none is marked.",
}
LIST = "https://api-511x-nysdot.carsprogram.org/cameras/map-features"
NYC_DOT = "https://webcams.nyctmc.org/api/cameras"  # (NYC DOT's own list: the cameras it still serves)
NYC_ID = re.compile(r"nyctmc\.org/api/cameras/([0-9a-fA-F-]{36})/")


def nyc_dot_ids(get):
    """The ids of the cameras NYC DOT still serves, or None if its list can't be had."""
    try:
        return {str(cam.get("id")).lower() for cam in json.loads(get(NYC_DOT)) if cam.get("id")}
    except (OSError, ValueError):
        return None


def cameras(get, key=None):
    serving = nyc_dot_ids(get)
    for feature in json.loads(get(LIST))["features"]:
        site = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
        lon, lat = coords[0], coords[1]
        if not lat or not lon:
            continue
        if lon > 0:  # a flipped sign
            lon = -lon
        views = site.get("views") or []
        location = site.get("location") or {}
        city = (location.get("cityReference") or "").removeprefix("in ").removeprefix("near ") or None
        for view in views:
            url = view.get("url")
            if not url:
                continue
            video = view.get("type") == "WMP" and ".m3u8" in url
            image = view.get("videoPreviewUrl") if video else url
            extra = {"owner": site.get("cameraOwner")}
            if url.startswith("https://public.carsprogram.org/cameras/NYSDOT/other/") and (
                    site.get("route") in ("QEW", "HWY 405", "HWY 406", "Thorold Tunnel")) or (
                    "Canadian Toll Plaza" in (site.get("name") or "")):  # (the Lewiston-Queenston bridge's, in Queenston)
                extra["country"] = "CA"
            nyc = NYC_ID.search(url)
            retired = bool(nyc and serving and nyc.group(1).lower() not in serving)
            if retired:
                extra["retired"] = "not in NYC DOT's own list; its picture answers 404"
            yield {
                "id": str(site["id"]) + (f"/{url.rstrip('/').rsplit('/', 1)[-1]}" if len(views) > 1 else ""),
                "name": (view.get("name") if len(views) > 1 else None) or site.get("name") or "Camera",
                "lat": lat,
                "lon": lon,
                "image": image,
                "video": url if video else None,
                "video_type": "hls" if video else None,
                "road": site.get("route"),
                "city": city,
                "online": not view.get("broken") and not retired,
                "extra": extra,
            }
