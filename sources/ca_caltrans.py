"""California: Caltrans' cameras on the state highways, all 12 districts, from the documented CCTV status files on its
Commercial Wholesale Web Portal (CWWP2), one JSON file per district (no key). Every camera has a still picture; about
two thirds also have HLS video from wzmedia.dot.ca.gov. A camera is known by its picture's path ("d3/hwy5atpocket").
The same list feeds QuickMap (quickmap.dot.ca.gov)."""

import json
import re
from urllib.parse import urlparse

SOURCE = {
    "name": "Caltrans",
    "state": "CA",
    "covers": "California's state highways and interstates, all 12 Caltrans districts",
    "site": "https://quickmap.dot.ca.gov/",
    "terms": "https://dot.ca.gov/conditions-of-use",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Documented open data: https://cwwp2.dot.ca.gov/documentation/cctv/cctv.htm ('available for integration "
             "into your application ... no charge'). Pictures update every 1 to 60 minutes depending on the district "
             "(refresh gives it); HLS video is unsigned. The files' 'direction' is the side of the road the camera is "
             "on, not the way it faces, so it goes in extra['side']; direction is set only when the description says "
             "'Looking <way>'.",
}
LIST = "https://cwwp2.dot.ca.gov/data/d{n}/cctv/cctvStatusD{n:02d}.json"
LOOKING = re.compile(r"\blooking (north|south|east|west)(bound)?\b", re.I)


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _url(value):
    value = (value or "").strip()
    if value.startswith("ttps://"):  # one district's file drops the h
        value = "h" + value
    if value.startswith("http://wzmedia.dot.ca.gov/"):
        value = "https://" + value.removeprefix("http://")
    return value if value.startswith(("https://", "http://")) else None


def cameras(get, key=None):
    for n in range(1, 13):
        for row in json.loads(get(LIST.format(n=n)))["data"]:
            cam = row["cctv"]
            loc, data = cam.get("location") or {}, cam.get("imageData") or {}
            still = data.get("static") or {}
            image = _url(still.get("currentImageURL"))
            video = _url(data.get("streamingVideoURL"))
            if not image and not video:
                continue
            path = urlparse(image or video).path
            match = re.match(r"^/data/(d\d+)/cctv/image/([^/]+)/", path)
            cid = f"{match[1]}/{match[2]}" if match else path.strip("/")
            description = (data.get("imageDescription") or "").strip()
            looking = LOOKING.search(description)
            minutes = _float(still.get("currentImageUpdateFrequency"))
            name = (loc.get("locationName") or "").strip() or description or cid
            if description and description.lower().startswith("at ") and description.lower() not in name.lower():
                name = f"{name} {description}"
            extra = {k: v for k, v in {
                "district": loc.get("district"),
                "side": loc.get("direction"),
                "postmile": loc.get("postmile"),
                "description": description,
            }.items() if v}
            yield {
                "id": cid,
                "name": name,
                "lat": _float(loc.get("latitude")),
                "lon": _float(loc.get("longitude")),
                "image": image,
                "video": video,
                "video_type": "hls" if video else None,
                "road": loc.get("route") or None,
                "direction": looking[1].title() if looking else None,
                "county": loc.get("county") or None,
                "city": loc.get("nearbyPlace") or None,
                "refresh": minutes * 60 if minutes else None,
                "online": cam.get("inService") != "false",
                "extra": extra,
            }
