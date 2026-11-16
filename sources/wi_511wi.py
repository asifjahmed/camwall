"""Wisconsin: WisDOT's cameras, from the camera list 511WI's site loads (Arcadis IBI's 511 platform; no key). Each
camera site's picture is a camera here, known by its picture's id (/map/Cctv/<id>); each has an HLS stream too.

511WI lists the 34 Madison Beltline (US 12/18) Flex Lane cameras at 0,0. Their positions here are estimates (PLACED),
worked out once from each camera's name ("US 12/18 at W of Park St") and OpenStreetMap's Beltline: "at X" is where X
crosses the Beltline, "W of X" / "E of X" 250 m along it. The source's own position wins as soon as it gives one."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "WisDOT (511WI)",
    "state": "WI",
    "covers": "Wisconsin's interstates and highways: Milwaukee (STOC), Madison, Fox Valley, Green Bay, Eau Claire, La "
              "Crosse and Wausau",
    "site": "https://511wi.gov/cctv",
    "terms": "https://511wi.gov/Cms/GetFile?id=60dc61b7-2bf0-ed11-abd6-06b534637530.133282862079100000",
    "key": None,
    "headers": {},
    "restricted": "\"WisDOT owns the copyright to the data and video it produces and makes available under the 511WI "
                  "API or through the 511WI website. Any commercial or public use of the data or video available on "
                  "the 511WI website by a third-party requires explicit written consent from WisDOT prior to its use.\" "
                  "(Developers Access Agreement for 511WI API)",
    "notes": "Undocumented: the DataTables JSON the site's camera list loads (/List/GetData/Cameras), paged 100 at a "
             "time. 511WI's documented API (https://511wi.gov/developers/doc) needs a developer key that WisDOT "
             "approves on request, throttled to 10 calls a minute. Stills (PNG, 352x240) change about every 10 s; "
             "video is HLS from cctv1/cctv2.dot.wi.gov, not signed. Terms: the Developers Access Agreement linked "
             "from https://511wi.gov/developers/doc (a .docx) covers \"data or video available on the 511WI "
             "website\" too; it asks for attribution to WisDOT (\"an unaltered logo or caption displayed "
             "prominently\" and notice of WisDOT's copyright) and says the data and video \"may not be altered\". "
             "The site's own /terms page has a title and no text. The 34 Madison Beltline (US 12/18) Flex Lane "
             "cameras, listed at 0,0, are placed at estimated positions (extra.position says so). The 3 Iowa DOT "
             "cameras at the Lansing ferry are left out (ia_iowadot has them). WisDOT also publishes the same 461 "
             "located cameras keylessly on ArcGIS (https://services5.arcgis.com/0pgGLzT0Nh7FVjon/arcgis/rest/"
             "services/511_Camera/FeatureServer/0), a fallback feed.",
}
BASE = "https://511wi.gov"
PAGE = 100
PLACED = {  # picture id -> (lat, lon), estimated from the name: 511WI lists these Beltline Flex Lane cameras at 0,0
    "1231": (43.03529, -89.42579), "1232": (43.03541, -89.42877), "1233": (43.03534, -89.43399),
    "1234": (43.035, -89.44054), "1235": (43.0348, -89.44668), "1236": (43.03545, -89.44992),
    "1238": (43.03677, -89.45299), "1239": (43.03824, -89.45606), "1240": (43.04128, -89.46211),
    "1241": (43.04647, -89.47349), "1242": (43.04212, -89.37321), "1243": (43.04046, -89.37821),
    "1244": (43.03948, -89.38128), "1245": (43.03767, -89.38722), "1246": (43.03717, -89.39087),
    "1247": (43.03539, -89.39701), "1249": (43.03454, -89.40373), "1250": (43.0347, -89.4068),
    "1251": (43.03504, -89.41558), "1252": (43.03519, -89.41964), "1253": (43.04491, -89.32108),
    "1254": (43.04482, -89.32415), "1255": (43.04482, -89.32415), "1256": (43.04463, -89.32722),
    "1257": (43.04396, -89.35115), "1258": (43.04396, -89.35115), "1260": (43.04386, -89.35729),
    "1261": (43.0435, -89.36707), "1262": (43.04318, -89.37014), "1263": (43.04746, -89.29173),
    "1264": (43.04758, -89.2948), "1265": (43.04669, -89.3039), "1266": (43.04601, -89.30697),
    "1267": (43.04546, -89.31004),
}

NOT_FOR_CRAWLERS = True  # (its list's path is one the site's robots.txt asks crawlers to leave alone)


def cameras(get, key=None):
    start = 0
    while True:
        query = json.dumps({"columns": [], "order": [], "start": start, "length": PAGE, "search": {"value": ""}},
                           separators=(",", ":"))
        page = json.loads(get(f"{BASE}/List/GetData/Cameras?query={quote(query)}&lang=en"))
        rows = page.get("data") or []
        for site in rows:
            point = re.search(r"POINT \(([-\d.]+) ([-\d.]+)\)",
                              ((site.get("latLng") or {}).get("geography") or {}).get("wellKnownText") or "")
            located = point and (float(point.group(1)), float(point.group(2))) != (0, 0)
            if site.get("source") == "USER" and "iowadot.gov" in json.dumps(site.get("images")):
                continue  # Iowa DOT's Lansing ferry cameras, which ia_iowadot has
            images = [i for i in site.get("images") or [] if i.get("imageUrl")]
            for n, image in enumerate(images):
                if located:
                    lat, lon, placed = float(point.group(2)), float(point.group(1)), None
                elif str(image.get("id")) in PLACED:
                    (lat, lon), placed = PLACED[str(image.get("id"))], "estimated from the name (511WI gives 0,0)"
                else:
                    continue  # no location at all
                video = image.get("videoUrl") if not image.get("videoDisabled") else None
                name = site.get("location") or site.get("roadway") or "Camera"
                if len(images) > 1:
                    name = f"{name} ({n + 1})"
                direction = site.get("direction")
                yield {
                    "id": str(image.get("id")),
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "image": BASE + image["imageUrl"],
                    "video": video or None,
                    "video_type": "hls" if video else None,
                    "road": site.get("roadway") or None,
                    "direction": direction if direction and direction != "Unknown" else None,
                    "county": site.get("county") or None,
                    "city": site.get("city") or None,
                    "refresh": 10,
                    "online": not (image.get("disabled") or image.get("blocked")),
                    "extra": {k: v for k, v in (("site", site.get("id")), ("region", site.get("region")),
                                                 ("district", site.get("dotDistrict")), ("position", placed)) if v},
                }
        start += PAGE
        if not rows or start >= (page.get("recordsTotal") or 0):
            break
