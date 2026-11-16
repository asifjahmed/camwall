"""Mississippi: MDOT's cameras on MDOTtraffic.com. The map's camera list (default.aspx/LoadCameraData) gives the
camera sites; each site's map bubble (mapbubbles/camerasite.aspx?site=N) lists its views, each a Wowza stream on
streamingjxnN.mdottraffic.com with a thumbnail and an HLS playlist. A view is a camera here, known by its stream name.
Fetching every bubble takes one request a site (about 470), paced at one a second."""

import html
import json
import re
import time

BASE = "https://www.mdottraffic.com/"

SOURCE = {
    "name": "MDOT (MDOTtraffic)",
    "state": "MS",
    "covers": "Mississippi interstates and state routes: Jackson, the Gulf Coast, DeSoto County (Memphis suburbs), "
              "Hattiesburg, Tupelo and other areas",
    "site": "https://www.mdottraffic.com/default.aspx?showMain=true",
    "terms": "https://mdot.ms.gov/documents/Administration/TermsOfUse.pdf",
    "key": None,
    "headers": {},
    "restricted": "\"users are granted non-commercial short-term non-exclusive revocable use of the Mississippi "
                  "Department of Transportation (MDOT) Web Portal resources including ... *mdottraffic.com\"; "
                  "\"Users may access and use MDOT's web sites, content, and services only in the manner presented "
                  "by MDOT\"; \"You will not use or access any service, information, application or software "
                  "available via the web sites in a manner not expressly permitted by MDOT\"; "
                  "\"Commercial users are subject to different terms of use and are instructed to contact the MDOT "
                  "Chief Information Officer\". (The same terms call the site's information \"in general ... "
                  "public domain\".) Attribution asked: \"Source: Mississippi Department of "
                  "Transportation, www.mdot.ms.gov\".",
    "notes": "Undocumented: the map's own ASP.NET page methods. Stills are Wowza thumbnails of the stream "
             "(352x240 as the site asks; the size parameter takes up to 1280x720), cached 10 s; the site refreshes "
             "them every 5 s. Video is unsigned HLS (1280x720). A view whose thumbnail is a 'novideo' picture is "
             "marked out of service; its image is that placeholder with the view's stream name added to the query "
             "(ignored by the server), so that the app doesn't take the out-of-service views for one camera. "
             "direction is the bubble's view button (N/S/E/W), the way the view looks (e.g. 'US 84 EB Bridge to "
             "Louisiana' is W); extra.description is MDOT's longer description where it has one. "
             "MDOT's traffic-signal (TED) cameras have their own list "
             "(LoadCameraTEDSignalData) that answers 401 and isn't on the public map.",
}
VIEW = re.compile(r"switchImage\('([^']*)',\s*'([^']*)',\s*'((?:[^'\\]|\\.)*)',\s*'((?:[^'\\]|\\.)*)'")
BUTTON = re.compile(r"id='cambutton_([^']+)'>([^<]*)<")


def _text(s):
    return html.unescape(s).replace("\\'", "'").strip()


def _bubble(get, site):
    for attempt in range(3):
        try:
            return get(f"{BASE}mapbubbles/camerasite.aspx?site={site}").decode("utf-8", "replace")
        except OSError:
            if attempt == 2:
                return ""
            time.sleep(3)


def _video(thumb, stream):
    host = re.match(r"https?://([^/]+)/", thumb)
    if not host or "novideo" in thumb.lower():
        return None
    return f"https://{host.group(1)}/rtplive/{stream}.stream/playlist.m3u8"


def cameras(get, key=None):
    sites = json.loads(get(BASE + "default.aspx/LoadCameraData", data={}))["d"]
    seen = set()
    for site in sites:
        number = re.search(r"site=(\d+)", site.get("framehtml") or "")
        if not number:
            continue
        time.sleep(0.75)  # about one request a second
        page = _bubble(get, number.group(1))
        views = [(html.unescape(t), s, _text(n), _text(d)) for t, s, n, d in VIEW.findall(page)]
        directions = dict(BUTTON.findall(page))
        if not views:  # (a bubble without view buttons: its one view is in javaimgsrc and the favourites button)
            thumb = re.search(r'javaimgsrc = "([^"]+)"', page)
            stream = re.search(r"streamname=([^.&]+)\.stream", thumb.group(1)) if thumb else None
            stream = stream or re.search(r"""favsButtonClicked\([^)]*["']([^"']+)["']\s*\)""", page)
            title = re.search(r'<p id="camTitle">([^<]*)</p>', page)
            summary = re.search(r'<p id="camSummary">([^<]*)</p>', page)
            if thumb and stream:
                views = [(html.unescape(thumb.group(1)), stream.group(1),
                          _text(title.group(1)) if title else site.get("tooltip") or "",
                          _text(summary.group(1)) if summary else "")]
        for thumb, stream, name, description in views:
            if stream in seen:
                continue
            seen.add(stream)
            video = _video(thumb, stream)
            image = thumb
            if "novideo" in thumb.lower():  # (MDOT's one "no video" picture: made distinct per view, or the
                image = f"{thumb}{'&' if '?' in thumb else '?'}stream={stream}"  # app takes them all for one camera)
            cam = {
                "id": stream,
                "name": name or site.get("tooltip") or "Camera",
                "lat": site.get("lat"),
                "lon": site.get("lon"),
                "image": image,
                "video": video,
                "video_type": "hls" if video else None,
                "refresh": 5,
                "extra": {"site": number.group(1), "site_name": site.get("tooltip")},
            }
            if description:
                cam["extra"]["description"] = description
            if directions.get(stream, "").strip():
                cam["direction"] = directions[stream].strip()
            if "novideo" in thumb.lower():
                cam["online"] = False
            yield cam
