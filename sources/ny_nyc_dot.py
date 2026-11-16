"""New York City: NYC DOT's cameras, from the camera list its webcams.nyctmc.org map serves (no key). Stills only,
which NYC DOT says change about every 15 s. 511NY (ny_511ny) shows the same cameras, plus about a hundred more NYC DOT
ones this list leaves out."""

import json

SOURCE = {
    "name": "NYC DOT",
    "state": "NY",
    "covers": "New York City's five boroughs: highways, bridges and major arterials",
    "site": "https://webcams.nyctmc.org/map",
    "terms": "https://webcams.nyctmc.org/subscribers",
    "key": None,
    "headers": {},
    "restricted": "\"Developers wishing to access the cameras via a data feed, must sign a data-sharing agreement\" "
                  "(https://webcams.nyctmc.org/api/cameras/subscriber-api-agreement, emailed to TMCDOT@dot.nyc.gov); "
                  "the agreement asks that the pictures be credited to NYC DOT and allows \"direct links to the "
                  "Department's web services\" but not copying them to the user's site. nyc.gov's terms: "
                  "https://www.nyc.gov/home/terms-of-use.page",
    "notes": "Undocumented: the list behind the map (also /cameras/graphql). NYC DOT asks developers to fetch the "
             "list about once a day and not to ask for a picture more often than every 15 s.",
}
LIST = "https://webcams.nyctmc.org/api/cameras"


def cameras(get, key=None):
    for cam in json.loads(get(LIST)):
        if not cam.get("id") or not cam.get("latitude") or not cam.get("longitude"):
            continue
        yield {
            "id": cam["id"],
            "name": cam.get("name") or "Camera",
            "lat": float(cam["latitude"]),
            "lon": float(cam["longitude"]),
            "image": cam.get("imageUrl") or f"https://webcams.nyctmc.org/api/cameras/{cam['id']}/image",
            "city": "New York",
            "county": {"Manhattan": "New York", "Brooklyn": "Kings", "Staten Island": "Richmond"}.get(
                cam.get("area"), cam.get("area")),
            "refresh": 15,
            "online": str(cam.get("isOnline")).lower() != "false",
            "extra": {"borough": cam.get("area")},
        }
