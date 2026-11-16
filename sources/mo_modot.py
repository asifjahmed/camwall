"""Missouri: MoDOT's cameras on its Traveler Information map, from the two lists the map loads (no key): the streaming
cameras (HLS from MoDOT's own Wowza servers, statewide and St. Louis's Gateway Guide, and from Ozarks Traffic in
Springfield, which MoDOT and the City of Springfield run) and a dozen snapshot cameras (JPEG stills). The map's
Kansas City cameras play through a MoDOT proxy that refuses scripts; they are KC Scout's, in mo_kcscout, and are
left out here. A streaming camera is known by its stream name ("MODOT_CAM_209", "ozarks/CAM38")."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "MoDOT (Traveler Information)",
    "state": "MO",
    "covers": "Missouri highways: St. Louis (Gateway Guide), Springfield (Ozarks Traffic), Columbia, Joplin and rural "
              "interstates",
    "site": "https://traveler.modot.org/map/",
    "terms": "https://www.modot.org/privacy",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: /timconfig/feed/desktop/StreamingCams2.json and /map/js/snapshot.json, the lists the "
             "map loads. Untokenized HLS (no stills for the streaming cameras); the snapshot cameras' JPEGs update "
             "every few minutes. Each stream server is probed once per run (up to three playlists) and its cameras "
             "are marked out of service if none plays: sfs02, with 139 cameras, answered 504 for every stream from "
             "about 3 am to at least 11 am on 2026-11-08 (its front end answers; its back end doesn't). Single "
             "streams on a working server can hang (two of sfs04's six did) and aren't detected; a cold stream can "
             "take over 30 s to start. traveler.modot.org sits behind Incapsula, which let these list requests "
             "through. The Ozarks Traffic site itself "
             "(ozarkstraffic.com) answers with an Incapsula page that asks for an hCaptcha, so its own list wasn't used; "
             "its streams are all in MoDOT's list.",
}
BASE = "https://traveler.modot.org"
STREAMS = BASE + "/timconfig/feed/desktop/StreamingCams2.json"
SNAPSHOTS = BASE + "/map/js/snapshot.json"


def _servers_up(get, streams):
    """Whether each stream server is serving its cameras: three of its playlists, spread through its list, are tried
    in turn, and it's up as soon as one answers. A server with fewer than three cameras has one tried again, because a
    stream nobody is watching can take more than the 30 s timeout to start (sfs07's did) and answers at once the next
    time; a dead server (sfs02's front end answering 504 after 30 s for every stream) costs 90 s."""
    by_host = {}
    for cam in streams:
        by_host.setdefault(urlparse(cam["video"]).hostname, []).append(cam["video"])
    up = {}
    for host, urls in by_host.items():
        up[host] = False
        for url in (urls[round(i * (len(urls) - 1) / 2)] for i in range(3)):
            try:
                if get(url).startswith(b"#EXTM3U"):
                    up[host] = True
                    break
            except OSError:
                pass
    return up


def cameras(get, key=None):
    seen, streams = set(), []
    for cam in json.loads(get(STREAMS)):
        url, lat, lon = cam.get("html") or "", cam.get("y"), cam.get("x")
        host = (urlparse(url).hostname or "").lower()
        if "/rtplive/" not in url or not lat or not lon:
            continue  # the KC Scout proxy (tisvc) and anything without a position
        stream = url.split("/rtplive/", 1)[1].split("/")[0]
        cam_id = ("ozarks/" + stream.upper()) if "ozarkstraffic" in host else stream
        if cam_id in seen:
            continue
        seen.add(cam_id)
        streams.append({
            "id": cam_id,
            "name": (cam.get("location") or stream).strip(),
            "lat": float(lat),
            "lon": float(lon),
            "image": None,
            "video": url.replace("://S2.", "://s2.").replace(":443/", "/"),
            "video_type": "hls",
            "extra": {"operator": "Ozarks Traffic" if "ozarkstraffic" in host else "MoDOT"},
        })
    up = _servers_up(get, streams)
    for cam in streams:
        cam["online"] = up.get(urlparse(cam["video"]).hostname, True)
        yield cam
    for cam in json.loads(get(SNAPSHOTS)).get("cameras") or []:
        place = cam.get("location") or {}
        if not cam.get("url") or not place.get("x"):
            continue
        yield {
            "id": "snapshot/" + str(cam.get("id")),
            "name": (cam.get("caption") or "Camera").strip(),
            "lat": float(place["y"]),
            "lon": float(place["x"]),
            "image": BASE + cam["url"] if cam["url"].startswith("/") else cam["url"],
        }
