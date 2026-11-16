"""North Carolina: NCDOT's camera list as its TIMS application publishes it to NCDOT's ArcGIS Online organisation (the
public NCDOT_Cameras feature layer, kept current through the day), with each camera's snapshot on NCDOT's own
snapshot servers. It is the same camera system DriveNC shows (nc_drivenc), but it also lists cameras DriveNC's map
leaves off: in November 2026, 42 with current pictures, among them about 20 of the Elizabeth City signal-system
cameras on US 17, US 17 Business, US 158 and NC 344 (Pasquotank County), and more on I-440, NC 540, US 74 and I-95.

Cameras are known by NCDOT's own camera id (CameraId, the "sourceId" DriveNC also carries), so a camera keeps its id
whether or not DriveNC shows it. Cameras DriveNC also lists have the same name and position there, so the catalogue
lists each once (preferring DriveNC's, which has video)."""

import json

LAYER = "https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/NCDOT_Cameras/FeatureServer/0"
PAGE = 1000

SOURCE = {
    "name": "NCDOT (camera layer on NCDOT's ArcGIS)",
    "state": "NC",
    "covers": "NCDOT's traffic cameras statewide (all 14 highway divisions), including ones DriveNC's map leaves off, "
              "such as Elizabeth City's US 17 / US 158 / NC 344 signal cameras",
    "site": "https://ncdot.maps.arcgis.com/home/item.html?id=eace738dc8d44ff99b2793459572d86e",
    "terms": "https://www.ncdot.gov/about-us/how-we-operate/policy-process/Pages/terms-use.aspx",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Terms: NCDOT allows copying and distributing its images \"for non-commercial use, provided they are copied and "
             "distributed without alteration\"; camwall is free and shows them unaltered, so it's on. "
             "The public NCDOT_Cameras feature layer (owner TIMSApp.NCDOT.GOV, 1,162 rows in November 2026), queried "
             "with the standard ArcGIS REST query, 1,000 a page; no key. It isn't advertised as a developer feed and "
             "its item has no description or licence, so NCDOT's site-wide terms of use apply (non-commercial use "
             "only; see restricted). Rows without an ImageUrl (49) are left out, since they have no public "
             "picture. ImageStatus 'Unavailable' (about 150) means the snapshot URL answers 404: those are listed "
             "with online False. 'Stale' snapshots were in fact current when checked. Snapshots are JPEG (800x450 "
             "to 1280x720) on cf{a,e,m,s,t}s.services.ncdot.gov/snapshots/chan-<CameraId>_l.jpg, changing every one "
             "to three minutes. No video here: DriveNC's HLS needs a token (see nc_drivenc).",
}


def cameras(get, key=None):
    offset = 0
    while True:
        url = (f"{LAYER}/query?where=1%3D1&outFields=*&returnGeometry=false&orderByFields=OBJECTID"
               f"&resultOffset={offset}&resultRecordCount={PAGE}&f=json")
        page = json.loads(get(url))
        if page.get("error"):
            raise OSError(f"{LAYER}: {page['error']}")
        rows = page.get("features") or []
        for row in rows:
            a = row.get("attributes") or {}
            image, lat, lon = a.get("ImageUrl"), a.get("Latitude"), a.get("Longitude")
            if not image or a.get("CameraId") is None or lat is None or lon is None:
                continue
            cam = {
                "id": str(a["CameraId"]),
                "name": (a.get("LocationName") or a.get("Description") or "Camera").strip(),
                "lat": float(lat),
                "lon": float(lon),
                "image": image,
                "road": a.get("Highway") or None,
                "county": a.get("County") or None,
                "refresh": 120,
                "extra": {"status": a.get("CameraStatus"), "image_status": a.get("ImageStatus")},
            }
            if a.get("ImageStatus") == "Unavailable":
                cam["online"] = False
            yield cam
        if len(rows) < PAGE and not page.get("exceededTransferLimit"):
            break
        offset += len(rows)
