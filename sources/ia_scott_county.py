"""Iowa: Scott County's webcams (scottcountyiowa.gov/webcams), keeping the one that shows a road: the Administrative
Center's rooftop camera looking south over downtown Davenport's streets towards the Centennial Bridge (US 67). The
county's other webcams are nature and park views (the Wapsi River Environmental Education Center's owl, bird
feeder, raptor and deck cameras; Glynns Creek golf clubhouse) and are left out."""

import re

SOURCE = {
    "name": "Scott County, Iowa",
    "state": "IA",
    "covers": "Downtown Davenport from the Scott County Administrative Center, looking south to the Centennial Bridge",
    "site": "https://www.scottcountyiowa.gov/webcams/admin-south",
    "terms": "https://www.scottcountyiowa.gov/disclaimer",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "The county's own webcam page; its picture is a JPEG still from latest.php (no-cache), stamped with its "
             "time, which changes every 5 minutes (11:20:02, then 11:25:02 local). The disclaimer is informational-use "
             "only, with nothing against apps or reuse. The list is the webcams page's own links; only the views "
             "named in ROADS are kept, since the rest show parks and wildlife.",
}
PAGE = "https://www.scottcountyiowa.gov/webcams"
IMAGE = "https://www3.scottcountyiowa.gov/webcams/latest.php?cam={}"
ROADS = {  # the webcams that show a road: slug -> (name, lat, lon, facing)
    "admin-south": ("Scott County Administrative Center looking south (downtown Davenport)",
                    41.523585, -90.58152, "South"),
}


def cameras(get, key=None):
    listed = set(re.findall(r'href="(?:https://www\.scottcountyiowa\.gov)?/webcams/([a-z0-9-]+)"',
                            get(PAGE).decode("utf-8", "replace")))
    for slug, (name, lat, lon, facing) in ROADS.items():
        if slug not in listed:  # (the county has taken it down)
            continue
        yield {
            "id": slug,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": IMAGE.format(slug),
            "video": None,
            "direction": facing,
            "city": "Davenport",
            "county": "Scott",
            "refresh": 300,
        }
