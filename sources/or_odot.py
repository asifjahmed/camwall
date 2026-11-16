"""Oregon: the cameras on ODOT's TripCheck, from the keyless inventory its map loads (www.tripcheck.com/Scripts/map/
data/cctvinventory.js, an ArcGIS-style feature set). Besides ODOT's highway cameras it carries its partners' cameras:
Portland (PBOT), Washington County, Clackamas County, Salem, Eugene, Bend and others. TripCheck also mirrors some
Caltrans, WSDOT and Idaho cameras near the borders and the Coast Guard's harbor-bar cameras; those are left out (the
first three belong to their own states' modules, the bar cameras don't show roads). A camera is known by TripCheck's
published image id; a camera with several views has one id per view."""

import json
import re
from urllib.parse import quote

SOURCE = {
    "name": "ODOT (TripCheck)",
    "state": "OR",
    "covers": "Oregon's state highways and interstates, plus Portland, Washington County, Clackamas County, Salem, "
              "Eugene and Bend city and county cameras",
    "site": "https://www.tripcheck.com/",
    "terms": "https://apiportal.odot.state.or.us/product#product=tripcheck-api-data",
    "key": None,
    "headers": {},
    "restricted": None,
    "credit": "Oregon DOT (TripCheck) and partner agencies",
    "disclaimer": (
        "ODOT and public agencies providing the data on this portal attempt to provide the best service "
        "reasonably available, but situations will occur that disrupt service. The updating and dissemination of "
        "this information depends on a number of available resources, including Internet availability, "
        "communications networks, and interconnected computer systems which may be beyond the immediate control "
        "of ODOT. Availability at any given time is not guaranteed.\n\n"
        "Those relying on information presented on this site do so at their own risk, and the State of Oregon, "
        "ODOT, and the public agencies providing the data, and any of their officers, employees or agents shall "
        "be held harmless and released from liability for the accuracy or completeness of this information and "
        "from any actions taken based on the information.\n\n"
        'All information is provided "as is" without warranty of any kind, either express or implied, including, '
        "but not limited to, the implied warranties of merchantability, fitness for a particular purpose, or "
        "non-infringement.\n\n"
        "ODOT assumes no responsibility for errors or omissions in the information or software or other documents "
        "which are referenced by or linked to this portal. Under no circumstances, including, but not limited to, "
        "negligence, shall ODOT or any public agency contributing data to this portal be liable for any direct, "
        "indirect, incidental, special or consequential damages that result from the use of, or the inability to "
        "use, this portal or its content."),
    "notes": "Terms: ODOT lets \"the public and private business\" republish its data and camera images if they credit "
             "the agency, copy the pictures to their own server and use them from there, and repeat its disclaimer "
             "(https://apiportal.odot.state.or.us, TripCheck Data, Terms of Use). camwall shows the credit and the "
             "disclaimer with these cameras, and each install's own server fetches the pictures and serves them to "
             "its pages. Many pictures also carry their agency's name, which ODOT's terms count as credit. "
             "Undocumented: the inventory TripCheck's map loads (refreshed daily). ODOT's documented TripCheck API "
             "(apiportal.odot.state.or.us, CCTV Inventory) has the same list but needs a free key. JPEG stills that "
             "the map reloads every minute; most change every 1 to 5 minutes. The 'live streaming video' TripCheck "
             "offers for about 90 cameras is a TrafficLand fast-refresh still with a per-session token, not HLS, so it "
             "isn't given; extra['video_id'] marks those cameras.",
}
LIST = "https://www.tripcheck.com/Scripts/map/data/cctvinventory.js"
IMAGE = "https://tripcheck.com/RoadCams/cams/"
ELSEWHERE = re.compile(r"\bCalifornia\b|\bIdaho -|\bWashington (-|at\b)|- WA\b|\(USCG\)")
WAYS = re.compile(r"\b(NB|SB|EB|WB)\b")


def cameras(get, key=None):
    data = json.loads(get(LIST).decode("utf-8", errors="replace"))
    for feature in data.get("features") or []:
        a = feature.get("attributes") or {}
        title = " ".join((a.get("title") or "").split())
        filename = (a.get("filename") or "").strip()
        lat, lon = a.get("latitude"), a.get("longitude")
        if not filename or lat is None or lon is None or ELSEWHERE.search(title) or lat < 41.995:
            continue
        route = (a.get("route") or "").strip()
        place = title.split(" - ", 1)[0] if " - " in title else None
        city = county = None
        if route.upper() == "CITY" and place:
            city = "Portland" if place.lower().startswith("port") else place
        elif route.upper() == "CNTY" and place:
            if re.search(r"\sCo(unty)?$", place):
                county = re.sub(r"\s+Co(unty)?$", "", place)
            else:
                city = place
        way = WAYS.search(filename)
        yield {
            "id": str(a.get("publishedImageId") or filename),
            "name": title or filename,
            "lat": float(lat),
            "lon": float(lon),
            "image": IMAGE + quote(filename),
            "road": route if route.upper() not in ("CITY", "CNTY", "") else None,
            "direction": {"NB": "N", "SB": "S", "EB": "E", "WB": "W"}[way[1]] if way else None,
            "city": city,
            "county": county,
            "refresh": 60,
            "extra": {k: v for k, v in {"camera": a.get("cameraId"), "video_id": a.get("videoId")}.items() if v},
        }
