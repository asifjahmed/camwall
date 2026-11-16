"""Virginia: Arlington County's own traffic cameras (Department of Environmental Services, Transportation Engineering &
Operations), about 315 at signals across the county. The list is the one the county's camera map loads; the county's
open-data layer of the same cameras fills in stream links where the map's port is wrong. Video only: unsigned HLS from
the county's Wowza server, itsvideo.arlingtonva.us. 511 Virginia (va_511va) carries a separate 41 Arlington County
cameras through VDOT's video system, some at the same intersections."""

import json
import re

SOURCE = {
    "name": "Arlington County DES",
    "state": "VA",
    "covers": "Arlington County signalised intersections and arterials (Columbia Pike, US-29, US-50, US-1, Glebe Rd, "
              "Wilson Blvd and others)",
    "site": "https://www.arlingtonva.us/Government/Programs/Transportation/Live-Traffic-Cameras",
    "terms": "https://www.arlingtonva.us/Home/Terms-Conditions",
    "key": None,
    "headers": {},
    "restricted": "Website terms: 'Information may be printed or downloaded from the website for non commercial, "
                  "personal use only ... No person may, however, sell, distribute, modify, transmit, reuse, repost, "
                  "use or create derivative works based on the content of the website in whole or part for any "
                  "purpose without the written permission in each instance from Arlington County Government'. The "
                  "camera page also limits viewers to 'one camera at a time' and 'a live feed for one minute' for "
                  "bandwidth.",
    "notes": "List: datahub-v2-s3.arlingtonva.us/Uploads/AutomatedJobs/Traffic+Cameras.json, the camera map's own "
             "(undocumented; 315 cameras, 'STATUS' ONLINE/OFFLINE). The map builds each stream as "
             "https://itsvideo.arlingtonva.us:<port+10>/live/<Camera Site>.stream/playlist.m3u8. The county's "
             "documented open-data layer 'Traffic Cameras' (services1.arcgis.com/JrtUzVcH8S2wnzVH/.../Traffic_Cameras/"
             "FeatureServer/1, listed on data.virginia.gov and gisdata-arlgis.opendata.arcgis.com; 316 rows, 53 "
             "without a URL and a few with another camera's URL) gives explicit stream URLs; one is used when it "
             "names the same camera, since the map's port is wrong for some (cam287). Streams are 352x240 to "
             "1280x720 H.264; no stills. The open-data portal calls its layers 'a public resource' but 'not ... in "
             "the Public Domain'. arlingtonva.us itself answered 403 when checked (Akamai); the camera page's text was "
             "read from the Wayback Machine (2026-09-08). The map skips the list's first row (cam1) by mistake; it "
             "is included here.",
}
LIST = "https://datahub-v2-s3.arlingtonva.us/Uploads/AutomatedJobs/Traffic+Cameras.json"
LAYER = ("https://services1.arcgis.com/JrtUzVcH8S2wnzVH/arcgis/rest/services/Traffic_Cameras/FeatureServer/1/query"
         "?where=1%3D1&outFields=ID,URL,Status&returnGeometry=false&resultRecordCount=2000&f=json")
STREAM = "https://itsvideo.arlingtonva.us:{port}/live/{site}.stream/playlist.m3u8"


def _layer_urls(get):
    """Camera number -> stream URL from the open-data layer, where the URL names that same camera."""
    urls = {}
    try:
        features = json.loads(get(LAYER)).get("features") or []
    except (OSError, ValueError):
        return urls
    for feature in features:
        a = feature.get("attributes") or {}
        own = re.fullmatch(r"CAM0*(\d+)", (a.get("ID") or "").strip(), re.I)
        url = (a.get("URL") or "").strip()
        named = re.search(r"/live/cam(\d+)\.stream/playlist\.m3u8$", url)
        if own and named and own.group(1) == named.group(1) and url.startswith("https://itsvideo.arlingtonva.us:"):
            urls[int(own.group(1))] = url
    return urls


def cameras(get, key=None):
    layer = _layer_urls(get)
    for row in json.loads(get(LIST)):
        site = (row.get("Camera Site") or "").strip()
        number = re.fullmatch(r"cam(\d+)", site, re.I)
        if not number:
            continue
        video = layer.get(int(number.group(1)))
        port = str(row.get("port") or "").strip()
        if not video and port.isdigit() and int(port):
            video = STREAM.format(port=int(port) + 10, site=site)
        name = re.sub(r"\s+", " ", row.get("Camera EncoderB2") or row.get("Camera Encoder") or site).strip()
        cam = {
            "id": site.lower(),
            "name": name,
            "lat": row.get("Latitude"),
            "lon": row.get("Longitude"),
            "image": None,
            "video": video,
            "video_type": "hls" if video else None,
            "county": "Arlington",
        }
        if (row.get("STATUS") or "").upper() != "ONLINE":
            cam["online"] = False
        yield cam
