"""Santa Clara (city): the City of Santa Clara's traffic cameras around Levi's Stadium, the convention center and Great
America Pkwy. The camera list (and whether each is active) comes from the city's camera viewer
(trafficcam.santaclaraca.gov, a dropdown), the locations from the city's public ArcGIS layer of camera points
(TrafficCamLocations, used by its camera story map). A camera is known by the viewer's camera id ("GATasman")."""

import html
import json
import re
from urllib.parse import parse_qs, urlparse

SOURCE = {
    "name": "City of Santa Clara Traffic Engineering",
    "state": "CA",
    "covers": "City of Santa Clara arterials near Levi's Stadium (Great America Pkwy, Tasman Dr, Mission College Blvd)",
    "site": "https://trafficcam.santaclaraca.gov/TrafficCamera.aspx",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the viewer page (HTML) and the story map's ArcGIS layer. Pictures are JPEGs from the "
             "viewer's CameraProxy, which the viewer reloads every second (near-live). Three cameras also stream HLS, "
             "but only after a cookie check, so no video is given. The viewer's https certificate had expired on "
             "2026-11-07, so this uses http (the site serves both); switch back when it is renewed. A camera with no "
             "point in the layer (Mission College @ Juliette, Nov 2026) is skipped. No terms found.",
}
VIEWER = "http://trafficcam.santaclaraca.gov/TrafficCamera.aspx"
IMAGE = "http://trafficcam.santaclaraca.gov/CameraProxy.ashx?id={id}"
POINTS = ("https://services2.arcgis.com/evwJC31SSJVvbZfF/arcgis/rest/services/TrafficCamLocations_HTTPS_Points_copyTest/"
          "FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json")
OPTION = re.compile(r'(?is)<option\s+([^>]*)>(.*?)</option>')
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def cameras(get, key=None):
    places = {}
    for f in json.loads(get(POINTS)).get("features") or []:
        a, g = f.get("attributes") or {}, f.get("geometry") or {}
        link = re.search(r"href='([^']+)'", a.get("description") or "")
        cid = (parse_qs(urlparse(link[1]).query).get("CID") or [None])[0] if link else None
        if cid and g.get("x") is not None:
            places[cid] = (float(g["y"]), float(g["x"]))
    page = get(VIEWER).decode("utf-8", errors="replace")
    seen = set()
    for attrs, label in OPTION.findall(page):
        attrs = dict(ATTR.findall(attrs))
        cid = attrs.get("value", "").strip()
        if not cid or cid in seen or cid not in places:
            continue
        seen.add(cid)
        lat, lon = places[cid]
        yield {
            "id": cid,
            "name": html.unescape(re.sub(r"\s+", " ", label)).replace(" (Offline)", "").strip(),
            "lat": lat,
            "lon": lon,
            "image": IMAGE.format(id=cid),
            "city": "Santa Clara",
            "county": "Santa Clara",
            "refresh": 1,
            "online": attrs.get("data-active", "true") == "true",
            "extra": {"video_on_site": True} if attrs.get("data-rtsp") == "true" else {},
        }
