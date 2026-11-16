"""Delaware: DelDOT's cameras, from the camera feed its Transportation Management Center publishes for its own map
and for anyone else (no key). Live HLS video only; DelDOT publishes no stills."""

import json
import re

SOURCE = {
    "name": "DelDOT",
    "state": "DE",
    "covers": "Delaware's state highways in all three counties (New Castle, Kent, Sussex), including the city-street "
              "intersections of Wilmington, Newark and Dover that its Transportation Management Center watches",
    "site": "https://deldot.gov/map/index.shtml?tab=TrafficCameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "The open feed tmc.deldot.gov/json/videocamera.json (undocumented, but public and keyless; its map and "
             "Delaware FirstMap's DE_TMC_Traffic_Feeds layer use it). No terms of use are published (deldot.gov "
             "links only the state privacy policy, https://delaware.gov/privacy-policy/). Video is untokenized HLS "
             "(https://video.deldot.gov/live/<id>.stream/playlist.m3u8); the map's thumbnails are drawn in the "
             "browser from the video, so there are no stills. deldot.gov's own pages reject short user agents (an F5 "
             "firewall); the feed and video don't. Some streams start on demand: the first chunklist request can "
             "answer 404 for a few seconds. road and approach are read from the title ('US 13 SB @ DE 14').",
}
LIST = "https://tmc.deldot.gov/json/videocamera.json"
BOUND = {"NB": "Northbound", "SB": "Southbound", "EB": "Eastbound", "WB": "Westbound"}


def _road(title):
    """(road, approach) from a title like 'US 13 SB @ DE 14': the part before '@', its direction split off."""
    if "@" not in title:
        return None, None
    road = title.split("@", 1)[0].strip()
    if road.count("(") > road.count(")"):  # a title cut short: 'DE 1 BUSINESS (N REHOBOTH @ NO'
        road = road[:road.rfind("(")].strip()
    m = re.fullmatch(r"(.+?)\s+(NB|SB|EB|WB)", road)
    if m:
        return m.group(1), BOUND[m.group(2)]
    return road or None, None


def cameras(get, key=None):
    for cam in json.loads(get(LIST)).get("videoCameras") or []:
        urls = cam.get("urls") or {}
        video = urls.get("m3u8s") or urls.get("m3u8")
        if not cam.get("id") or not video or not cam.get("lat") or not cam.get("lon"):
            continue
        name = cam.get("title") or cam["id"]
        road, approach = _road(name)
        out = {
            "id": cam["id"],
            "name": name,
            "lat": float(cam["lat"]),
            "lon": float(cam["lon"]),
            "image": None,
            "video": video.replace("https://video.deldot.gov:443/", "https://video.deldot.gov/"),
            "video_type": "hls",
            "county": cam.get("county"),
            "online": bool(cam.get("enabled", True)) and cam.get("status", "Active") == "Active",
        }
        if road:
            out["road"] = road
        if approach:
            out["approach"] = approach
        yield out
