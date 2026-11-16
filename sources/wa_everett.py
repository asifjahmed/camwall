"""Everett: the City of Everett's traffic cameras, JPEG stills on coe.everettwa.gov/Broadway/Images/<camera>/. The
city's "All Everett Traffic Cameras" page (everettwa.gov/2937) shows them as pictures; when it can be read, the cameras
are the ones it shows. everettwa.gov answered with a Cloudflare block when this was written, so when the
page can't be read the cameras are those in LOCATIONS: the 44 pictures the page and the city's camera map
(everettwa.gov/1634) showed in their December 2025 and February 2026 copies, each confirmed on coe.everettwa.gov in
November 2026. The pages give no coordinates: LOCATIONS places each intersection where the two streets' centerlines
cross in Snohomish County's public NG911 street layer (gis.snoco.org SAS_Streets). A camera is known by its picture's
folder name ("Evergreen_Casino")."""

import re

SOURCE = {
    "name": "City of Everett Public Works (Traffic)",
    "state": "WA",
    "covers": "City of Everett arterials: Evergreen Way, Pacific Ave, Broadway, Rucker Ave, Airport Rd, Merrill Creek "
              "Pkwy, Seaway Blvd, 75th St SW",
    "site": "https://www.everettwa.gov/2937/All-Everett-Traffic-Cameras",
    "terms": "https://www.everettwa.gov/Copyright",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the city's camera page, read as HTML when it can be; otherwise the table of cameras built "
             "into this module. Pictures are JPEG stills that change every one to two minutes. In November 2026 six "
             "cameras (Evergreen Way at 47th, 75th and Everett Mall Way, Merrill Creek Pkwy at Hardeson, Pacific at "
             "Wetmore, Colby at 41st) showed the city's 'This image is not available' picture and 75th St SW at the "
             "PUD had not changed since July 2025. The city's terms (everettwa.gov/Copyright) could not be read when "
             "this was written.",
}
PAGE = "https://www.everettwa.gov/2937/All-Everett-Traffic-Cameras"
IMAGES = "https://coe.everettwa.gov/Broadway/Images/"
LOCATIONS = {  # picture folder -> (picture file, name as the city's camera list gives it, lat, lon)
    "WMVD_18th": ("WMVD_18th.jpg", "W Marine View Drive-18th St", 47.99423, -122.213837),
    "Broadway_Everett": ("Broadway_Everett.jpg", "Broadway-Everett Ave", 47.9819, -122.201495),
    "Broadway_Hewitt": ("Broadway_Hewitt.jpg", "Broadway-Hewitt Ave", 47.979228, -122.201537),
    "Hewitt_Colby1": ("Hewitt_Colby1.jpg", "Hewitt Ave-Colby Ave #1", 47.979294, -122.208625),
    "Hewitt_Colby2": ("Hewitt_Colby2.jpg", "Hewitt Ave-Colby Ave #2", 47.979294, -122.208625),
    "Hewitt_Cedar": ("Hewitt_Cedar.jpg", "Hewitt Ave-Cedar St", 47.979123, -122.193842),
    "Broadway_Pacific": ("Broadway_Pacific.jpg", "Broadway-Pacific Ave", 47.976678, -122.201483),
    "Pacific_WMVD": ("Pacific_WMVD.jpg", "Pacific Ave-W Marine View Dr", 47.976435, -122.214189),
    "Pacific_Grand": ("Pacific_Grand.jpg", "Pacific Ave-Grand Ave", 47.976465, -122.21283),
    "Pacific_Rucker": ("Pacific_Rucker.jpg", "Pacific Ave-Rucker Ave", 47.976483, -122.211344),
    "Pacific_Hoyt": ("Pacific_Hoyt.jpg", "Pacific Ave-Hoyt Ave", 47.976514, -122.209942),
    "Pacific_Colby": ("Pacific_Colby.jpg", "Pacific Ave-Colby Ave", 47.976545, -122.20852),
    "Pacific_Wetmore": ("Pacific_Wetmore.jpg", "Pacific Ave-Wetmore Ave", 47.976583, -122.207119),
    "Pacific_Oakes": ("Pacific_Oakes.jpg", "Pacific Ave-Oakes Ave", 47.976631, -122.204325),
    "Pacific_Smith": ("Pacific_Smith.jpg", "Pacific Ave-Smith Ave", 47.976749, -122.198488),
    "Smith_33rd": ("Smith_33rd.jpg", "Smith Ave-33rd St", 47.974119, -122.1977),
    "Rucker_35th": ("Rucker_35th.jpg", "Rucker Ave-35th St", 47.971216, -122.211145),
    "Rucker_37th": ("Rucker_37th.jpg", "Rucker Ave-37th St", 47.968571, -122.211042),
    "Rucker_41st": ("Rucker_41st.jpg", "Rucker Ave-41st St", 47.963264, -122.210839),
    "Colby_41st": ("Colby41st.jpg", "Colby Ave-41st St", 47.963326, -122.207947),
    "Evergreen_47th": ("Evergreen_47th.jpg", "Evergreen Way-47th St SE", 47.95527, -122.213033),
    "Evergreen_52nd": ("Evergreen_52nd.jpg", "Evergreen Way-52nd St SE", 47.949422, -122.2145),
    "Evergreen_Pecks": ("Evergreen_Pecks.jpg", "Evergreen Way-Pecks Dr", 47.941732, -122.217575),
    "MCPkwy_Hardeson": ("MCPkwyHardeson.jpg", "Merrill Creek Pkwy-Hardeson Rd", 47.942686, -122.256095),
    "MCPkwy_23rd": ("MCPkwy23rd.jpg", "Merrill Creek Pkwy-23rd Dr W", 47.941143, -122.263701),
    "MCPkwy_Seaway": ("MCPkwySeaway.jpg", "Seaway Blvd-Merrill Creek Pkwy", 47.937104, -122.267851),
    "Evergreen_Madison": ("Evergreen_Madisn.jpg", "Evergreen Way-Madison St", 47.936235, -122.219032),
    "Evergreen_75th": ("Evergreen_75th.jpg", "Evergreen Way-75th St SE", 47.930139, -122.220787),
    "Seaway_75th": ("Seaway75th.jpg", "Seaway Blvd-75th St SW", 47.930975, -122.260782),
    # (a driveway on 75th St SW between Seaway Blvd and Hardeson Rd; placed halfway between them)
    "75thStSW_PUD": ("75thStSW_PUD.jpg", "75th St SW-PUD-Seaway Transit Center", 47.930402, -122.254126),
    "Hardeson_75th": ("Hardeson75th.jpg", "Hardeson Rd-75th St SW", 47.92983, -122.247471),
    "Evergreen_79th": ("Evergreen_79th.jpg", "Evergreen Way-79th Pl SE", 47.925977, -122.224311),
    "Evergreen_Casino": ("Evergreen_Casino.jpg", "Evergreen Way-Casino Rd", 47.921948, -122.228066),
    "Casino_5th": ("Casino_5th.jpg", "Casino Rd-5th Ave W", 47.921832, -122.240499),
    "Airport_Casino": ("Airport_Casino.jpg", "Airport Rd-W Casino Rd", 47.920055, -122.271679),
    "Airport_KaschPark": ("Airport_KaschPk.jpg", "Airport Rd-Kasch Park Rd", 47.918278, -122.271672),
    "Evergreen_Holly": ("Evergreen_Holly.jpg", "Evergreen Way-Holly Dr", 47.916933, -122.23278),
    "Evergreen_4th": ("Evergreen_4th.jpg", "Evergreen Way-4th Ave W", 47.910185, -122.239029),
    "Evergreen_100th": ("Evergreen_100th.jpg", "Evergreen Way-100th St SW", 47.907335, -122.241706),
    "Evergreen_EverettMallWay": ("Evergreen_EMWay.jpg", "Evergreen Way-Everett Mall Way", 47.904191, -122.244618),
    "Airport_106th": ("Airport_106th.jpg", "Airport Rd-106th St SW", 47.901999, -122.267503),
    "Evergreen_112th": ("Evergreen_112th.jpg", "Evergreen Way-112th St SW", 47.896452, -122.251808),
    "Airport_112th": ("Airport_112th.jpg", "Airport Rd-112th St SW", 47.896508, -122.263507),
    "Evergreen_Airport": ("Evergreen_Airprt.jpg", "Evergreen Way-Airport Rd", 47.88942, -122.258442),
}
PICTURE = re.compile(r'https://coe\.everettwa\.gov/Broadway/Images/([^/"\'?\s]+)/([^/"\'?\s]+\.jpg)', re.I)


def _from_page(get):
    """The (folder, file) of each picture the city's page shows, or None if the page can't be read."""
    try:
        page = get(PAGE).decode("utf-8", errors="replace")
    except OSError:
        return None
    found = PICTURE.findall(page)
    return found or None


def cameras(get, key=None):
    folders = {k.lower(): k for k in LOCATIONS}
    shown = _from_page(get)
    if shown is None:
        shown = [(folder, entry[0]) for folder, entry in LOCATIONS.items()]
    seen = set()
    for folder, picture in shown:
        cid = folders.get(folder.lower())
        if cid is None or cid in seen:  # (a camera new to the page isn't placed yet)
            continue
        seen.add(cid)
        _, name, lat, lon = LOCATIONS[cid]
        yield {
            "id": cid,
            "name": name,
            "lat": lat,
            "lon": lon,
            "image": f"{IMAGES}{folder}/{picture}",
            "city": "Everett",
            "refresh": 120,
        }
