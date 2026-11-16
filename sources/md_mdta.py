"""Maryland: the Maryland Transportation Authority's cameras at its toll facilities (I-95 JFK Highway and Express Toll
Lanes, the ICC, the Baltimore Harbor and Fort McHenry tunnels, the Bay Bridge, the Hatem and Nice/Middleton bridges and
the Key Bridge approaches), from the camera lists in its Traffic Cameras page's script (no key).

The streams are CHART's (and most cameras are also in md_chart); each camera is known by its CHART stream id, so the
two can be matched. Live HLS video only."""

import json
import re

SOURCE = {
    "name": "Maryland Transportation Authority",
    "state": "MD",
    "covers": "MDTA toll facilities: I-95 (JFK Highway, Express Toll Lanes), ICC/MD 200, I-895, I-95 Fort McHenry "
              "Tunnel, US 50/301 Bay Bridge, US 40 Hatem Bridge, US 301 Nice/Middleton Bridge, I-695 Key Bridge area",
    "site": "https://mdta.maryland.gov/traffic-cameras-by-facility",
    "terms": "https://mdta.maryland.gov/mdta-websites-privacy-statement",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the lists in /themes/mdta/js/traffic-cams-noflash-mdta_v1.1.js, a hand-kept file; some of "
             "its streams no longer play (cameras near the fallen Key Bridge, an old raw-IP server). About 120 of its "
             "cameras are in CHART's feed too (md_chart), under the same stream id. Video only.",
}
SCRIPT = "https://mdta.maryland.gov/themes/mdta/js/traffic-cams-noflash-mdta_v1.1.js?v=1.x"
FACILITIES = {"JFK": "I-95 John F. Kennedy Memorial Highway", "ICC": "Intercounty Connector (MD 200)",
              "BHT": "Baltimore Harbor Tunnel (I-895)", "ETL": "I-95 Express Toll Lanes", "THB": "Hatem Bridge (US 40)",
              "FMT": "Fort McHenry Tunnel (I-95)", "FSK": "Key Bridge (I-695)", "WPL": "Bay Bridge (US 50/301)",
              "NMB": "Nice/Middleton Bridge (US 301)"}


def cameras(get, key=None):
    script = get(SCRIPT).decode("utf-8", errors="replace")
    script = re.sub(r"/\*.*?\*/", "", script, flags=re.S)  # cameras commented out of the lists
    found = {}  # stream id -> camera
    for name, body in re.findall(r"var (CameraData\w*)\s*=\s*\[(.*?)\];", script, flags=re.S):
        facility = FACILITIES.get(name.removeprefix("CameraData_"))
        for item in re.findall(r"\{[^{}]*\}", body):
            try:
                cam = json.loads(item)
            except ValueError:
                continue
            url = cam.get("rtmp") or ""
            stream = re.search(r"/rtplive/([0-9a-f]{32})/playlist\.m3u8", url)
            if not stream or not url.startswith("https://") or not cam.get("latitude") or not cam.get("longitude"):
                continue
            if stream.group(1) in found:  # the default list comes first; the others name the facility
                if facility:
                    found[stream.group(1)]["extra"].setdefault("facility", facility)
                continue
            found[stream.group(1)] = {
                "id": stream.group(1),
                "name": (cam.get("name") or "Camera").strip(),
                "lat": float(cam["latitude"]),
                "lon": float(cam["longitude"]),
                "image": None,
                "video": url,
                "video_type": "hls",
                "extra": {k: v for k, v in {"mdta_id": cam.get("id"), "region": cam.get("Region"),
                                            "facility": facility}.items() if v},
            }
    yield from found.values()
