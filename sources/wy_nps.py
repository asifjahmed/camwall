"""National Park Service: the NPS webcams that show a road, from the webcam index nps.gov's own search pages use
(www.nps.gov/solr, no key). NPS publishes about 290 webcams; most are scenic, wildlife, volcano or air-quality views,
so only the ones whose own title or description says they watch a road or an entrance station's traffic are kept, by
NPS's webcam id (a GUID, stable across the index and the view page, www.nps.gov/media/webcam/view.htm?id=...).

The list was picked from the whole index in Nov 2026. Left out on purpose:
- Glacier's West Entrance (webcams-glac/WestEntrance.jpg): mt_511mt already carries it, from Montana 511.
- parking-lot views (Hurricane Ridge, Logan Pass, McKittrick, Devils Tower visitor centre), scenic views that happen to
  have a road in the distance (Elk Prairie, Bunker Hill, Alpine Visitor Center), a PTZ view park staff re-aim (St. Mary)
  and NPS entries that are copies of a DOT camera (AZ511, UDOT), which the state modules already have;
- inactive cameras with no still picture (Grand Teton's seasonal Teton Park Road camera, an eyetrax viewer).

The index's coordinates are a park default for a few cameras (Yellowstone's North Entrance carries the West
Entrance's, Beaver Meadows the Kawuneeche Valley's, Devils Tower's entrance views the tower's), so those are placed
here by hand. The run is from Wyoming (Yellowstone's East Entrance and Devils Tower's entrance road), but the cameras
span seven states."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "National Park Service (park webcams)",
    "state": ["WY", "MT", "CO", "AZ", "UT", "WA", "OR"],
    "covers": "National park entrance stations and park roads: Yellowstone, Devils Tower, Rocky Mountain, Black "
              "Canyon of the Gunnison, Grand Canyon, Arches, Zion, Mount Rainier and Crater Lake",
    "site": "https://www.nps.gov/media/multimedia-search.htm#sort=score+desc&fq%5B%5D=Type%3A%22Webcam%22",
    "terms": "https://www.nps.gov/aboutus/disclaimer.htm",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the Solr index behind nps.gov's multimedia search (robots.txt allows it). NPS's documented "
             "API (developer.nps.gov/api/v1/webcams) has the same webcams but needs a free api.data.gov key; not "
             "used. JPEG stills on www.nps.gov, most current to the minute (Grand Canyon and Devils Tower say every "
             "60 s); Zion's South Gate picture has been frozen since Sep 2025 although NPS lists it as active. NPS "
             "material is public domain unless marked otherwise (disclaimer). A curated subset: only the road and "
             "entrance views (17 of about 290 webcams).",
}
INDEX = "https://www.nps.gov/solr/"
FIELDS = "ID,Title,Status,Webcam_URL,Latitude,Longitude,Parks,Parks_Codes,PageURL"

# NPS webcam id -> what NPS's own title and description say about the road (approach in NPS's words), and
# fixes to the index.
ROADS = {
    # Wyoming
    "45FDA0AC-0A10-4ACA-A0C6-44F440575AE1": {"state": "WY", "approach": "Out of the park"},  # Yellowstone East Ent.
    "E3772256-9585-4859-A1FD-FC47F15F7226": {"state": "WY", "approach": "Into the park"},
    "AF525760-D248-7B9D-833CFB922312238E": {"state": "WY", "approach": "Exiting the park", "refresh": 60,
                                             "at": (44.58938, -104.70048)},  # Devils Tower entrance station
    "B350FEC9-B0A9-1A69-A42E3BF75F21E821": {"state": "WY", "approach": "Entering the park", "refresh": 60,
                                             "at": (44.58938, -104.70048)},
    # Montana (Yellowstone's North and West Entrances)
    "81B468BC-1DD8-B71B-0BBA4C383E179188": {"state": "MT", "approach": "Out of the park",
                                             "at": (45.02540, -110.70094)},  # North Entrance, Gardiner
    "81B468C8-1DD8-B71B-0BFE5983E4D2E421": {"state": "MT", "approach": "Out of the park"},
    "81B468D6-1DD8-B71B-0B9C2E324EF5F9F8": {"state": "MT", "approach": "Into the park"},
    # Colorado
    "81B46856-1DD8-B71B-0B8636427EFFC938": {"state": "CO", "road": "US 34", "direction": "East"},  # Fall River
    "81B4686B-1DD8-B71B-0B122CB864D072FC": {"state": "CO", "road": "US 36", "direction": "East",
                                             "at": (40.36662, -105.58110)},  # Beaver Meadows Entrance
    "3F33B673-957B-51DD-612B99E4A9FDF417": {"state": "CO", "road": "US 34", "direction": "South",
                                             "approach": "Entering the park"},  # Grand Lake Entrance
    "E7315AD6-834F-4731-848D-3903508DEE75": {"state": "CO", "direction": "West",
                                             "approach": "Incoming"},  # Black Canyon South Rim Entrance
    # Arizona, Utah
    "9B5FC6BA-9FE6-EC6B-61637825D562D367": {"state": "AZ", "refresh": 60},  # Grand Canyon South Entrance Station
    "81B46BDB-1DD8-B71B-0B250E8F4CC1E74A": {"state": "UT"},  # Arches Entrance Station, looking toward US 191
    "81B46CC4-1DD8-B71B-0B1B52AAF5930623": {"state": "UT"},  # Zion South Gate Entrance
    # Washington, Oregon
    "81B46445-1DD8-B71B-0BB0376A8482E275": {"state": "WA", "direction": "Southwest"},  # Mount Rainier, Longmire road
    "81B4628D-1DD8-B71B-0B183DA83E05154F": {"state": "OR", "road": "Munson Valley Road", "direction": "North"},
    "A790BA3E-D6C0-40E2-BB4B-56C3C23820E9": {"state": "OR", "road": "OR 62",  # Crater Lake Hwy at Munson Valley Rd
                                             # (the index's URL has "&mu" decoded to a Greek mu)
                                             "image": "https://www.nps.gov/webcams-crla/hwy62%26munson.jpg"},
}


def _image(url):
    """The picture's URL, percent-encoded where the index gives it raw (spaces, non-ASCII)."""
    return quote(url, safe=":/?=&%#~+,;@!$'()*") if url else None


def cameras(get, key=None):
    webcams = quote('Type:"Webcam"')
    ids = quote("ID:(" + " OR ".join(f'"{i}"' for i in ROADS) + ")")
    query = f"q=*:*&fq={webcams}&fq={ids}&fl={FIELDS}&wt=json&rows={len(ROADS) + 10}"
    docs = json.loads(get(f"{INDEX}?{query}"))["response"]["docs"]
    for doc in docs:
        road = ROADS.get(doc.get("ID"))
        if not road:
            continue
        image = road.get("image") or _image(doc.get("Webcam_URL"))
        if not image:
            continue
        lat, lon = road.get("at") or (doc.get("Latitude"), doc.get("Longitude"))
        park = doc.get("Parks") or ""
        camera = {
            "id": doc["ID"],
            "name": f"{park}: {doc.get('Title')}" if park else doc.get("Title"),
            "lat": lat,
            "lon": lon,
            "image": image,
            "state": road["state"],
            "online": doc.get("Status") == "Active",
            "extra": {"park": doc.get("Parks_Codes"),
                      "page": f"https://www.nps.gov/media/webcam/view.htm?id={doc['ID']}"},
        }
        for field in ("road", "direction", "approach", "refresh"):
            if road.get(field):
                camera[field] = road[field]
        yield camera
