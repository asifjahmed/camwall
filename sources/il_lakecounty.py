"""Illinois: Lake County DOT's PASSAGE cameras, from the camera list its map loads (no key). An intersection camera has
a view per leg (North Leg, East Leg...), and each view is a camera here, known by its picture's file name."""

import json
from urllib.parse import quote

SOURCE = {
    "name": "Lake County DOT (PASSAGE)",
    "state": "IL",
    "covers": "Lake County, Illinois: county highway and state route intersections, plus portable and cellular "
              "cameras",
    "site": "https://www.lakecountypassage.com/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "cache_bust": True,
    "notes": "Undocumented: https://www.lakecountypassage.com/rest/cctv, the JSON the PASSAGE map loads. JPEG stills "
             "on lakecountypassage.com/snapshots/, refreshed about every 2-5 minutes (the map reloads them every 5); "
             "no video. Nearly all (about 1,570 of 1,610) views are also in IDOT's Gateway layer (il_idot, "
             "IL-LAKECOUNTY ids) with the same picture URLs; this list adds about 40 (portable and cellular cameras) "
             "and the 'alarmed' flag, taken as out of service (an alarmed camera's picture is an 8,325-byte "
             "placeholder). Its pictures are served with 'Cache-Control: max-age=3600, immutable', so cache_bust is "
             "set (the map adds ?x=<time> itself). No terms page found.",
}
LIST = "https://www.lakecountypassage.com/rest/cctv"
SNAPSHOTS = "https://www.lakecountypassage.com/snapshots/"
DIRECTIONS = {"north": "N", "south": "S", "east": "E", "west": "W"}


def cameras(get, key=None):
    seen = set()
    for site in json.loads(get(LIST)):
        where = site.get("location") or site.get("iconPoint") or {}
        if where.get("latitude") is None or where.get("longitude") is None:
            continue
        name = (where.get("overrideLocation") or f"{where.get('route', '')} @ {where.get('xstreet', '')}").strip()
        for view in (site.get("approaches") or {}).get("approach") or []:
            file = (view.get("filename") or "").strip()
            if not file or file in seen:
                continue
            seen.add(file)
            leg = (view.get("description") or "").strip()
            yield {
                "id": file.removesuffix(".jpg"),
                "name": f"{name} ({leg})" if leg else name,
                "lat": where["latitude"],
                "lon": where["longitude"],
                "image": SNAPSHOTS + quote(file, safe="@()"),
                "direction": DIRECTIONS.get((view.get("direction") or "").lower()),
                "road": where.get("route") or None,
                "county": "Lake",
                "refresh": 300,
                "online": not site.get("alarmed"),
                "extra": {"site": site.get("id"), "agency": site.get("agency")},
            }
