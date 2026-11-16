"""Montana: MDT's cameras from Montana 511 (511mt.net, Iteris' ClearRoute platform). Nearly all of MDT's public cameras
are on its road-weather (RWIS) stations, each with two to five views (the road each way and the road surface); the 511
map loads them as the RWIS layer (icons.rwis.geojson). Each view is a camera, known by MDT's view id. The same 422
views are on MDT's own ATMS pages (app.mdt.mt.gov/atms/public/cameras), but under picture names that change with
every capture; 511's are stable.

511's separate "cameras" layer (icons.cameras.geojson) holds only other agencies' cameras near Montana: neighbouring
states', Alberta's, and the National Park Service's at park entrances. Only the park cameras in Montana are kept here
(Glacier's West Entrance, Yellowstone's North Entrance); the rest come from their own states' sources. Both are copies
of NPS's own webcam pictures (same camera, a few minutes later): Glacier's is the West Entrance station road
(nps.gov/webcams-glac/WestEntrance.jpg); Yellowstone's "North Entrance" is NPS's "North Entrance - Electric Peak"
view (nps.gov/webcams-yell/mammoth_electric.jpg), a mountain view with no road in it. Their NPS picture is in
extra["nps_image"], so a national NPS source can skip them.

MDT also documents an RWIS API (app.mdt.mt.gov/atms/api, "MDT ATMS Road Weather Service REST API"), with the same
stations' pictures; it needs a key MDT gives out on request by email (mdtrwis@mt.gov). The keyless 511 feed carries the
same 422 views, so it isn't used."""

import json

SOURCE = {
    "name": "MDT (Montana 511)",
    "state": "MT",
    "covers": "Montana's interstates and highways statewide: MDT's road-weather station cameras, plus two National "
              "Park entrance cameras",
    "site": "https://www.511mt.net/",
    "terms": "https://www.mdt.mt.gov/mdt/terms-of-use.aspx",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented GeoJSON the 511 map loads from Iteris' CDN. JPEG stills, refreshed about every 15 minutes "
             "(cache max-age 120). MDT's terms let anyone 'view, copy, or distribute information ... for personal or "
             "informational use' if not modified. MDT records no video and publishes no urban traffic cameras. "
             "MDT's documented ATMS RWIS API (app.mdt.mt.gov/atms/api) has the same pictures but needs a key "
             "requested by email; not used. The Yellowstone 'North Entrance' camera is NPS's Electric Peak view "
             "(no road in frame).",
}
RWIS = "https://mt.cdn.iteris-atis.com/geojson/icons/metadata/icons.rwis.geojson"
OTHER = "https://mt.cdn.iteris-atis.com/geojson/icons/metadata/icons.cameras.geojson"
PARKS = ("Glacier National Park", "Yellowstone National Park - North Entrance")  # the park cameras in Montana
NPS_IMAGE = {  # 511's park cameras' own NPS pictures (checked Nov 2026: same Axis camera, same framing)
    "5549-1": "https://www.nps.gov/webcams-glac/WestEntrance.jpg",
    "5550-1": "https://www.nps.gov/webcams-yell/mammoth_electric.jpg",
}


def _direction(text):
    for word in ("North", "South", "East", "West"):
        if (text or "").startswith(word):
            return word
    return None


def cameras(get, key=None):
    for feature in json.loads(get(RWIS)).get("features") or []:
        props = feature.get("properties") or {}
        lon, lat = (feature.get("geometry") or {}).get("coordinates") or (None, None)
        for view in props.get("cameras") or []:
            if not view.get("image"):
                continue
            camera = {
                "id": view["id"],
                "name": view.get("name") or f"{props.get('name')} - {view.get('description')}",
                "lat": lat,
                "lon": lon,
                "image": view["image"],
                "refresh": 900,
                "extra": {"site": feature.get("id"), "site_name": props.get("name"), "where": props.get("description"),
                          "view": view.get("description"), "mdt_area": props.get("area") or None},
            }
            if props.get("route"):
                camera["road"] = props["route"]
            if _direction(view.get("description")):
                camera["direction"] = _direction(view["description"])
            yield camera
    for feature in json.loads(get(OTHER)).get("features") or []:
        props = feature.get("properties") or {}
        if not (props.get("description") or "").startswith(PARKS):
            continue
        lon, lat = (feature.get("geometry") or {}).get("coordinates") or (None, None)
        for view in props.get("cameras") or []:
            if view.get("image"):
                yield {
                    "id": view["id"],
                    "name": props["description"].strip(),
                    "lat": lat,
                    "lon": lon,
                    "image": view["image"],
                    "extra": {"owner": "National Park Service", "nps_image": NPS_IMAGE.get(view["id"])},
                }
