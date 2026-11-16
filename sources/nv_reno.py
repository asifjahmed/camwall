"""Nevada: the City of Reno's downtown webcams that show streets, from the city's Webcams pages (reno.gov). The city
streams them live on YouTube, so there's no HLS: each camera's picture is YouTube's live thumbnail of its stream, and
the stream itself is in extra["youtube"]. The video id is read from the camera's page on every run, because a restarted
YouTube stream gets a new one. The city's other webcams (the Reno Aces ballpark, Whitewater Park on the river, Silver
Lake water level) don't show a road and are left out. NDOT's Reno freeway and arterial cameras are in nv_nvroads."""

import re

SOURCE = {
    "name": "City of Reno",
    "state": "NV",
    "covers": "Downtown Reno: Virginia Street at the Reno Arch, and City Plaza with the Virginia Street Bridge",
    "site": "https://www.reno.gov/community/webcams/index.php",
    "terms": "https://www.reno.gov/terms_and_conditions/index.php",
    "key": None,
    "headers": {},
    "restricted": "City of Reno terms: 'You may view, download, and print content for personal, educational, or "
                  "non-commercial use. Any other use (including reproduction, modification, or distribution) requires "
                  "prior written permission'. The streams are on YouTube, whose terms say you may not 'access the "
                  "Service using any automated means (such as robots, botnets or scrapers)' without permission.",
    "notes": "Pictures are YouTube's live thumbnails (i.ytimg.com/vi/<id>/maxresdefault_live.jpg, 1280x720, cached "
             "5 minutes). The pages give no positions: they are the views' subjects, placed by hand. The city's "
             "terms page is an unfilled template ('[Your Agency]').",
    "cache_bust": False,
    "image_json": None,
}
BASE = "https://www.reno.gov/community/webcams/"
CAMERAS = [  # (page, name, lat, lon, road)
    ("virginia-street-webcam", "Virginia Street at the Reno Arch", 39.52806, -119.81361, "N Virginia St"),
    ("city-plaza-webcam", "City Plaza and the Virginia Street Bridge", 39.52545, -119.81265, "N Virginia St"),
]
YOUTUBE = re.compile(r'<iframe[^>]+src="https://www\.youtube(?:-nocookie)?\.com/embed/([\w-]{11})')


def cameras(get, key=None):
    for page, name, lat, lon, road in CAMERAS:
        m = YOUTUBE.search(get(BASE + page + ".php").decode("utf-8", "replace"))
        if not m:  # (the page no longer embeds a YouTube stream)
            continue
        video = m.group(1)
        yield {
            "id": page.removesuffix("-webcam"),
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": f"https://i.ytimg.com/vi/{video}/maxresdefault_live.jpg",
            "video": None,
            "video_type": None,
            "road": road,
            "city": "Reno",
            "county": "Washoe",
            "refresh": 300,
            "extra": {"youtube": f"https://www.youtube.com/watch?v={video}", "page": BASE + page + ".php"},
        }
