"""San Diego County (Flood Control District, Department of Public Works): the district's low-water-crossing road
webcams. The district keeps PTZ cameras where county roads ford a creek (Quarry Rd in Spring Valley, Sandia Creek Dr
near Fallbrook, Country Club Dr near Escondido, Cole Grade Rd near Valley Center) so the public can see whether a
crossing is flooded. Its "Low-Water Crossing Web Cameras" page links one page per camera, each embedding an HDRelay
player; the player's settings give the camera id, the media servers and the camera's position. A camera is known by
its page's name on sdcfcd.org ("quarry")."""

import html
import json
import re

SOURCE = {
    "name": "San Diego County Flood Control District",
    "state": "CA",
    "covers": "Low-water crossings on county roads in unincorporated San Diego County (Quarry Rd, Sandia Creek Dr, "
              "Country Club Dr, Cole Grade Rd)",
    "site": "https://www.sdcfcd.org/content/sdc/sdcfcd/webcams.html",
    "terms": "https://www.sandiegocounty.gov/security-and-privacy-policies/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the district's webcam index page, each camera page's HDRelay player id, and the player "
             "settings on manage.hdrelay.com (camera id, media servers, position, online flag). HLS cameras give a "
             "JPEG made on request (<hls server>/camera/<id>/snapshot) and unsigned HLS "
             "(<hls server>/camera/<id>/relay/playlist.m3u8); a camera set to pictures only (Sandia Creek, Nov 2026) "
             "gives its last uploaded JPEG (<jpg server>/camera/<id>/get_image), which can be hours old over its poor "
             "cellular link. A camera page with no player (Cole Grade Rd, 'offline due to repair' until late 2026) "
             "is skipped until it gets one. The media hosts refuse curl's default User-Agent (405/404) but answer "
             "camwall's. The cameras are PTZ, moved by county staff during storms. No terms of use beyond the county's "
             "privacy policy.",
}
INDEX = "https://www.sdcfcd.org/content/sdc/sdcfcd/webcams.html"
PAGE = "https://www.sdcfcd.org/content/sdc/sdcfcd/webcams/{}.html"
PLAYER = "https://manage.hdrelay.com/player/{}"
LINK = re.compile(r'href="(?:https?://www\.sdcfcd\.org)?/content/sdc/sdcfcd/webcams/([a-z0-9_]+)\.html"[^>]*>(.*?)</a>',
                  re.S | re.I)
LOAD = re.compile(r"HDRelayLoader\.load\(\s*['\"][^'\"]*['\"]\s*,\s*['\"]([0-9a-f-]{36})['\"]")


def _https(server):
    return ("https:" + server if server.startswith("//") else server).rstrip("/")


def cameras(get, key=None):
    index = get(INDEX).decode("utf-8", errors="replace")
    pages = {}
    for slug, label in LINK.findall(index):
        name = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", label))).strip()
        pages.setdefault(slug, re.sub(r"(?i)\s*web\s*cam(era)?$", "", name) or slug)
    for slug, name in pages.items():
        try:
            page = get(PAGE.format(slug)).decode("utf-8", errors="replace")
        except OSError:
            continue
        player = LOAD.search(page)
        if not player:  # (no player on the page: the camera is down for repair)
            continue
        try:
            settings = json.loads(get(PLAYER.format(player[1])))
        except (OSError, ValueError):
            continue
        camera, server, video = settings.get("camera") or {}, settings.get("server") or {}, settings.get("video") or {}
        cid, lat, lon = camera.get("id"), camera.get("latitude"), camera.get("longitude")
        if not cid or lat is None or lon is None or not server.get("hls"):
            continue
        hls = _https(server["hls"])
        cam = {
            "id": slug,
            "name": name,
            "lat": float(lat),
            "lon": float(lon),
            "image": f"{hls}/camera/{cid}/snapshot",
            "video": f"{hls}/camera/{cid}/relay/playlist.m3u8",
            "video_type": "hls",
            "road": name,
            "county": "San Diego",
            "extra": {"hdrelay_player": player[1], "hdrelay_camera": cid},
        }
        if video.get("format") == "jpg":  # pictures only: the last one the camera sent
            width = 800
            height = int(width / float(video.get("aspectRatio") or 4 / 3))
            jpg = _https(server.get("jpg") or re.sub(r"^(.*//b\d+)(\..*)$", r"\1b\2", server["hls"]))
            cam.update(image=f"{jpg}/camera/{cid}/get_image?size={width}x{height}", video=None, video_type=None)
        if (camera.get("status") or {}).get("online") is False:
            cam["online"] = False
        yield cam
