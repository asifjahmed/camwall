"""Oklahoma: ODOT's cameras on OKTraffic, from the camera-pole list its map loads (no key). A pole carries several
cameras, one per direction ("I-44 & S59th S"); each is a camera here, known by ODOT's camera id. Live HLS video from
ODOT's Wowza server. Oklahoma City, Tulsa, Lawton and the interstates between them, with work-zone trailer cameras.

The API is LoopBack; the map sends its query as a "filter" header. This asks for the same public cameras (type "Web",
not blocked from traveler information) but keeps the ones marked "Out Of Service", which the map hides, so they can
be listed as out of service.

Stills: ODOT's winter road-conditions map (okroads.org) shows a JPEG of some of these cameras, by the same camera id,
at pics.okroads.org/files/camera-pictures/<id>.jpg, renewed every 5 minutes. Its camera layer (HighwayCamera_prod_
ViewLayer) lists them only in winter, so the ids that had a picture when this was written are kept here as well; a
camera gets an image if it is in either."""

import json

SOURCE = {
    "name": "ODOT (OKTraffic)",
    "state": "OK",
    "covers": "Oklahoma interstates and highways: Oklahoma City, Tulsa, Lawton, Norman and work zones",
    "site": "https://oktraffic.org/#/map",
    "terms": "https://oktraffic.org/#/static/terms",
    "key": None,
    "headers": {},
    "restricted": "\"In using this website, you agree not to capture or record images for litigation purposes, and you "
                  "agree not to hot link to images on this website.\"",
    "notes": "Undocumented: oktraffic.org/api/CameraPoles with a LoopBack filter header, as the map sends it. Untokenized "
             "HLS (800x600, delayed). About 64 cameras also have a JPEG still (renewed every 5 minutes) from ODOT's "
             "okroads.org winter map, at pics.okroads.org. direction is the way the camera looks, as ODOT labels it. "
             "ODOT also has CCTV and security cameras that the public site doesn't show; they're left out.",
}
LIST = "https://oktraffic.org/api/CameraPoles"
FILTER = {"include": [{"relation": "mapCameras", "scope": {"include": "streamDictionary",
                                                         "where": {"type": "Web", "blockAtis": {"neq": "1"}}}}]}
OKROADS = ("https://services.arcgis.com/268FQVIBhnf3Eunr/arcgis/rest/services/HighwayCamera_prod_ViewLayer/FeatureServer/"
           "0/query?where=status%3D%271%27&outFields=id&returnGeometry=false&f=json")
PICTURE = "https://pics.okroads.org/files/camera-pictures/{}.jpg"
# Camera ids with a picture on pics.okroads.org on 2026-11-08 (56 current, 8 old ones on out-of-service cameras).
STILLS = set("""2 4 5 7 8 9 56 57 58 59 66 68 71 72 73 1103130967 1103131100 1103131149 1103132905 1103132951 1103133002
1103133056 1103135247 1103135287 1103135353 1103135396 1103136698 1103136748 1103136797 1103136848 1107353688 1107353748
1107353810 1122644194 1122644273 1122644327 1122644383 1122644623 1122644671 1122644713 1122644756 1170778130 1170778297
1379329604 1379329640 1379329682 1465895926 1465895972 1465896014 1465896062 1524059833 1524059912 1524059946 1554912544
1554912584 1554912618 1554912656 1704398136452 1756153696970 1756153778314 1756156249416 1756156352288 1756156439882
1756156560157""".split())


def okroads_ids(get):
    """The camera ids okroads.org lists with a picture now (none out of winter, or if the layer can't be read)."""
    try:
        features = json.loads(get(OKROADS)).get("features") or []
    except (OSError, ValueError):
        return set()
    return {str(f["attributes"]["id"]) for f in features if (f.get("attributes") or {}).get("id")}


def cameras(get, key=None):
    poles = json.loads(get(LIST, headers={"filter": json.dumps(FILTER, separators=(",", ":"))}))
    stills = STILLS | okroads_ids(get)
    for pole in poles:
        for cam in pole.get("mapCameras") or []:
            stream = (cam.get("streamDictionary") or {}).get("streamSrc")
            try:
                lat, lon = float(cam["latitude"]), float(cam["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            if not stream or not lat or not lon or cam.get("type") != "Web" or str(cam.get("blockAtis")) == "1":
                continue
            still = str(cam["id"]) in stills
            yield {
                "id": str(cam["id"]),
                "name": (cam.get("location") or pole.get("name") or str(cam["id"])).strip(),
                "lat": lat,
                "lon": lon,
                "image": PICTURE.format(cam["id"]) if still else None,
                "video": stream,
                "video_type": "hls",
                "direction": cam.get("direction") or None,
                "city": (cam.get("city") or "").strip() or None,
                "refresh": 300 if still else None,
                "online": cam.get("status") != "Out Of Service",
                "extra": {"pole": pole.get("name"), "pole_id": pole.get("id"), "status": cam.get("status")},
            }
