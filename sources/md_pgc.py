"""Maryland: Prince George's County DPW&T's cameras, from PGC Trip (pgctrip.com), the county's travel map on Castle
Rock's CARS "511x" platform. The list is the GeoJSON the map loads (no key). Each camera site has one live view, an
HLS stream on Skyline's SkyVDN (s57.us-east-1.skyvdn.com), known here by its stream's name: "cam018" for the county's
own intersection cameras, "CHARTFeed11" for the MDOT SHA (CHART) cameras the county restreams (those are md_chart's
cameras too). The map gives no stills (its preview picture is a county logo).

In November 2026 every view was flagged broken and its stream answered 404, so every camera is out of service here
and the map hides them all; the module follows the flag, so they come back when the county's streams do."""

import json
from urllib.parse import urlparse

SOURCE = {
    "name": "Prince George's County DPW&T (PGC Trip)",
    "state": "MD",
    "covers": "Prince George's County, Maryland: county intersection cameras (National Harbor, Largo/Lake Arbor, "
              "Landover, Marlboro Pike, College Park) and the CHART cameras on the Capital Beltway, US 50 and MD 210 "
              "the county restreams",
    "site": "https://pgctrip.com/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: https://api-511x-pgc.carsprogram.org/cameras/map-features, the list PGC Trip's map loads "
             "(68 sites: 32 county cameras, 8 of them also in CHART's feed, and 36 CHART restreams, CHARTFeed<n>). "
             "On 2026-11-08 all 68 were flagged broken and their streams 404, and the map hides broken cameras; "
             "earlier in 2026 about 45 worked. Video "
             "only, untokenized HLS. No terms of use on PGC Trip; its 'For Developers' link is Castle Rock's "
             "general data-feed page. The county's own camera page (princegeorgescountymd.gov) is behind Akamai, "
             "and couldn't be reached when this was written.",
}
LIST = "https://api-511x-pgc.carsprogram.org/cameras/map-features"


def cameras(get, key=None):
    seen = set()
    for feature in json.loads(get(LIST)).get("features") or []:
        p = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if not p.get("public", True) or len(coords) < 2:
            continue
        location = p.get("location") or {}
        place = location.get("cityReference") or ""  # "in National Harbor", or "1 mile north of Queen Anne"
        for view in p.get("views") or []:
            url = view.get("url") or ""
            if ".m3u8" not in url:
                continue
            stream = urlparse(url).path.removeprefix("/rtplive/").removesuffix("/playlist.m3u8").strip("/")
            if not stream or stream in seen:
                continue
            seen.add(stream)
            yield {
                "id": stream,
                "name": view.get("name") or p.get("name") or "Camera",
                "lat": float(coords[1]),
                "lon": float(coords[0]),
                "image": None,
                "video": url.replace(":443/", "/", 1),
                "video_type": "hls",
                "road": p.get("route") or location.get("routeId") or None,
                "county": "Prince George's",
                "city": place[3:] if place.startswith("in ") else None,
                "online": not view.get("broken"),
                "extra": {k: v for k, v in (
                    ("site", p.get("id")), ("place", place or None),
                    ("owner", "MDOT SHA (CHART), restreamed by the county" if stream.startswith("CHARTFeed")
                     else p.get("cameraOwner"))) if v},
            }
