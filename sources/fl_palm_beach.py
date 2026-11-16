"""Florida: Palm Beach County Traffic Engineering's signal cameras, from the stream list its public camera map
(pbctrafficstreams.pbc.gov/portal, a WINK Streaming portal) loads (no key). These are county intersection cameras,
not on FL511. Each has a JPEG poster and HLS video."""

import xml.etree.ElementTree as ET

BASE = "https://pbctrafficstreams.pbc.gov"

SOURCE = {
    "name": "Palm Beach County Traffic Engineering",
    "state": "FL",
    "covers": "Palm Beach County signalised intersections (West Palm Beach, Boca Raton, Lake Worth Beach, "
              "Greenacres, Jupiter and the rest of the county)",
    "site": "https://pbctrafficstreams.pbc.gov/portal/",
    "terms": "https://pbctrafficstreams.pbc.gov/portal/toc.php",
    "key": None,
    "headers": {},
    "restricted": "WINK Streaming's site terms: \"You agree that all materials, products, and services provided on "
                  "this website are the property of WINK Streaming ... You also agree that you will not reproduce or "
                  "redistribute the WINK Streaming's intellectual property in any way\"; and \"You must be at least "
                  "18 (eighteen) years of age before you can use this website.\"",
    "notes": "Undocumented: the portal's list /portal/feeds/loader.php (WINK mediarouter XML). Linked from the "
             "county's Traffic Engineering pages as 'Public Traffic Camera Map'; the county says the video is live "
             "only and not recorded. Stills are 1280x720 JPEG from /vf2/media/image.php?guid=<id> (no-cache, a "
             "fresh frame each time); video is unsigned HLS (1280x720, 15 fps). Streams in 'maintenance' or "
             "'blocked' state are marked out of service.",
}
LIST = BASE + "/portal/feeds/loader.php"


def cameras(get, key=None):
    root = ET.fromstring(get(LIST))
    for stream in root.iter("stream"):
        guid = stream.get("guid")
        if not guid:
            continue
        meta = stream.find("meta")
        meta = meta.attrib if meta is not None else {}
        video = stream.get("href") or None
        poster = stream.get("poster") or ""
        cam = {
            "id": guid,
            "name": stream.get("title") or meta.get("cname") or guid,
            "lat": float(stream.get("lat")),
            "lon": float(stream.get("lng")),
            "image": (BASE + poster) if poster.startswith("/") else (poster or None),
            "video": video,
            "video_type": "hls" if video else None,
            "road": meta.get("roadway") or None,
            "direction": meta.get("orientation") or None,
            "county": "Palm Beach",
            "city": meta.get("locality") or None,
            "extra": {"state": stream.get("state"), "ext_id": meta.get("ext_id") or None},
        }
        if stream.get("state") != "active":
            cam["online"] = False
        yield cam
