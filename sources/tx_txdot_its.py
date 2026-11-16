"""Texas: TxDOT's cameras on its.txdot.gov, the district ITS pages TxDOT's own "live traffic cameras" page links to (no
key). The list is the 25 district camera lists (the statewide map's own camera layer, Map/GetIconModelsOfType, comes
and goes: 4,101 cameras one minute, 10 the next). Each gives the roadway, its direction and whether the camera is
online. It has several hundred cameras DriveTexas (tx_drivetexas) lacks, among them Harris County's and Beaumont's
arterial cameras. A district's list sometimes comes back short (Austin's gave 22 cameras once, 283 the next run), so
the statewide layer, when it answers in full, is used as a check: a district near cameras it has and the lists lack is
asked again.

The stills are not served as pictures: GetCctvSnapshotByIcdId answers JSON whose "snippet" is the JPEG in base64. So
`image` here is that JSON URL, and SOURCE["image_json"] tells the app the picture is its "snippet"."""

import json
from urllib.parse import quote, urlencode

SOURCE = {
    "name": "TxDOT (its.txdot.gov)",
    "state": "TX",
    "covers": "Texas state highways in all TxDOT districts, with Houston-area county arterials",
    "site": "https://its.txdot.gov/its/map",
    "terms": "https://www.txdot.gov/about/disclaimer.html",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the lists its.txdot.gov's map and district pages load. Stills only, refreshed every few "
             "minutes, and delivered as base64 inside JSON (image is that JSON URL, and image_json names the field holding the picture). "
             "direction is the roadway direction the district lists the camera under, not checked against the "
             "pictures. Most cameras are also on DriveTexas (tx_drivetexas, video) under other ids.",
    "image_json": "snippet",
}
BASE = "https://its.txdot.gov/its/"
DISTRICTS = ("ABL AMA ATL AUS BMT BRY BWD CHS CRP DAL ELP FTW HOU LBB LFK LRD ODA PAR PHR SAT SJT TYL WAC WFS "
             "YKM").split()


def _snapshot_url(icd_id):
    return BASE + "DistrictIts/GetCctvSnapshotByIcdId?" + urlencode({"icdId": icd_id, "districtCode": icd_id},
                                                                     quote_via=quote)


def _district(get, district):
    body = json.loads(get(BASE + "DistrictIts/GetCctvStatusListByDistrict?districtCode=" + district))
    return [info for road in (body.get("roadwayCctvStatuses") or {}).values() for info in road
            if info.get("icd_Id") and info.get("latitude") is not None]


def _short_districts(get, found):
    """The districts whose lists look short: those nearest the statewide layer's cameras that no list has, and those
    that gave nothing. found maps each district to its cameras. None when the statewide layer isn't usable."""
    try:
        layer = json.loads(get(BASE + "Map/GetIconModelsOfType?type=camera"))
    except (OSError, ValueError):
        return None
    if not isinstance(layer, list) or len(layer) < 1000:  # (it sometimes answers with a handful)
        return None
    names = {(info.get("name") or "").strip() for infos in found.values() for info in infos}
    points = [(info["latitude"], info["longitude"], district) for district, infos in found.items() for info in infos]
    short = {district for district, infos in found.items() if not infos}
    for cam in layer:
        if (cam.get("name") or "").strip() in names or cam.get("lat") is None or not points:
            continue
        short.add(min(points, key=lambda p: (p[0] - cam["lat"]) ** 2 + (p[1] - cam["lon"]) ** 2)[2])
    return short


def cameras(get, key=None):
    found = {}
    for district in DISTRICTS:
        try:
            found[district] = _district(get, district)
        except (OSError, ValueError):
            found[district] = []
    for district in _short_districts(get, found) or ():
        try:
            again = _district(get, district)
        except (OSError, ValueError):
            continue
        if len(again) > len(found[district]):
            found[district] = again
    seen = set()
    for district in DISTRICTS:
        for info in found[district]:
            icd_id = info["icd_Id"]
            if icd_id in seen:
                continue
            seen.add(icd_id)
            place = info.get("equipLoc") or {}
            state = info.get("statusDescription")
            yield {
                "id": icd_id,
                "name": (info.get("name") or icd_id).strip(),
                "lat": info["latitude"],
                "lon": info["longitude"],
                "image": _snapshot_url(icd_id),
                "road": place.get("roadway") or None,
                "direction": place.get("direction") or info.get("dirDescription") or None,
                "online": state not in ("Device Offline", "Device Error") and info.get("hasSnapshot") is not False,
                "extra": {k: v for k, v in {"district": district, "net": info.get("netId"), "status": state}.items()
                          if v},
            }
