"""Maryland: MDOT SHA's CHART cameras, from CHART's documented camera feed (no key). It also has the Maryland
Transportation Authority's cameras on the Nice/Middleton (US 301) bridge, and some Prince George's County ones.

Every camera is untokenized HLS video. CHART's camera page shows a thumbnail for each (/wwwroot/thumbnails/<id>.jpg),
given here as the still. CHART renews the thumbnails every few minutes, but Cloudflare in front of chart.maryland.gov
keeps them for up to two hours, so the page asks for each with a changing ?v= query (cache_bust)."""

import json

SOURCE = {
    "name": "MDOT SHA (CHART)",
    "state": "MD",
    "covers": "Maryland's interstates and state highways, with a few MDTA and Prince George's County cameras",
    "site": "https://chart.maryland.gov/TrafficCameras/GetTrafficCameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Documented: https://chart.maryland.gov/DataFeeds/GetDataFeeds (Live Traffic Cameras, JSON). No terms of "
             "use are posted. Stills are the camera page's thumbnails, renewed every few minutes (1 to 10 minutes old "
             "with a fresh query; Cloudflare's cached copies were up to 2 hours old); the video is live. "
             "Cameras whose commMode isn't ONLINE, or whose opStatus is a failure, are marked out of service.",
    "cache_bust": True,
}
LIST = "https://chart.maryland.gov/DataFeeds/GetCamerasJson"
PREFIX = {"IS": "I-", "US": "US ", "MD": "MD "}


def cameras(get, key=None):
    for cam in json.loads(get(LIST)):
        if not cam.get("id") or not cam.get("lat") or not cam.get("lon"):
            continue
        road = None
        if cam.get("routePrefix") in PREFIX and cam.get("routeNumber"):
            road = f"{PREFIX[cam['routePrefix']]}{cam['routeNumber']}{cam.get('routeSuffix') or ''}"
        host = cam.get("cctvIp") or "strmr5.sha.maryland.gov"
        status = cam.get("opStatus") or ""
        yield {
            "id": cam["id"],
            "name": cam.get("description") or cam.get("name") or "Camera",
            "lat": float(cam["lat"]),
            "lon": float(cam["lon"]),
            "image": f"https://chart.maryland.gov/wwwroot/thumbnails/{cam['id']}.jpg",
            "video": f"https://{host}/rtplive/{cam['id']}/playlist.m3u8",
            "video_type": "hls",
            "road": road,
            "online": cam.get("commMode") == "ONLINE" and "FAILURE" not in status,
            "extra": {k: v for k, v in {
                "region": ", ".join(cam.get("cameraCategories") or []) or None, "mile_post": cam.get("milePost"),
                "status": status or None, "page": cam.get("publicVideoURL")}.items() if v},
        }
