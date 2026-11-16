"""Indiana: INDOT's cameras (TrafficWise), from the camera list Indiana 511's site loads from its GraphQL API (Castle
Rock's CARS platform; no key). Each camera view is a camera here, known by its view's path ("24978/3896304759"); it has
a still (PNG, grabbed from the video) and an HLS stream."""

import json

SOURCE = {
    "name": "INDOT (511IN / TrafficWise)",
    "state": "IN",
    "covers": "Indiana's interstates and state routes: Indianapolis, Fort Wayne, Northwest Indiana (Borman), "
              "Louisville and Cincinnati approaches, Evansville, and RWIS road-weather sites",
    "site": "https://511in.org/list/cameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the listCameraViewsQuery the site's camera list sends to https://511in.org/api/graphql, "
             "paged 100 at a time. Stills are on public.carsprogram.org and change every few minutes (about 6 when "
             "checked; the video is live); video is HLS from INDOT's TrafficWise servers (skysfs*.trafficwise.org), "
             "not signed. A camera that's out shows the site's 'camera closed' icon instead of a still, and its "
             "stream plays a placeholder; those are online: False. Snowplow cameras (moving) are left out. No terms "
             "page found on the site (its help pages have none, and it links no in.gov policy). The separate IN.gov "
             "portal's terms (https://www.in.gov/core/terms_of_use.html) grant a personal-use-only licence for "
             "content on www.in.gov; they don't name 511in.org. The list matched the map's normalCameras layer "
             "camera for camera on 2026-11-08 (758 on the map, 759 listed: one has its longitude's sign wrong). It "
             "includes 15 Indianapolis city-street cameras (codes 11-049-*), INDOT signal cameras (sigcam-*, 01-*) "
             "and about 10 on the Kentucky side of the Ohio River bridges (codes ky1-*, ky2-*).",
}
API = "https://511in.org/api/graphql"
QUERY = ("query ($input: ListArgs!) { listCameraViewsQuery(input: $input) { cameraViews { category title uri url "
         "sources { type src } parentCollection { title uri bbox location { routeDesignator } } } totalRecords "
         "error { message type } } }")
PAGE = 100


def cameras(get, key=None):
    offset, seen = 0, set()
    while True:
        body = {"query": QUERY, "variables": {"input": {
            "west": -180, "south": -85, "east": 180, "north": 85, "sortDirection": "ASC", "sortType": "ROADWAY",
            "freeSearchTerm": "", "classificationsOrSlugs": [], "recordLimit": PAGE, "recordOffset": offset}}}
        result = json.loads(get(API, data=body))["data"]["listCameraViewsQuery"]
        views = result.get("cameraViews") or []
        for view in views:
            uri = view.get("uri") or ""
            parent = view.get("parentCollection") or {}
            bbox = parent.get("bbox") or []
            if uri in seen or len(bbox) < 2:
                continue
            seen.add(uri)
            hls = next((s["src"] for s in view.get("sources") or [] if "mpegurl" in (s.get("type") or "").lower()), None)
            image = view.get("url") or ""
            road = (parent.get("location") or {}).get("routeDesignator")
            online = image.startswith("http")  # an offline camera's picture is the site's "camera closed" icon
            if not online and not hls:
                continue
            yield {
                "id": uri.removeprefix("camera/"),
                "name": view.get("title") or parent.get("title") or "Camera",
                "lat": bbox[1],
                "lon": -abs(bbox[0]),  # one camera's longitude comes with the wrong sign
                "image": image if online else None,
                "video": hls,
                "video_type": "hls" if hls else None,
                "road": road if road and road != "Unknown" else None,
                "refresh": 300,
                "online": online,
            }
        offset += PAGE
        if not views or offset >= (result.get("totalRecords") or 0):
            break
