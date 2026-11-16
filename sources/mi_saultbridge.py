"""Michigan: the Sault Ste. Marie International Bridge's US-side traffic camera (no key). It is video only, an
Angelcam stream whose HLS link carries a token good for about two hours, so the camera is listed with video None and
resolve() reads Angelcam's player page for a fresh link. The Canadian-side camera is left out."""

import re

SOURCE = {
    "name": "International Bridge Administration (Sault Ste. Marie)",
    "state": "MI",
    "covers": "The International Bridge (I-75 to Ontario) at Sault Ste. Marie: the US approach",
    "site": "https://www.saultbridge.com/bridge-traffic-camera-south/",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the Angelcam player (camera 1nl8v4goy0) the bridge's 'Bridge Traffic Camera (South)' page "
             "embeds, read from that page; https://v.angelcam.com/iframe?v=<id> contains the HLS playlist URL with a "
             "JWT token that expires after about two hours. No still picture. The bridge is run by the International "
             "Bridge Administration (MDOT) for the joint US-Canada bridge authority. The position is Mi Drive's point "
             "for the bridge (the camera watches the US approach nearby). The 'North' camera (1p2lgz17orn) is the "
             "Canadian plaza and is left out. No terms page.",
}
PAGE = "https://www.saultbridge.com/bridge-traffic-camera-south/"
NAME = "International Bridge: US approach (Bridge Traffic Camera South)"
LAT, LON = 46.50703, -84.36132  # Mi Drive's point for the bridge


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", "replace")
    for angel_id in dict.fromkeys(re.findall(r"id:\s*'([0-9a-z]{8,})'", page)):
        yield {
            "id": angel_id,
            "name": NAME,
            "lat": LAT,
            "lon": LON,
            "image": None,
            "video": None,  # tokenized: resolve() gives it
            "video_type": "hls",
            "road": "I-75",
            "city": "Sault Ste. Marie",
        }


def resolve(get, camera, key=None):
    page = get(f"https://v.angelcam.com/iframe?v={camera['id']}").decode("utf-8", "replace")
    page = page.replace("\\u002D", "-").replace("\\u003D", "=").replace("\\/", "/")
    hls = re.search(r"https://[^\"'\s<>]+?/playlist\.m3u8\?token=[^\"'\s<>]+", page)
    return {"image": None, "video": hls.group(0) if hls else None, "video_type": "hls"}
