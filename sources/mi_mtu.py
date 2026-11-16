"""Michigan: Michigan Technological University's two webcams that look at US-41 in Houghton, from the university's
Webcams page (no key). "College Avenue View" looks west down College Avenue (US-41) toward downtown Houghton and the
Portage Lake Lift Bridge; "Lift Bridge" looks at the Portage Lake Lift Bridge (US-41 between Houghton and Hancock)
from the waterfront. The page's other cameras (campus lawns, ski hill, trails, broomball rinks, a falcon nest, the
waterway) don't show roads and are left out. Each camera has a JPEG still and an unsigned HLS stream."""

import re

SOURCE = {
    "name": "Michigan Technological University",
    "state": "MI",
    "covers": "US-41 in Houghton: College Avenue and the Portage Lake Lift Bridge",
    "site": "https://www.mtu.edu/webcams/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the Community Cams section of the university's Webcams page links each camera's page "
             "(/webcams/view/, /webcams/bridge/) and its still "
             "(www.mtu.edu/mtu_resources/php/webcams/cache/<name>.jpg, 1920x1080, Cache-Control no-store, "
             "regenerated about every 15 s). Each camera page's player has a "
             "data-cam number, which the page's script turns into "
             "https://streamingwebcams.mtu.edu:1935/rtplive/camera<n>.stream/playlist.m3u8 (Wowza, unsigned, "
             "1080p). These are a public university's scenic campus webcams that happen to frame a state highway, "
             "not traffic cameras as such: the lift bridge is seen from a distance. Positions: the College Avenue "
             "camera at the point the university's own 'Michigan Tech Webcams' ArcGIS map gives it; the Lift Bridge "
             "camera by its caption (the Lakeshore Center on Houghton's waterfront), approximate. No webcam terms "
             "(only the university's general policies).",
}
INDEX = "https://www.mtu.edu/webcams/"
STREAM = "https://streamingwebcams.mtu.edu:1935/rtplive/camera{}.stream/playlist.m3u8"
CAMERAS = {  # camera page path -> (lat, lon, direction it faces)
    "/webcams/view/": (47.1195, -88.5493, "W"),
    "/webcams/bridge/": (47.1212, -88.5625, "NW"),
}


def cameras(get, key=None):
    page = get(INDEX).decode("utf-8", "replace")
    for path, (lat, lon, facing) in CAMERAS.items():
        # the index's item for this camera: <h3><a href=path>title</a></h3> <a href=path><img src=still></a>
        link = r'<a href="' + re.escape(path) + r'(?:index\.html)?">'
        item = re.search(link + r'([^<]+)</a>\s*</h3>\s*' + link + r'\s*<img[^>]*\ssrc="([^"]+)"', page)
        if not item:
            continue
        name, still = item.group(1).strip(), item.group(2)
        if still.startswith("/"):
            still = "https://www.mtu.edu" + still
        cam_page = get("https://www.mtu.edu" + path).decode("utf-8", "replace")
        number = re.search(r'data-cam="(\d+)"', cam_page)
        yield {
            "id": path.strip("/").split("/")[-1],
            "name": f"Michigan Tech: {name}",
            "lat": lat,
            "lon": lon,
            "image": still,
            "video": STREAM.format(number.group(1)) if number else None,
            "video_type": "hls" if number else None,
            "road": "US-41",
            "direction": facing,
            "city": "Houghton",
            "county": "Houghton",
            "refresh": 15,
        }
