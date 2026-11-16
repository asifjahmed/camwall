"""Georgia: the State Road and Tollway Authority's Peach Pass express-lane cameras (no key). Each of the four
"Real-Time Toll Rates" corridor pages on peachpass.com shows a map of the corridor's toll-price signs, and hovering over
a sign shows a still from the camera that watches it (JPEG on srtaivedds.com, the express lanes' toll system). Most of
these cameras frame the price sign with the lanes beneath; a few (I-85, Big Shanty Rd, Jonesboro Rd) show more road.
None of them is on 511GA.

The pages give only the picture's file name, placed on a drawing of the corridor, so each camera's position comes from
the table below: the milepost and direction printed in the picture's caption ("85A-093.5-CMS-CAM21-02": I-85,
milepost 93.5), placed by interpolating between the GDOT cameras on 511GA at the mileposts either side. Which cameras
are listed today comes from the site's own script, which sets every corridor page's popup pictures (the pages' HTML
carries placeholders); a camera that isn't in the table is left out."""

import re

SCRIPT = "https://peachpass.com/wp-content/themes/astra-child/js/ghPeachPass.js"  # sets each popup's picture
IMAGE = "https://srtaivedds.com/Images/Cameras/{}-00001.jpg"

SOURCE = {
    "name": "State Road and Tollway Authority (Peach Pass)",
    "state": "GA",
    "covers": "Metro Atlanta's express (toll) lanes: the Northwest Corridor (I-75/I-575), I-75 South Metro and I-85 "
              "Express Lanes, toll-price sign cameras",
    "site": "https://peachpass.com/real-time-toll-rates/",
    "terms": "https://peachpass.com/disclaimer/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the camera pictures the four Real-Time Toll Rates corridor pages show when a toll sign is "
             "hovered (img.cameraImg on srtaivedds.com), as the site's script (astra-child/js/ghPeachPass.js) sets "
             "them; the pages' HTML has placeholders (the I-85 page repeats one picture four times). JPEG stills, "
             "640x360 to 1920x1080, with the camera's name and time burned in; Last-Modified changes about every "
             "30 s (the pages add a time query to defeat the "
             "browser's cache; the server itself sends no Cache-Control). The cameras are there to verify the toll "
             "signs, so most show the sign over the lanes. Positions are not published: they are placed by the "
             "milepost in each camera's caption, interpolated between GDOT's 511GA cameras (to within a few hundred "
             "metres); the three on arterial ramps (Big Shanty Rd, Roswell Rd, Jonesboro Rd) are placed at the "
             "interchange. 75A-001.5 is taken to be on I-675 (the I-75 South Metro lanes' I-675 connection). "
             "peachpass.com sits behind Cloudflare, which served camwall's requests when this was written; its "
             "robots.txt asks for a 10 s crawl delay (the adapter makes one request). "
             "The disclaimer page has no restriction on use.",
}

# picture file stem -> (corridor, name, lat, lon, road, approach, county, caption)
CAMERAS = {
    # Northwest Corridor (I-75 and I-575, Cobb and Cherokee): reversible lanes
    "75B-011.0-CMS-CAM01": ("Northwest Corridor Express Lanes", "I-575 S Express Lanes sign at Sixes Rd",
                            34.14377, -84.51816, "I-575", "Southbound", "Cherokee", "75B-011.0-CMS-CAM21-01"),
    "75B-002.0-CMS-CAM01": ("Northwest Corridor Express Lanes", "I-575 S Express Lanes sign near Barrett Pkwy (MM 2)",
                            34.02888, -84.56054, "I-575", "Southbound", "Cobb", "75B-002.0-CMS-CAM01-01"),
    "75B-275.0-CMS-CAM01": ("Northwest Corridor Express Lanes", "I-75 S Express Lanes sign at Woodstock Rd (MM 275)",
                            34.07680, -84.62135, "I-75", "Southbound", "Cobb", "75B-275.0-CMS-CAM01-01"),
    "75B-256.9-CMS-CAM01": ("Northwest Corridor Express Lanes", "I-75 N Express Lanes sign near Mt Paran Rd (MM 256.9)",
                            33.87101, -84.44386, "I-75", "Northbound", "Fulton", "75B-256.9-CMS-CAM01-01"),
    "75B-BSH31-CMS-CAM31": ("Northwest Corridor Express Lanes", "Big Shanty Rd at the I-75 Express Lanes ramp",
                            34.02578, -84.57380, "Big Shanty Rd", None, "Cobb", "75B-BSH31-CMS-CAM31-01"),
    "75B-ROS31-CMS-CAM31": ("Northwest Corridor Express Lanes", "Roswell Rd at the I-75 Express Lanes ramp",
                            33.95096, -84.51592, "Roswell Rd", None, "Cobb", "75B-ROS-CMS-CAM31-01"),
    # I-75 South Metro (Henry and Clayton): reversible lanes
    "NEWCCTV1": ("I-75 South Metro Express Lanes", "I-75 N Express Lanes sign near SR 155 (MM 215.6)",
                 33.40595, -84.15522, "I-75", "Northbound", "Henry", "75A-215.6-CMS-CAM-01"),
    "NEWCCTV2": ("I-75 South Metro Express Lanes", "I-75 S Express Lanes sign near SR 138 (MM 228.6)",
                 33.54978, -84.28702, "I-75", "Southbound", None, "75A-228.6-CMS-CAM21-01"),
    "NEWCCTV3": ("I-75 South Metro Express Lanes", "I-675 S Express Lanes sign near SR 138 (MM 1.5)",
                 33.55616, -84.26952, "I-675", "Southbound", "Clayton", "75A-001.5-CMS-CAM21-01"),
    "NEWCCTV4": ("I-75 South Metro Express Lanes", "Jonesboro Rd at the I-75 Express Lanes ramp",
                 33.46218, -84.20685, "Jonesboro Rd", None, "Henry", "75A-JB048-CMS-CAM31-01"),
    # I-85 Express Lanes (DeKalb and Gwinnett): HOT lanes both ways
    "RSN1": ("I-85 Express Lanes", "I-85 N Express Lane sign near Chamblee Tucker Rd (MM 93.5)",
             33.87120, -84.28075, "I-85", "Northbound", "DeKalb", "85A-093.5-CMS-CAM21-02"),
    "RSN2": ("I-85 Express Lanes", "I-85 N Express Lane sign near Northcrest Rd (MM 96.3)",
             33.89979, -84.24697, "I-85", "Northbound", "DeKalb", "85A-096.3-CMS-CAM21-02"),
    "RSS1": ("I-85 Express Lanes", "I-85 S Express Lane sign near Old Peachtree Rd (MM 110.1)",
             34.01501, -84.06517, "I-85", "Southbound", "Gwinnett", "85A-110.1-CMS-CAM21-02"),
    "RSS2": ("I-85 Express Lanes", "I-85 S Express Lane sign near Beaver Ruin Rd (MM 102.7)",
             33.94276, -84.15041, "I-85", "Southbound", "Gwinnett", "85A-102.7-CMS-CAM21-02"),
    # I-85 Extension (Gwinnett)
    "CCTV1B": ("I-85 Extension Express Lanes", "I-85 N Express Lane sign near Sugarloaf Pkwy (MM 108.8)",
               33.99460, -84.07977, "I-85", "Northbound", "Gwinnett", "85B-108.8-CMS-CAM01-01"),
    "CCTV2B": ("I-85 Extension Express Lanes", "I-85 N Express Lane sign near McGinnis Ferry Rd (MM 110.7)",
               34.02333, -84.05726, "I-85", "Northbound", "Gwinnett", "85B-110.7-CMS-CAM01-01"),
    "CCTV3B": ("I-85 Extension Express Lanes", "I-85 S Express Lane sign near I-985 (MM 113.9)",
               34.05206, -84.01686, "I-85", "Southbound", "Gwinnett", "85B-113.9-CMS-CAM21-01"),
    "CCTV4B": ("I-85 Extension Express Lanes", "I-85 S Express Lane sign near Hamilton Mill Rd (MM 120.9)",
               34.07657, -83.89960, "I-85", "Southbound", "Gwinnett", "85B-120.9CMS-CAM21-01"),
}
PICTURE = re.compile(r"srtaivedds\.com/Images/Cameras/([A-Za-z0-9._-]+?)-00001\.jpg", re.I)


def _camera(stem):
    corridor, name, lat, lon, road, approach, county, caption = CAMERAS[stem]
    return {
        "id": stem,
        "name": name,
        "lat": lat,
        "lon": lon,
        "image": IMAGE.format(stem),
        "video": None,
        "road": road,
        "approach": approach,
        "county": county,
        "refresh": 30,
        "extra": {"corridor": corridor, "caption": caption,
                  "position": "at the interchange" if approach is None else "by milepost (approximate)"},
    }


def cameras(get, key=None):
    try:
        listed = list(dict.fromkeys(PICTURE.findall(get(SCRIPT).decode("utf-8", "replace"))))
    except OSError:
        listed = []
    known = [stem for stem in listed if stem in CAMERAS]
    for stem in known or CAMERAS:  # (the script couldn't be read or has changed: the cameras known here)
        yield _camera(stem)
