"""Texas: the City of Austin's low-water-crossing cameras on ATXFloods (atxfloods.com, no key), the flooded-road site the
City's Watershed Protection Department runs with CAPCOG and the Central Texas counties. Each camera looks at a road
where it crosses a creek (or the gate arm that closes it), so it shows whether the road is under water. The cameras and
the site are Beholder Technology's platform. Stills only, a new one about every 3 minutes; each still has its own file
name, so the list gives the newest at the time and resolve() asks the list again for the current one."""

import json

SOURCE = {
    "name": "ATXFloods (City of Austin Watershed Protection)",
    "state": "TX",
    "covers": "City of Austin low-water crossings and flood-prone road crossings",
    "site": "https://atxfloods.com/cameras",
    "terms": "https://atxfloods.com/terms",
    "key": None,
    "headers": {},
    "restricted": "The site's terms (Beholder Technology's Terms of Use) prohibit \"copying, distributing, or disclosing "
                  "any part of the Service in any medium, including without limitation by any automated or "
                  "non-automated 'scraping'\".",
    "notes": "Undocumented: api.atxfloods.com/api/cameras, the list the site's camera map loads; each camera carries its "
             "last six stills (2048x1536 JPEG, about 350 KB, a new one about every 3 minutes, file names that change "
             "with each still), so image is the newest when listed and resolve() gives the current one. Crossing "
             "closures are at api/closures. A few cameras sit near City of Austin signal cameras (tx_austin), but "
             "they look at the crossings, not the intersections.",
}
LIST = "https://api.atxfloods.com/api/cameras"
IMAGE = "https://api.atxfloods.com/uploads/{}"


def _newest(cam):
    images = [i for i in cam.get("images") or [] if i.get("image_name")]
    if not images:
        return None
    return IMAGE.format(max(images, key=lambda i: i.get("created_at") or "")["image_name"])


def _list(get):
    body = json.loads(get(LIST))
    if body.get("status") not in (200, "200", None):
        raise OSError(f"ATXFloods said {body.get('message')}")
    return body.get("attributes") or []


def _id(cam):
    return str(cam.get("unique_id") or cam.get("id") or "").strip()


def cameras(get, key=None):
    for cam in _list(get):
        try:
            lat, lon = float(cam["lat"]), float(cam["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        cam_id, image = _id(cam), _newest(cam)
        if not cam_id or not image:
            continue
        yield {
            "id": cam_id,
            "name": (cam.get("name") or cam_id).strip(),
            "lat": lat,
            "lon": lon,
            "image": image,
            "city": "Austin" if cam.get("jurisdiction") == "COA" else None,
            "refresh": 180,
            "online": cam.get("display_status") is not False,
            "extra": {k: v for k, v in {"jurisdiction": cam.get("jurisdiction"), "address": cam.get("address"),
                                        "list_id": cam.get("id")}.items() if v not in (None, "")},
        }


def resolve(get, camera, key=None):
    for cam in _list(get):
        if _id(cam) == camera["id"]:
            return {"image": _newest(cam), "video": None}
    return {"image": None, "video": None}
