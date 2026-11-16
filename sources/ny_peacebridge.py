"""New York: the Peace Bridge (Buffalo and Fort Erie Public Bridge Authority) cameras, from the Authority's Traffic
Cameras page (no key). The Authority streams them live on YouTube; there's no HLS, so each camera's picture is YouTube's
live thumbnail of its stream and the stream itself is in extra["youtube"]. Three look at the Canadian plaza in Fort
Erie (extra["country"] = "CA")."""

import html
import re

SOURCE = {
    "name": "Peace Bridge Authority",
    "state": "NY",
    "covers": "The Peace Bridge between Buffalo and Fort Erie: both plazas, the deck and the approaches",
    "site": "https://www.peacebridge.com/media-room/traffic-cameras/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": "Its pictures are thumbnails of the Peace Bridge Authority's YouTube live streams, and YouTube's "
                  "terms forbid accessing it by automated means; the cameras' positions come from NITTEC's map, "
                  "whose own terms restrict apps like this one.",
    "notes": "The page lists YouTube live streams (channel PeaceBridgeAuthority); pictures are YouTube's live "
             "thumbnails (i.ytimg.com/vi/<id>/maxresdefault_live.jpg, cached 5 minutes). The page gives no positions: "
             "they come from NITTEC's camera map, which shows five of these cameras (the sixth is placed at the "
             "Canadian plaza). The Authority posts no website terms (its /terms page is purchasing terms).",
}
PAGE = "https://www.peacebridge.com/media-room/traffic-cameras/"
PLACES = {  # video id -> lat, lon, in Canada (from NITTEC's map)
    "9En2186vo5g": (42.90617, -78.90079, False),
    "DnUFAShZKus": (42.90706, -78.90620, False),
    "WPMgP2C3_co": (42.90743, -78.90935, True),
    "SETJ79HmwI0": (42.90774, -78.91968, True),
    "yygTuX5JaKg": (42.90174, -78.89984, False),
    "g9hNGJxw6Yw": (42.90800, -78.91300, True),
}
BRIDGE = (42.9064, -78.9055, False)


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", errors="replace")
    seen = set()
    for match in re.finditer(r"watch\?v=([A-Za-z0-9_\-]{11})", page):
        video = match.group(1)
        if video in seen:
            continue
        seen.add(video)
        before = re.sub(r"<[^>]+>", "|", page[max(0, match.start() - 1500):match.start()])
        labels = [s.strip() for s in html.unescape(before).split("|") if s.strip() and len(s.strip()) < 60
                  and not re.search(r"[{};=<>]", s)]
        lat, lon, canada = PLACES.get(video, BRIDGE)
        yield {
            "id": video,
            "name": f"Peace Bridge: {labels[-1]}" if labels else "Peace Bridge",
            "lat": lat,
            "lon": lon,
            "image": f"https://i.ytimg.com/vi/{video}/maxresdefault_live.jpg",
            "road": "Peace Bridge",
            "city": "Fort Erie" if canada else "Buffalo",
            "refresh": 300,
            "extra": {"youtube": f"https://www.youtube.com/watch?v={video}", **({"country": "CA"} if canada else {})},
        }
