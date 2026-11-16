"""Virginia: Transurban's cameras on the Northern Virginia Express Lanes it runs for VDOT (I-495 Capital Beltway, I-95
and I-395), from the camera list its "Map your trip" page loads. These are Transurban's own cameras, separate from
VDOT's on the same roads. Video only: unsigned HLS from vds.aws.expresslanes.com."""

import json
import re

SOURCE = {
    "name": "Transurban (495, 95 and 395 Express Lanes)",
    "state": "VA",
    "covers": "I-495 Express Lanes (Springfield to the Dulles Toll Road), I-95 Express Lanes (Fredericksburg to "
              "Edsall Rd) and I-395 Express Lanes",
    "site": "https://www.expresslanes.com/map-your-trip",
    "terms": "https://www.expresslanes.com/website-and-mobile-app-terms-of-use",
    "key": None,
    "headers": {},
    "restricted": "Terms of use: 'you may not engage in scraping, data mining, harvesting, screen scraping, data "
                  "aggregating, and indexing. You agree that you will not use any robot, spider, scraper or other "
                  "automated means to access the Website or Mobile App for any purpose without the express prior "
                  "written permission of Transurban' and 'you may not: (i) offer to third parties a service of your "
                  "own that uses the services or Material contained within the Website or Mobile App'.",
    "notes": "Undocumented: www.expresslanes.com/maps-api/get-cameras, the map page's own JSON (52 cameras: 495 21, "
             "95 22, 395 9; cached an hour). Each gives lat/lon, a facing direction (N/S) and a description of what "
             "is on the left and right of the picture. Streams are 1280x720 H.264 HLS (RTMP and RTSP are listed "
             "too); no stills. Transurban is VDOT's private concessionaire for these lanes.",
}
LIST = "https://www.expresslanes.com/maps-api/get-cameras"
DIRECTIONS = {"N": "North", "S": "South", "E": "East", "W": "West"}


def cameras(get, key=None):
    for c in json.loads(get(LIST)).get("infra_cameras") or []:
        name = (c.get("name") or "").strip()
        if not name:
            continue
        urls = {u.get("type"): u.get("url") for u in c.get("url") or [] if isinstance(u, dict)}
        video = urls.get("hls") or None
        road = re.match(r"CCTV-(\d+)-", name)
        place = re.match(r"CCTV-(\d+)-([NSEW])-([\d.]+)(?:-(\d+))?$", name)
        label = name
        if place:
            label = f"I-{place.group(1)} Express Lanes, mile {place.group(3)}"
            if place.group(4):
                label += f" (camera {place.group(4)})"
        yield {
            "id": name,
            "name": label,
            "lat": c.get("loc_lat"),
            "lon": c.get("loc_lon"),
            "image": None,
            "video": video,
            "video_type": "hls" if video else None,
            "road": f"I-{road.group(1)}" if road else None,
            "direction": DIRECTIONS.get((c.get("direction") or "").strip().upper()),
            "extra": {"view": (c.get("message") or "").strip() or None},
        }
