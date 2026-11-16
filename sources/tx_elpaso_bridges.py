"""Texas: the City of El Paso's international bridge cameras (Stanton Street, Paso del Norte and Ysleta-Zaragoza), three
views a bridge, as HLS video from the city's own stream server (zoocams.elpasozoo.org, which also carries the zoo's
cameras). The list is fixed: the nine streams the city's bridge camera page embeds. Positions are the bridges' (from
Wikipedia; Stanton Street's estimated), not each camera's."""

SOURCE = {
    "name": "City of El Paso International Bridges",
    "state": "TX",
    "covers": "El Paso's Stanton Street, Paso del Norte and Ysleta-Zaragoza international bridges",
    "site": "https://www2.elpasotexas.gov/misc/externally_linked/bridges/cameras.html",
    "terms": None,
    "key": None,
    "headers": {},
    "restricted": None,
    "notes": "The nine HLS streams embedded in the city's bridge camera page (no list feed, so they are listed here). "
             "Untokenized live video. The page says the cameras are under maintenance, but 8 of the 9 streams play; "
             "the adapter fetches each playlist and marks the ones that don't answer out of service. TxDOT's El Paso "
             "cameras are in tx_txdot_its and tx_drivetexas.",
}
BASE = "https://zoocams.elpasozoo.org/{}.m3u8"
BRIDGES = {
    "Stanton Street Bridge": (31.7512, -106.4827, ["stantonbridge1", "BridgeStanton2", "BridgeStanton3"]),
    "Paso del Norte Bridge": (31.74765, -106.48698, ["bridgepdn1", "bridgesantafe3", "bridgesantafe4"]),
    "Ysleta-Zaragoza Bridge": (31.6711, -106.338, ["BridgeZaragoza1", "BridgeZaragoza2", "BridgeZaragoza3"]),
}


def cameras(get, key=None):
    for bridge, (lat, lon, streams) in BRIDGES.items():
        for n, stream in enumerate(streams, 1):
            try:  # nine small playlists: whether each stream is up
                online = get(BASE.format(stream)).startswith(b"#EXTM3U")
            except OSError:
                online = False
            yield {"id": stream, "name": f"{bridge} camera {n}", "lat": lat, "lon": lon, "image": None,
                   "video": BASE.format(stream), "video_type": "hls", "city": "El Paso", "county": "El Paso",
                   "online": online}
