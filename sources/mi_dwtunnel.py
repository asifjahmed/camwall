"""Michigan: the Detroit-Windsor Tunnel's border cameras on the Detroit side, from the Dacast streams its home page
embeds (no key). Each stream has an HLS playlist and a preview still, both found through Dacast's content-access
lookup. The page gives no coordinates, so the two Detroit cameras are placed by hand at the spots their captions name;
the third camera (Canadian inspection, in Windsor) is left out."""

import html
import json
import re

SOURCE = {
    "name": "Detroit Windsor Tunnel",
    "state": "MI",
    "covers": "The Detroit-Windsor Tunnel's Detroit entrance (Randolph Street) and the US inspection plaza",
    "site": "https://www.dwtunnel.com/",
    "terms": "https://www.dwtunnel.com/privacy-policy/",
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "Undocumented: the Dacast iframe ids on dwtunnel.com's 'Live Border Cameras' section, resolved through "
             "https://playback.dacast.com/content/access (which returns the HLS and preview URLs, unsigned). The "
             "tunnel is owned by the cities of Detroit and Windsor; the Detroit half is run by Detroit Windsor Tunnel "
             "LLC under lease, so this is a privately operated but publicly owned crossing. The page pauses its "
             "player after 15 seconds ('Continue Watching'); the stills are the stream's preview.jpg, a few seconds "
             "old. Positions are approximate (placed by caption). Only a privacy policy, no terms.",
}
PAGE = "https://www.dwtunnel.com/"
ACCESS = "https://playback.dacast.com/content/access?contentId={account}-live-{stream}&provider=default"
PLACES = {  # caption -> (lat, lon); captions not here (the Windsor plaza) are skipped
    "Detroit to Windsor – Randolph Street": (42.3292, -83.0443),
    "Windsor to Detroit Inspection": (42.3275, -83.0411),
}


def cameras(get, key=None):
    page = get(PAGE).decode("utf-8", "replace")
    text = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", page)
    captions = [c for c in (html.unescape(re.sub(r"\s+", " ", s)).strip() for s in re.split(r"<[^>]+>", text))
                if c.lower().startswith(("detroit to windsor", "windsor to detroit"))]
    streams = re.findall(r"iframe\.dacast\.com/live/([0-9a-f-]{36})/([0-9a-f-]{36})", page)
    for (account, stream), caption in zip(streams, captions):
        place = PLACES.get(caption)
        if not place:
            continue
        urls = json.loads(get(ACCESS.format(account=account, stream=stream)))
        if not urls.get("hls") and not urls.get("preview"):
            continue
        yield {
            "id": stream,
            "name": f"Detroit-Windsor Tunnel: {caption}",
            "lat": place[0],
            "lon": place[1],
            "image": urls.get("preview"),
            "video": urls.get("hls"),
            "video_type": "hls" if urls.get("hls") else None,
            "city": "Detroit",
            "county": "Wayne",
            "refresh": 10,
        }
