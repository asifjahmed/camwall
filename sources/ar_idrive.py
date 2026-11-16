"""Arkansas: ARDOT's cameras on IDrive Arkansas, from the camera layer its map loads (no key), with stills from
layers.idrivearkansas.com/cameras/<id>.jpg (a PNG, despite the name). The video (HLS on cdn.idrivearkansas.com) needs
CloudFront signed cookies that the site sets for its own player, which the contract can't carry, so it is left out.
The layer includes partner cameras (cities, neighbouring states, TV stations) that ARDOT shows."""

import json
import time

SOURCE = {
    "name": "ARDOT (IDrive Arkansas)",
    "state": "AR",
    "covers": "Arkansas interstates and highways statewide, with partner city cameras",
    "site": "https://www.idrivearkansas.com/",
    "terms": "https://site.idrivearkansas.com/index.php/policies/camera-terms-of-use/",
    "key": None,
    "headers": {},
    "restricted": "\"Embedding live camera images or the IDrive Arkansas site in another web site or application (app) "
                  "is prohibited. End-users may not directly or indirectly link to any camera from another web site "
                  "or app. End-users are prohibited from building a web page or app that contains links to any camera "
                  "and marketing that page or app as a traffic camera feature.\" Screen captures must keep the camera "
                  "owner's logo.",
    "notes": "Undocumented: layers.idrivearkansas.com/cameras.geojson, the layer the map loads. Stills (720x405 PNG) "
             "refreshed about every 20 minutes, some much older; the site's still endpoint "
             "(actis.idrivearkansas.com/index.php/api/cameras/image?camera=<id>) redirects to the same file. HLS "
             "video exists but needs CloudFront signed cookies (Key-Pair-Id), so it isn't given. direction is the "
             "camera's default direction as ARDOT lists it.",
}
LAYER = "https://layers.idrivearkansas.com/cameras.geojson?v={}"
IMAGE = "https://layers.idrivearkansas.com/cameras/{}.jpg"


def cameras(get, key=None):
    for feature in json.loads(get(LAYER.format(int(time.time())))).get("features") or []:
        props, geometry = feature.get("properties") or {}, feature.get("geometry") or {}
        if geometry.get("type") != "Point" or props.get("id") is None:
            continue
        lon, lat = geometry["coordinates"][:2]
        route = " ".join(p for p in (props.get("route_type_abbr"), props.get("route")) if p) or None
        yield {
            "id": str(props["id"]),
            "name": (props.get("name") or str(props["id"])).strip(),
            "lat": float(lat),
            "lon": float(lon),
            "image": IMAGE.format(props["id"]),
            "road": route,
            "direction": props.get("direction_name") or None,
            "online": props.get("status") != "disabled",
            "extra": {k: v for k, v in {"ardot_number": props.get("ahtd_camera_number"), "status": props.get("status"),
                                        "primary": props.get("primary"), "model": props.get("camera")}.items()
                      if v is not None},
        }
