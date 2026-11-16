"""Auburn: the City of Auburn's traffic cameras, from the public ArcGIS layer its Traffic Photo Wall
(gis.auburnwa.gov/trafficphotowall) queries: the city's camera inventory (Communication/CommunicationA/MapServer/2),
of which the wall shows the cameras marked SHOWONLINE = 1 and STATUS 'EXISTING' that have a name and a picture name.
Each picture is gis.auburnwa.gov/TrafficPhotoWall/TrafficPhotos/<STRUCTURE>.jpg. A camera is known by its STRUCTURE
number, as the wall labels it ("Camera: 41")."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "City of Auburn Transportation",
    "state": "WA",
    "covers": "City of Auburn arterials (Auburn Way, C St, 15th St SW, S 277th St, A St SE, Lakeland Hills, "
              "Lea Hill)",
    "site": "https://www.auburnwa.gov/city_hall/public_works/transportation/trafficphotowall",
    "terms": "https://www.auburnwa.gov/city_hall/documents/terms_of_use_privacy_policy",
    "key": None,
    "headers": {},
    "restricted": "Auburn's terms: 'The City of Auburn retains copyright on all text, graphic images, maps, photographs "
                  "and other content on this website. ... Copies of any information or materials may be printed for "
                  "limited personal, non-commercial use only. Written permission from the City of Auburn is required "
                  "for any other use or distribution of the information or materials on this site.'",
    "notes": "Undocumented: the public layer and query the Traffic Photo Wall page makes. JPEG stills (about 580x390) "
             "that change every minute or so; the wall reloads them every 60 s. The inventory also holds the city's "
             "detection and security cameras and King County and WSDOT cameras, which the wall leaves out and so "
             "does this source.",
}
LAYER = ("https://utility.arcgis.com/usrsvcs/servers/4283de2d92ef4cb68bc3ed7f1846d642/rest/services/Communication/"
         "CommunicationA/MapServer/2/query")
WHERE = ("IMAGENAME IS NOT NULL AND IMAGENAME <> '' AND CAMERANAME IS NOT NULL AND CAMERANAME <> '' "
         "AND SHOWONLINE = 1 AND STATUS = 'EXISTING'")
FIELDS = "OBJECTID,STRUCTURE,CAMERANAME,CAMERAGROUP,SIGNALIZEDINTERSECTION"  # (never the inventory's IP addresses)
PHOTOS = "https://gis.auburnwa.gov/TrafficPhotoWall/TrafficPhotos/{}.jpg"


def cameras(get, key=None):
    seen, offset = set(), 0
    while True:
        url = (f"{LAYER}?where={quote(WHERE)}&outFields={FIELDS}&outSR=4326&orderByFields=OBJECTID&f=json"
               f"&resultRecordCount=1000&resultOffset={offset}")
        page = json.loads(get(url))
        features = page.get("features") or []
        for f in features:
            a, g = f.get("attributes") or {}, f.get("geometry") or {}
            cid = str(a.get("STRUCTURE") or "").strip()
            if not cid or cid in seen or g.get("x") is None or g.get("y") is None:
                continue
            seen.add(cid)
            name = " ".join((a.get("CAMERANAME") or "").split())
            if name.startswith("ITS - "):
                name = name[6:]
            yield {
                "id": cid,
                "name": name,
                "lat": float(g["y"]),
                "lon": float(g["x"]),
                "image": PHOTOS.format(quote(cid)),
                "city": "Auburn",
                "refresh": 60,
                "extra": {k: v for k, v in {"corridor": a.get("CAMERAGROUP")}.items() if v},
            }
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
