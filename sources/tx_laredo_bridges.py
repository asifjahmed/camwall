"""Texas: the City of Laredo's international bridge cameras, a view toward the US and a view toward Mexico on each of
its four bridges (Gateway to the Americas, Juarez-Lincoln, Colombia Solidarity, World Trade), as JPEG stills on
openlaredo.com. The list is fixed (the city's bridge camera page has no feed). Positions are the bridges' (from
Wikipedia), not each camera's."""

SOURCE = {
    "name": "City of Laredo Bridge System",
    "state": "TX",
    "covers": "Laredo's four international bridges to Nuevo Laredo",
    "site": "https://www.cityoflaredo.com/departments/bridge-system/bridge-cameras",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Stills, about 300-600 KB, refreshed about every 30 s. cityoflaredo.com (Akamai) refused requests when "
             "this was written, so the camera page and any terms on it couldn't be read; the picture URLs come from "
             "Port Laredo's border page (portlaredo.com/border-crossing) and the page's camera names, and all eight "
             "answer.",
}
BASE = "https://www.openlaredo.com/bridge/BridgeWebCamStills/{}.jpg"
BRIDGES = {
    1: ("Bridge 1 (Gateway to the Americas)", 27.4994, -99.50742),
    2: ("Bridge 2 (Juarez-Lincoln)", 27.500216, -99.502814),
    3: ("Bridge 3 (Colombia Solidarity)", 27.699716, -99.745646),
    4: ("Bridge 4 (World Trade)", 27.597291, -99.537119),
}


def cameras(get, key=None):
    for number, (name, lat, lon) in BRIDGES.items():
        for side, view in (("US", "view into US"), ("MEX", "view to Mexico")):
            yield {"id": f"bridge{number}{side}", "name": f"{name} {view}", "lat": lat, "lon": lon,
                   "image": BASE.format(f"bridge{number}{side}"), "city": "Laredo", "county": "Webb", "refresh": 30}
