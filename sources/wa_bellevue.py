"""Bellevue: the City of Bellevue's traffic cameras, from the public ArcGIS layer its traffic map
(trafficmap.bellevuewa.gov) loads. Bellevue's own cameras are HLS video only (no still). The map also shows WSDOT's
I-405/SR 520 cameras and eight City of Redmond stills, which are left to wa_wsdot and wa_redmond. A camera is known by
its id in the layer ("CCTV174")."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "City of Bellevue Transportation",
    "state": "WA",
    "covers": "City of Bellevue arterials",
    "site": "https://trafficmap.bellevuewa.gov/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "The layer is public (services1.arcgis.com/EYzEZbDhXZjURPbP/.../TrafficCameras_Public_View) but "
             "undocumented. Bellevue's cameras are unsigned HLS (640x360) with no still picture; the map stops video "
             "after about 30 s. Some listed streams answer 404 (cameras down). No terms of use are posted on the map.",
}
LIST = ("https://services1.arcgis.com/EYzEZbDhXZjURPbP/ArcGIS/rest/services/TrafficCameras_Public_View/FeatureServer/0/"
        "query?where=" + quote("Media <> 'None'") + "&outFields=*&orderByFields=ESRI_OID&returnGeometry=true&f=json"
        "&outSR=4326&resultRecordCount=1000&resultOffset={offset}")
VIDEO = "https://trafficcams.bellevuewa.gov/traffic-edge/{id}L.stream/playlist.m3u8"


def cameras(get, key=None):
    seen, offset = set(), 0
    while True:
        page = json.loads(get(LIST.format(offset=offset)))
        features = page.get("features") or []
        for f in features:
            a, g = f.get("attributes") or {}, f.get("geometry") or {}
            owner, media, cid = a.get("OwnedBy"), a.get("Media"), (a.get("ID") or "").strip()
            if not cid or owner in ("WSDOT", "Redmond"):  # in wa_wsdot and wa_redmond
                continue
            lat, lon = a.get("Latitude") or g.get("y"), a.get("Longitude") or g.get("x")
            name = " ".join((a.get("Display_Address") or a.get("Address") or cid).split())
            if media == "Stream":
                cam = {"id": cid.upper(), "video": VIDEO.format(id=quote(cid.upper())), "video_type": "hls",
                       "city": "Bellevue"}
            else:
                continue
            if cam["id"] in seen:
                continue
            seen.add(cam["id"])
            yield {**cam, "name": name, "lat": float(lat), "lon": float(lon),
                   "extra": {k: v for k, v in {"owner": owner, "type": a.get("CameraType")}.items() if v}}
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
