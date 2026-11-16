"""Kansas: the City of Manhattan's intersection cameras, from the ArcGIS layer behind the City's "Public Traffic Camera
Viewer" (no key). Each camera's still is a JPEG in the City's SharePoint library (mhkGIS/Traffic_Cameras), overwritten
every few minutes, and the layer links it with an "anyone with the link" share URL. That URL only sets a session cookie
and redirects, so the picture is taken from SharePoint's own download address for the same share,
_layouts/15/download.aspx?share=<token>, which answers with the JPEG itself. A camera is known by the layer's globalid."""

import json
import re

SOURCE = {
    "name": "City of Manhattan Traffic",
    "state": "KS",
    "covers": "City of Manhattan (Riley County) signalized intersections",
    "site": "https://cityofmhk.maps.arcgis.com/apps/instant/basic/index.html?appid=7519481a8c50425f9d97a73395580eb1",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "ArcGIS FeatureServer Traffic_Cameras_view (layer 0), the layer of the City's Public Traffic Camera Viewer "
             "(\"Allows the public to view still images from intersections around town\"); its camlink field is a "
             "SharePoint anonymous share link. Pictures (320x240 to 1920x1080 JPEG, Axis cameras with a time overlay) "
             "come from SharePoint's download.aspx?share=<token>, with no cookie or key. They are replaced every few "
             "minutes; one (10th & K-18) was frozen at 16 Sep 2026 when checked on 8 Nov 2026. The City's website "
             "(cityofmhk.com) reset the connection when this was written, so its terms could not be read.",
}
LAYER = ("https://services.arcgis.com/rFQQFFw3jz8ox3VY/arcgis/rest/services/Traffic_Cameras_view/FeatureServer/0/query"
         "?where=1%3D1&outFields=*&outSR=4326&orderByFields=objectid&f=json&resultOffset=")
DOWNLOAD = "https://manhattanks.sharepoint.com/sites/mhkGIS/_layouts/15/download.aspx?share={}"
SHARE = re.compile(r"^https://manhattanks\.sharepoint\.com/:i:/s/mhkGIS/([A-Za-z0-9_-]+)")


def cameras(get, key=None):
    offset = 0
    while True:
        body = json.loads(get(LAYER + str(offset)))
        if body.get("error"):
            raise OSError(f"Manhattan's layer said {body['error']}")
        features = body.get("features") or []
        for feature in features:
            a, g = feature.get("attributes") or {}, feature.get("geometry") or {}
            share = SHARE.match((a.get("camlink") or "").strip())
            if not share or g.get("x") is None:
                continue
            ew, ns = (a.get("e_w_street") or "").strip(), (a.get("n_s_street") or "").strip()
            yield {
                "id": a.get("globalid") or share.group(1),
                "name": (a.get("intsctname") or f"{ew} - {ns}").strip(),
                "lat": g["y"],
                "lon": g["x"],
                "image": DOWNLOAD.format(share.group(1)),
                "road": ew or None,
                "city": "Manhattan",
                "extra": {k: v for k, v in {"cross_street": ns, "share": share.group(1)}.items() if v},
            }
        if not body.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
