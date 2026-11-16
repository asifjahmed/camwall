"""How to reach common cameras, recorders and camera hubs: for each, the kind of address it has (RTSP video, an MJPEG
stream, a snapshot URL or HLS), its usual port and path ({channel} where a recorder has several cameras), and what
the user has to do first. The cameras page offers these when adding a camera; ONVIF (onvif.py) finds the rest."""

BRANDS = [
    # IP cameras
    {"id": "reolink", "name": "Reolink", "group": "camera", "kind": "rtsp", "port": 554,
     "path": "/h264Preview_{channel:02d}_main", "sub": "/h264Preview_{channel:02d}_sub", "user": "admin",
     "notes": "Turn on RTSP in the Reolink app: Settings › Network › Advanced › Server Settings."},
    {"id": "hikvision", "name": "Hikvision / Annke / LTS", "group": "camera", "kind": "rtsp", "port": 554,
     "path": "/Streaming/Channels/{channel}01", "sub": "/Streaming/Channels/{channel}02", "user": "admin",
     "notes": "RTSP is on by default. A recorder's cameras are channels 1, 2, 3…"},
    {"id": "dahua", "name": "Dahua / Amcrest / Lorex", "group": "camera", "kind": "rtsp", "port": 554,
     "path": "/cam/realmonitor?channel={channel}&subtype=0", "sub": "/cam/realmonitor?channel={channel}&subtype=1", "user": "admin",
     "notes": "RTSP is on by default. A recorder's cameras are channels 1, 2, 3…"},
    {"id": "axis", "name": "Axis", "group": "camera", "kind": "rtsp", "port": 554, "path": "/axis-media/media.amp",
     "sub": "/axis-media/media.amp?resolution=640x360", "user": "root", "notes": ""},
    {"id": "uniview", "name": "Uniview (UNV)", "group": "camera", "kind": "rtsp", "port": 554,
     "path": "/unicast/c{channel}/s0/live", "sub": "/unicast/c{channel}/s1/live", "user": "admin", "notes": ""},
    {"id": "tapo", "name": "TP-Link Tapo / Kasa", "group": "camera", "kind": "rtsp", "port": 554, "path": "/stream1",
     "sub": "/stream2", "user": "",
     "notes": "In the Tapo app: the camera › Settings › Advanced Settings › Camera Account. Use that account here."},
    {"id": "eufy", "name": "Eufy", "group": "camera", "kind": "rtsp", "port": 554, "path": "/live0", "sub": "/live0",
     "user": "", "notes": "In the Eufy app: the camera › Settings › NAS (RTSP) › turn on Streaming, and set its username and password."},
    {"id": "wyze", "name": "Wyze", "group": "camera", "kind": "rtsp", "port": 8554, "path": "/{name}", "sub": "/{name}-sub",
     "user": "", "notes": "Through docker-wyze-bridge on a computer at home: use that computer's address, and the camera's name as the bridge shows it."},
    {"id": "foscam", "name": "Foscam", "group": "camera", "kind": "rtsp", "port": 88, "path": "/videoMain", "sub": "/videoSub",
     "user": "admin", "notes": ""},
    {"id": "ubiquiti", "name": "UniFi Protect", "group": "hub", "kind": "rtsp", "port": 7441, "path": "/{token}",
     "sub": "/{token}", "user": "", "scheme": "rtsps",
     "notes": "In UniFi Protect: the camera › Settings › Advanced › RTSP, turn on a stream and copy its address (paste it whole below)."},
    {"id": "amcrest-cloud", "name": "Swann / Night Owl recorder", "group": "camera", "kind": "rtsp", "port": 554,
     "path": "/ch{channel:02d}/0", "sub": "/ch{channel:02d}/1", "user": "admin", "notes": "Paths vary by model; ONVIF may find them."},
    # Hubs that bring in cameras with no stream of their own (Ring, Nest, Arlo, Blink) or many cameras at once
    {"id": "frigate", "name": "Frigate", "group": "hub", "kind": "rtsp", "port": 8554, "path": "/{name}", "sub": "/{name}",
     "user": "", "notes": "Frigate's go2rtc restream: the camera's name as Frigate knows it."},
    {"id": "go2rtc", "name": "go2rtc", "group": "hub", "kind": "rtsp", "port": 8554, "path": "/{name}", "sub": "/{name}",
     "user": "", "notes": "The stream's name in go2rtc."},
    {"id": "scrypted", "name": "Scrypted (Ring, Nest, Arlo…)", "group": "hub", "kind": "rtsp", "port": 0, "path": "", "sub": "",
     "user": "", "notes": "In Scrypted: the camera › Rebroadcast Plugin › copy its RTSP address and paste it whole below."},
    {"id": "homeassistant", "name": "Home Assistant", "group": "hub", "kind": "snapshot", "port": 8123,
     "path": "/api/camera_proxy/{entity}", "sub": "/api/camera_proxy/{entity}", "user": "", "token": True,
     "notes": "Any camera Home Assistant has (Ring, Nest, Arlo, Blink…). Make a long-lived access token on your Home Assistant profile page and paste it as the password; {entity} is like camera.front_door."},
    {"id": "blueiris", "name": "Blue Iris", "group": "hub", "kind": "rtsp", "port": 81, "path": "/{name}", "sub": "/{name}&decode=-1",
     "user": "", "notes": "The camera's short name in Blue Iris."},
    {"id": "synology", "name": "Synology Surveillance Station", "group": "hub", "kind": "rtsp", "port": 0, "path": "", "sub": "",
     "user": "", "notes": "In Surveillance Station: IP Camera › the camera › Share › copy its RTSP address and paste it whole below."},
    # Anything else
    {"id": "rtsp", "name": "Other RTSP camera", "group": "other", "kind": "rtsp", "port": 554, "path": "", "sub": "", "user": "",
     "notes": "Paste its rtsp:// address."},
    {"id": "mjpeg", "name": "MJPEG stream", "group": "other", "kind": "mjpeg", "port": 80, "path": "", "sub": "", "user": "",
     "notes": "An http:// address that streams video as pictures (often ends .mjpg or video.cgi)."},
    {"id": "snapshot", "name": "Snapshot picture", "group": "other", "kind": "snapshot", "port": 80, "path": "", "sub": "",
     "user": "", "notes": "An http:// address that gives the camera's current picture (often snapshot.jpg or snapshot.cgi)."},
    {"id": "hls", "name": "HLS video", "group": "other", "kind": "hls", "port": 80, "path": "", "sub": "", "user": "",
     "notes": "An address ending .m3u8."},
]

KINDS = ("rtsp", "mjpeg", "snapshot", "hls")
