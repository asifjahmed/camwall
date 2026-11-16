"""Louisiana: LADOTD's cameras on 511LA (an Arcadis IBI 511 site), from the camera list its List page loads (no key),
paged 100 at a time. A camera site can have several views; each view is a camera here, known by its picture's id
(/map/Cctv/<id>). JPEG stills and untokenized HLS from LADOTD's streaming servers (Baton Rouge, New Orleans,
Shreveport and the rest of the state)."""

import json
import re
from urllib.parse import urlencode

SOURCE = {
    "name": "LADOTD (511LA)",
    "state": "LA",
    "covers": "Louisiana interstates and highways: New Orleans, Baton Rouge, Shreveport, Lafayette, Lake Charles and "
              "the North Shore",
    "site": "https://www.511la.org/list/cameras",
    "terms": "https://www.511la.org/about/disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: /List/GetData/Cameras, the DataTables list behind 511LA's camera list. The documented "
             "REST API (511la.org/developers/doc) needs a key that requires an account, and is throttled to ten "
             "calls a minute. JPEG stills refreshed every few seconds (max-age 10), and 352x240 HLS. approach is each "
             "view's own label, 'Traffic closest to this camera is traveling eastbound on I-20' (392 of 491 views), "
             "else the site's road direction (most say Unknown; the 19 that give one agree with their labels). It "
             "is the carriageway nearest the camera, not the way the camera looks, which 511LA doesn't give; the "
             "description is kept in extra. One view (I-12 at LA 21, ns-cam-059) gives the streaming server's snapshot page as its video link; its playlist on the same "
             "server is used instead. LADOTD's ITS inventory (a consultant's ArcGIS layer, ITS_CCTV) lists about 50 "
             "more cameras than 511LA shows, mostly new Baton Rouge and New Orleans numbers; they aren't published.",
}
BASE = "https://www.511la.org"
PAGE = 100
NEAREST = re.compile(r"closest to (?:this|the) camera is traveling\s+(north|south|east|west)", re.I)
# a view whose video link is the streaming server's snapshot page instead of its playlist (one, in 2026)
WOWZA_SNAPSHOT = re.compile(r"^https?://([^/:]+)(?::\d+)?/snapshots\?application=(\w+)&snap=([\w.-]+?\.streams)\b", re.I)


def _hls(url):
    """The view's HLS playlist: its video link, or the playlist a streaming-server snapshot link stands for."""
    if not url:
        return None
    snapshot = WOWZA_SNAPSHOT.match(url)
    if snapshot:
        host, app, stream = snapshot.groups()
        return f"https://{host}/{app}/{stream}/playlist.m3u8"
    return url if ".m3u8" in url.lower() else None

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    start, total = 0, None
    while total is None or start < total:
        query = {"columns": [{"data": None, "name": ""}], "order": [], "start": start, "length": PAGE,
                 "search": {"value": ""}}
        body = json.loads(get(BASE + "/List/GetData/Cameras?" + urlencode({"query": json.dumps(query),
                                                                          "lang": "en-US"})))
        rows = body.get("data") or []
        total = body.get("recordsTotal") or 0
        for site in rows:
            point = re.match(r"POINT \(([-\d.]+) ([-\d.]+)\)",
                             ((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or "")
            if not point:
                continue
            views = [v for v in site.get("images") or [] if v.get("imageUrl") or v.get("videoUrl")]
            for n, view in enumerate(views, 1):
                image = BASE + view["imageUrl"] if (view.get("imageUrl") or "").startswith("/") else view.get("imageUrl")
                video = None if view.get("videoDisabled") else _hls(view.get("videoUrl"))
                name = (site.get("location") or site.get("roadway") or str(site.get("id"))).strip()
                bound = NEAREST.search(view.get("description") or "")
                bound = f"{bound.group(1).capitalize()}bound" if bound else site.get("direction")
                yield {
                    "id": str(view.get("id") or f"{site.get('id')}-{n}"),
                    "name": f"{name} ({n})" if len(views) > 1 else name,
                    "lat": float(point.group(2)),
                    "lon": float(point.group(1)),
                    "image": image or None,
                    "video": video or None,
                    "video_type": "hls" if video else None,
                    "road": site.get("roadway") or None,
                    "approach": bound if bound and bound != "Unknown" else None,
                    "online": not (view.get("disabled") or view.get("blocked")),
                    "extra": {k: v for k, v in {"site": site.get("id"), "source": site.get("source"),
                                                "description": view.get("description")}.items() if v},
                }
        if not rows:
            break
        start += len(rows)
