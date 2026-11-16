"""Virginia: the Richmond Metropolitan Transportation Authority's two live camera feeds (Downtown Expressway toll plaza
and Powhite Parkway), shown on its site through HDRelay's player. Each feed's current picture and HLS stream come from
the player's settings on manage.hdrelay.com. 511 Virginia (va_511va) carries the Powhite Parkway view too, as its one
RMTA camera."""

import json

SOURCE = {
    "name": "Richmond Metropolitan Transportation Authority",
    "state": "VA",
    "covers": "RMTA toll roads in Richmond: the Downtown Expressway (VA-195) toll plaza and the Powhite Parkway "
              "(VA-76)",
    "site": "https://www.rmtaonline.org/live-feeds/downtown-expressway-feed/",
    "terms": "https://www.rmtaonline.org/terms/terms-and-conditions/",
    "key": None,
    "headers": {},
    "restricted": "Terms of use: 'These Terms of Use permit you to use the Website for your personal, non-commercial "
                  "use only. You must not reproduce, distribute, modify, create derivative works of, publicly "
                  "display, publicly perform, republish, download, store or transmit any of the material on our "
                  "Website' and you agree not to 'Use any robot, spider or other automatic device, process or means "
                  "to access the Website for any purpose, including monitoring or copying any of the material'.",
    "notes": "The two feed pages (rmtaonline.org/live-feeds/downtown-expressway-feed and /powhite-parkway-feed) embed "
             "HDRelay players; manage.hdrelay.com/player/<id> gives the camera id and media server. Stills are "
             "1920x1080 JPEG made on request (<server>/camera/<camera>/snapshot); video is unsigned 1080p HLS "
             "(<server>/camera/<camera>/relay/playlist.m3u8). The player's own coordinates are wrong (one is in "
             "California, the other RMTA's downtown office), so positions here are set by hand: the Downtown "
             "Expressway toll plaza from OpenStreetMap, and the Powhite view where 511 Virginia places the same "
             "picture (approximate). The cameras are pan-tilt-zoom.",
}
PLAYER = "https://manage.hdrelay.com/player/{}"
FEEDS = [
    # (HDRelay player id from the feed page, name, lat, lon, road)
    ("c85243ec-27d6-4ca8-a74c-669d506252cc", "Downtown Expressway toll plaza", 37.53457, -77.50747, "VA-195"),
    ("8636b661-0800-42dd-b8ab-c7a1fce835ec", "Powhite Parkway", 37.5344, -77.5043, "VA-76"),
]


def cameras(get, key=None):
    for player, name, lat, lon, road in FEEDS:
        try:
            settings = json.loads(get(PLAYER.format(player)))
        except (OSError, ValueError):
            continue
        camera = (settings.get("camera") or {}).get("id")
        server = (settings.get("server") or {}).get("hls")
        if not camera or not server:
            continue
        base = ("https:" + server if server.startswith("//") else server).rstrip("/")
        status = (settings.get("camera") or {}).get("status") or {}
        cam = {
            "id": player,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": f"{base}/camera/{camera}/snapshot",
            "video": f"{base}/camera/{camera}/relay/playlist.m3u8",
            "video_type": "hls",
            "road": road,
            "city": "Richmond",
            "extra": {"hdrelay_camera": camera},
        }
        if status.get("online") is False:
            cam["online"] = False
        yield cam
