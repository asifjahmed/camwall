"""Puerto Rico: the Highways and Transportation Authority's (ACT, part of DTOP) cameras on its ITS site, from the
camera list its map loads (Default.aspx/GetCctv, an ASP.NET page method; no key). They watch the San Juan metro
expressways: PR-18, PR-26 (Baldorioty de Castro), PR-52 and others.

Each camera's own page (TrafficImage.aspx?id=N) asks TrafficImage.aspx/GetImageData every 3 s for the time its
picture was last retrieved ("Última Imagen Recuperada", Puerto Rico time); a camera whose picture is more than an
hour old is listed as out of service."""

import json
import re
from datetime import datetime, timedelta, timezone

BASE = "https://its.act.pr.gov"
AST = timezone(timedelta(hours=-4))  # Puerto Rico: Atlantic Standard Time all year
STALE = timedelta(hours=1)

SOURCE = {
    "name": "ACT / DTOP (ITS Puerto Rico)",
    "state": "PR",
    "covers": "San Juan metro expressways (PR-18, PR-26, PR-52, PR-22) and a few San Juan intersections",
    "site": "https://its.act.pr.gov/es/Default.aspx",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the map's page method POST its.act.pr.gov/es/Default.aspx/GetCctv (30 cameras on "
             "8 Nov 2026), plus one POST per camera to TrafficImage.aspx/GetImageData for the time of its latest "
             "picture (older than an hour: online False). Stills are 1280x720 JPEG from Axis cameras at "
             "/images/cameras/<name>.jpg, replaced every 30-60 s. No video. ACT's database holds about 31 more "
             "cameras (PR-26 east to Isla Verde and the airport, PR-66, more of PR-52 and PR-22, more San Juan "
             "intersections) that the map doesn't list and that have no coordinates; they aren't included. The site "
             "says only '©2026, Autoridad de Carreteras y Transportación. Todos los derechos reservados.'",
}


def _road(cam):
    """PR-18 from a device name like '18-4.6_04 MD-IPV', or a 'PR-26' in its name, location or picture's name."""
    m = re.match(r"(\d+)-\d", cam.get("Name") or "")
    if m:
        return "PR-" + m.group(1)
    for text in (cam.get("Name"), cam.get("LocationEs"), cam.get("LocationEn"), cam.get("ImageUrl")):
        m = re.search(r"PR-(\d+)", text or "")
        if m:
            return "PR-" + m.group(1)
    return None


def _last_image(get, cam_id):
    """When the camera's latest picture was retrieved (aware datetime), or None if the page doesn't say."""
    try:
        d = json.loads(get(BASE + "/es/TrafficImage.aspx/GetImageData", data={"id": cam_id}))["d"]
        return datetime.strptime(d["DateTime"], "%d/%m/%Y %I:%M:%S %p").replace(tzinfo=AST)
    except (OSError, ValueError, KeyError, TypeError):
        return None

# Its list isn't shipped with camwall, only fetched by each install. The site says "Todos los derechos
# reservados" (all rights reserved).
SHIPPED = False


def cameras(get, key=None):
    data = json.loads(get(BASE + "/es/Default.aspx/GetCctv", data={}))["d"]
    now = datetime.now(AST)
    for cam in data.get("Cctv") or []:
        if not cam.get("ImageUrl"):
            continue
        location = (cam.get("LocationEn") or cam.get("LocationEs") or "").strip()
        last = _last_image(get, cam["Id"])
        side = re.search(r"\b(NB|SB|EB|WB|MD|MED)-IPV\b", cam.get("Name") or "")
        extra = {"device": cam.get("Name"), "location_es": cam.get("LocationEs")}
        if side:
            extra["side"] = side.group(1)  # the carriageway it stands beside (MD/MED: the median)
        if last:
            extra["last_image"] = last.isoformat()
        yield {
            "id": str(cam["Id"]),
            "name": location or cam.get("Name") or "Camera",
            "lat": cam.get("Latitude"),
            "lon": cam.get("Longitude"),
            "image": BASE + cam["ImageUrl"].replace(" ", "%20"),
            "video": None,
            "road": _road(cam),
            "refresh": 60,
            **({"online": now - last < STALE} if last else {}),
            "extra": extra,
        }
