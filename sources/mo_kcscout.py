"""Missouri and Kansas: KC Scout, the Kansas City traffic center MoDOT and KDOT run together, from the camera list its
own map loads (no key). Freeway cameras on both sides of the state line, with JPEG stills and HLS video. An id starts
with M for MoDOT's cameras and K for KDOT's, and they sit in those states, which gives each camera its state. The
portable trailer cameras ("PTCCTV...") mostly have no position in this list and are left out (KanDrive, ks_kandrive,
places them); the one that has a position is kept with its video only, since the trailers' stills
("PTCCTV0023-LQ.jpg") are a "Last camera image missing" placeholder and the plain name answers 404.

The video is Wowza with SecureToken: the playlist needs a token, per stream and good for a few minutes, that the
site hands out from DataProvider.asmx/GetVideoParams; resolve() asks for one, as the site's player does."""

import json

SOURCE = {
    "name": "KC Scout (MoDOT and KDOT)",
    "state": ["MO", "KS"],
    "covers": "Kansas City metro freeways in Missouri and Kansas",
    "site": "https://www.kcscout.net/",
    "terms": "https://www.kcscout.net/UserLicense.aspx",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: DataProvider.asmx/LoadEntities, the list kcscout.net's map loads. JPEG stills (about "
             "300 KB, refreshed about every minute) and 720x480 HLS; the video URL in the list has no token and "
             "answers 403 until resolve() adds one. approach is the source's road direction (NB, EB), which says "
             "which carriageway the camera watches, not where it points. These cameras are also on KanDrive "
             "(ks_kandrive) and MoDOT's map. The site's User License (MoDOT) grants 'a non-transferable, "
             "non-exclusive license to use the Products for your personal or business use', says the Products are "
             "copyrighted and that copyright notices must not be altered or removed; it doesn't mention apps or "
             "automated access.",
}
BASE = "https://www.kcscout.net/"
SNAPSHOT = BASE + "TransSuite.VCS.CameraSnapshots/{}.jpg"
BOUND = {"NB": "Northbound", "SB": "Southbound", "EB": "Eastbound", "WB": "Westbound"}
WOWZA = "https://5fca316e7c40f.streamlock.net/live-secure/{}/playlist.m3u8"  # the site's _wowzaDomainUrl and app


def _file(video_url):
    parts = (video_url or "").strip().split("/")
    if len(parts) < 5:
        return None
    return parts[4] + "/" + parts[5] if len(parts) > 5 else parts[4]

# Its list isn't shipped with camwall, only fetched by each install. KC Scout's user license is
# "non-transferable", for your own use.
SHIPPED = False


def cameras(get, key=None):
    answer = json.loads(get(BASE + "DataProvider.asmx/LoadEntities", data={}))["d"]
    if isinstance(answer, str):
        answer = json.loads(answer)
    for cam in answer.get("Camera") or []:
        cam_id = (cam.get("ID") or "").strip()
        lat, lon = cam.get("Latitude") or 0, cam.get("Longitude") or 0
        if not cam_id or not lat or not lon:
            continue
        stream = _file(cam.get("VideoUrl"))
        cross = (cam.get("AtCrossStreet") or "").strip()
        name = (cam.get("OnStreetName") or cam_id).strip()
        if cross and cross != "(none)":
            name = f"{name} at {cross}"
        yield {
            "id": cam_id,
            "name": name.replace("&amp;", "&").replace("&apos;", "'"),
            "lat": lat,
            "lon": lon,
            "image": None if cam_id.startswith("PTCCTV") else SNAPSHOT.format(cam_id),
            "video": WOWZA.format(stream) if stream else None,
            "video_type": "hls" if stream else None,
            "state": "KS" if cam_id.startswith(("K", "PTCCTVKS")) else "MO",
            "approach": BOUND.get((cam.get("Direction") or "").strip().upper()),
            "extra": {"trafficland_id": cam["TrafficLandId"]} if cam.get("TrafficLandId") else {},
        }


def resolve(get, camera, key=None):
    video = camera.get("video")
    if not video:
        return {"image": camera.get("image"), "video": None}
    stream = video.split("/live-secure/", 1)[1].rsplit("/playlist.m3u8", 1)[0]
    token = json.loads(get(BASE + "DataProvider.asmx/GetVideoParams", data=json.dumps({"file": stream}).encode(),
                           headers={"Content-Type": "application/json; charset=utf-8"}))["d"]
    return {"image": camera.get("image"), "video": video.split("?")[0] + "?" + token}
