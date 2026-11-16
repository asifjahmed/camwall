"""camwall's web server, on this computer only (127.0.0.1): the pages, the JSON they work from, and the relay that
fetches cameras' pictures and video for them.

Why a relay: most cameras' servers send no CORS headers, so a page can show their pictures but can't read when each
was taken (Last-Modified), which the wall needs to time its checks and show how fresh a picture is. Some need a
Referer a page can't send, and HLS video needs its playlists' URLs rewritten. It relays only cameras in the catalogue,
from the URLs their sources list.

    GET  /api/state       version, settings, whether the welcome is due, the catalogue's size
    GET  /api/cameras     every camera, compact (catalogue.listing)
    GET  /api/camera?key= one camera's details
    GET  /api/setup       the camera sets and alerts (sets.for_pages)
    GET  /api/sources     every source and how it's doing
    GET  /api/places      ZIP codes, towns and counties (data/places.json)
    GET  /api/load        how busy the detector is
    POST /api/settings    {name: value}: change settings
    POST /api/setup       {"sets", "alerts"}: replace the sets
    POST /api/key         {"module", "key"}: keep (or with null, forget) a source's API key
    POST /api/refresh     {"module"}: fetch a source's list now
    GET  /cam/<key>       a camera's picture (ETag and Last-Modified for the wall's timing)
    GET  /hls/<key>/index.m3u8, /hls/<key>/x?u=<url>   a camera's HLS video
    GET  /mjpeg/<key>     a camera's MJPEG video
"""

import binascii
import gzip
import http.cookies
import http.client
import http.server
import importlib
import json
import re
import sys
import threading
import time
from email.utils import formatdate
from urllib.parse import parse_qs, unquote, urlsplit

import sources

from . import VERSION, brands, devices, mine, onvif, paths, relay, sets, system, tiles, withdrawn
from .detector import Supervisor
from . import settings as prefs
from .catalogue import Catalogue

PAGES = {
    "/": ("index.html", "text/html"), "/index.html": ("index.html", "text/html"),
    "/cameras.html": ("cameras.html", "text/html"), "/welcome.html": ("welcome.html", "text/html"),
    "/settings.html": ("settings.html", "text/html"), "/app.css": ("app.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"), "/icon.svg": ("icon.svg", "image/svg+xml"),
    "/vendor/leaflet.js": ("vendor/leaflet.js", "text/javascript"),
    "/vendor/leaflet.css": ("vendor/leaflet.css", "text/css"),
    "/vendor/hls.min.js": ("vendor/hls.min.js", "text/javascript"),
    "/pair.html": ("pair.html", "text/html"),
    "/mine.html": ("mine.html", "text/html"),
}  # the only files served
# What a phone or tablet on the network can't do, paired or not: these are for the computer running camwall.
LOCAL_ONLY = {"/api/key", "/api/quit", "/api/login", "/api/detector/install", "/api/network", "/api/network/code",
              "/api/devices/remove", "/api/sources", "/api/detector", "/api/mine", "/api/mine/save", "/api/mine/delete",
              "/api/mine/test", "/api/mine/discover", "/api/mine/onvif", "/api/mine/recordings", "/api/refresh"}
LOCAL_SETTINGS = {"network", "sources", "tiles"}  # settings only the computer running camwall can change
UNPAIRED = {"/pair.html", "/api/pair", "/app.css", "/app.js", "/icon.svg"}  # what an unpaired device may ask for
MAX_POST = 1024 * 1024
TILE = re.compile(r"/tiles/([0-9a-f]{16})/(\d{1,2})/(\d{1,7})/(\d{1,7})")  # a map tile: /tiles/<provider>/<z>/<x>/<y>
# What an HLS segment from a camera's server may be served as here; anything else goes as application/octet-stream.
SEGMENT_TYPES = {"video/mp2t", "video/mp4", "video/iso.segment", "video/mpeg", "audio/aac", "audio/mp4", "audio/mpeg",
                 "application/octet-stream", "binary/octet-stream"}
HOSTS = ("127.0.0.1", "localhost")
RESOLVED_KEEP = 240  # s a source's fresh video URL (resolve()) is used before asking again
STREAM_CHUNK = 64 * 1024

catalogue = Catalogue()
_resolved = {}  # key -> (until, {"image", "video"})
_resolved_lock = threading.Lock()
_places = None  # data/places.json, gzipped
supervisor = None  # the detector's (set by start)
servers = {}       # "local" and, while devices on the network are let in, "network": the HTTP servers
DETECTIONS = paths.USER / "detections"
ALERTS = paths.USER / "alerts.json"
SNAPSHOT = re.compile(r"/alerts/(\d{4}-\d\d-\d\d)/([\w .,-]{1,120}\.jpg)")
RECORDING = re.compile(r"/recordings/([a-z0-9]{8})/([\w .-]{1,40}\.mp4)")
RANGE = re.compile(r"bytes=(\d*)-(\d*)")


def wanted():
    """The sources whose lists are kept fresh: those the cameras in sets come from, those covering where the user
    lives, and any the user switched on that has no list yet (one that isn't shipped isn't fetched by every install
    everywhere)."""
    settings, setup = prefs.get(), sets.load()
    used = {key.split("/", 1)[0] for s in setup["sets"] for key in s["cameras"]}
    home = (settings.get("home") or {}).get("state")
    keys = prefs.keys()
    for module, source in catalogue.modules().items():
        states = source.get("state") if isinstance(source.get("state"), list) else [source.get("state")]
        if source.get("key") and module not in keys:
            continue  # (can't be fetched until the user gives it a key)
        if home in states or module not in catalogue.lists and settings["sources"].get(module):
            used.add(module)  # (where the user lives; or a source with no list yet that they turned on)
    return sorted(m for m in used if catalogue.source_on(m, settings))


class Server(http.server.ThreadingHTTPServer):
    # (On Windows, reusing an address lets a second camwall take a port the first is listening on; elsewhere it only
    # lets a restarted one have its port back at once.)
    allow_reuse_address = sys.platform != "win32"


def media_of(cam):
    """A camera's picture and video URLs, fresh from its source's resolve() if its URLs expire."""
    try:
        module = importlib.import_module(f"sources.{cam['module']}")
    except Exception:  # (its list is still here, but its module has gone, or won't load on this Python)
        module = None
    if not hasattr(module, "resolve"):
        return {"image": cam.get("image"), "video": cam.get("video"), "video_type": cam.get("video_type")}
    key = f"{cam['module']}/{cam['id']}"
    with _resolved_lock:
        hit = _resolved.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    try:
        fresh = {"image": cam.get("image"), "video": cam.get("video"), "video_type": cam.get("video_type"),
                 **module.resolve(sources.get, cam, prefs.keys().get(cam["module"]))}
    except Exception as e:  # (a source's own code: whatever it raises, the listed URLs will have to do)
        print(f"{cam['module']}: no fresh URLs for {cam['id']} ({type(e).__name__}: {str(e)[:120]})")
        fresh = {"image": cam.get("image"), "video": cam.get("video"), "video_type": cam.get("video_type")}
    with _resolved_lock:
        _resolved[key] = (time.monotonic() + RESOLVED_KEEP, fresh)
    return fresh


def headers_of(cam):
    return dict(catalogue.modules().get(cam["module"], {}).get("headers") or {})


def state():
    settings = prefs.get()
    return {"app": "camwall", "version": VERSION, "settings": settings, "welcome": not settings["welcomed"], "data": str(paths.USER),
            "catalogue": {"version": catalogue.version, "cameras": len(catalogue.cameras) - len(catalogue.view(settings)[0]),
                          "sources": len(catalogue.lists)},
            "detector": {k: v for k, v in supervisor.status().items() if k in ("installed", "running", "wanted", "error")}
            if supervisor else None}


def for_devices(answer):
    """The state as a paired device gets it: without the data folder's path (it holds the user's name) or the map
    provider's address (it may hold the user's key)."""
    return {**{k: v for k, v in answer.items() if k != "data"},
            "settings": {k: v for k, v in answer["settings"].items() if k != "tiles"}}


def watch_list():
    """For the detector: the cameras in sets that alert for something, and how to tell the user."""
    settings, setup = prefs.get(), sets.load()
    used = {key for s in setup["sets"] for key in s["cameras"]}
    cameras = []
    for key, kinds in setup["alerts"].items():
        cam = catalogue.get(key, settings) if key in used and kinds else None
        if cam and not catalogue.no_capture(key, settings):
            cameras.append({"key": key, "name": cam["name"], "lat": cam["lat"], "lon": cam["lon"], "kinds": kinds,
                            "media": catalogue.media(key, settings), "video": catalogue.part(key, "video", settings).get("video_type"),
                            "mine": cam["module"] == mine.MODULE})
    return {"cameras": cameras, "settings": {k: settings[k] for k in ("muted", "sound", "voice", "desktop", "quiet", "power_saver")}}


MARKS = paths.USER / "marks.json"  # snapshot -> "real" | "wrong": what the user said of an alert (the detector learns)
_marks_lock = threading.Lock()


def recent_alerts(after):
    alerts = (paths.read_json(ALERTS, {}) or {}).get("alerts", [])
    marks = paths.read_json(MARKS, {}) or {}
    return {"alerts": [{**a, "mark": marks.get(a.get("snapshot"))} for a in alerts if a.get("id", 0) > after][-50:]}


def mark_alert(body):
    """Mark an alert Real or Wrong (or neither, with None): the detector learns from these."""
    snapshot, verdict = str(body["snapshot"]), body["verdict"]
    if verdict not in ("real", "wrong", None) or not SNAPSHOT.fullmatch(f"/alerts/{snapshot}") \
            or not (DETECTIONS / snapshot).is_file():
        raise ValueError("mark")
    with _marks_lock:
        marks = paths.read_json(MARKS, {}) or {}
        if verdict:
            marks[snapshot] = verdict
        else:
            marks.pop(snapshot, None)
        paths.write_json(MARKS, marks)
    return {"ok": True, "marks": len(marks)}


def test_alert(body):
    from detector import notify  # (no heavy libraries in it)
    settings = prefs.get()
    threading.Thread(target=notify.announce, args=("Police at a test camera. This is a test.",), daemon=True,
                     kwargs={"sound": settings["sound"], "voice": settings["voice"], "desktop": settings["desktop"]}).start()
    return {"ok": True}


def install_detector(body):
    supervisor.install()
    return supervisor.status()


def places():
    global _places
    if _places is None:
        _places = gzip.compress((paths.DATA / "places.json").read_bytes(), 6)
    return _places


def save_key(body):
    module, key = body["module"], body["key"]
    if module not in catalogue.modules():
        raise ValueError("module")
    prefs.set_key(module, key)
    return {"ok": True}


def refresh(body):
    module = body["module"]
    if module not in catalogue.modules():
        raise ValueError("module")
    if module in withdrawn.current():
        raise PermissionError("Its agency asked camwall to stop using it")
    if not catalogue.source_on(module, prefs.get()):  # (a restricted source's terms are shown before it's switched on)
        raise PermissionError("Turn that source on first")
    threading.Thread(target=_refresh, args=(module,), daemon=True).start()
    return {"ok": True}


def _refresh(module):
    try:
        print(f"Camera list from {module}: {catalogue.refresh(module, prefs.keys())} cameras")
    except Exception as e:
        print(f"Camera list from {module} not used ({e})")


def update_mine():
    """The user's own cameras into the catalogue (again: they or where home is changed)."""
    catalogue.set_mine(mine.catalogue_cameras(prefs.get()["home"]), mine.SOURCE)


def mine_state():
    return {"cameras": mine.listing(), "brands": brands.BRANDS, "home": prefs.get()["home"]}


def save_mine(body):
    camera = mine.save(body)
    update_mine()
    return {"camera": camera, **mine_state()}


def delete_mine(body):
    mine.delete(str(body["id"]))
    update_mine()
    return mine_state()


def onvif_streams(body):
    address = str(body["address"])
    return onvif.streams(address, int(body.get("port") or 80), str(body.get("username") or ""), str(body.get("password") or ""),
                         body.get("service"))


def network_state():
    port = servers["local"].server_address[1] + 1
    return {"on": "network" in servers, "port": port, "hostname": system.hostname(),
            "addresses": system.local_addresses(), "devices": devices.listing(), "login": system.starts_at_login()}


def apply_network():
    """Listen on the local network (on the next port up) while the settings let devices in, and not otherwise."""
    want = prefs.get()["network"]
    if want and "network" not in servers:
        port = servers["local"].server_address[1] + 1
        try:
            server = Server(("0.0.0.0", port), NetworkHandler)
        except OSError as e:
            print(f"Can't let devices on the network in: port {port} is taken ({e.strerror})")
            return
        server.daemon_threads = True
        servers["network"] = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"Devices on the network can pair with camwall at http://{system.hostname()}:{port}/")
    elif not want and "network" in servers:
        server = servers.pop("network")
        threading.Thread(target=server.shutdown, daemon=True).start()
        print("Devices on the network can't reach camwall now")


def save_settings(body):
    changed = prefs.update(body)
    for module, on in (body.get("sources") or {}).items():  # (a source just switched on: its list now, not in a minute)
        if on and module in catalogue.modules() and module not in catalogue.lists:
            threading.Thread(target=_refresh, args=(module,), daemon=True).start()
    if "network" in body:
        apply_network()
    if "home" in body:
        update_mine()
    return changed


def set_login(body):
    system.start_at_login(bool(body["on"]))
    return network_state()


def quit_app(body):
    def stop():
        time.sleep(0.5)  # (the answer goes out first)
        shutdown()
        for server in list(servers.values()):
            server.shutdown()
    threading.Thread(target=stop, daemon=True).start()
    print("Quitting (asked to on the settings page)")
    return {"ok": True}


def shutdown():
    """Stop what camwall started: the detector, and the ffmpeg reading (and recording) the user's own cameras."""
    if supervisor:
        supervisor.retire()
    mine.stop_all()


def remove_device(body):
    devices.remove(str(body["id"]))
    return network_state()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    local = True  # (on this computer, not from a device on the network)
    server_version = f"camwall/{VERSION}"

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the page was closed or reloaded mid-answer

    def foreign(self):
        """A request through another host name (DNS rebinding) or sent by another site's page."""
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return host.rsplit(":", 1)[0] not in HOSTS or origin not in (None, f"http://{host}") or self.from_another_site()

    def from_another_site(self):
        """Asked for by another site's page (an <img>, say, which sends no Origin), as the browser says: anything but
        following a link to one of camwall's pages."""
        return self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site") \
            and not (self.command in ("GET", "HEAD") and self.headers.get("Sec-Fetch-Mode") == "navigate")

    def do_GET(self):
        self.route()

    def do_HEAD(self):
        self.route()

    def route(self):
        if self.headers.get("Content-Length", "0").strip() not in ("", "0") or self.headers.get("Transfer-Encoding"):
            self.close_connection = True  # (a GET's body isn't read: it mustn't be taken for the next request)
        url = urlsplit(self.path)
        path, query = url.path, parse_qs(url.query)
        if self.foreign():
            return self.fail(403, "Not from this computer's camwall pages")
        if refused := self.refused(path):
            if path in ("/", "/index.html", "/cameras.html", "/settings.html", "/welcome.html"):
                return self.redirect("/pair.html")
            return self.fail(403, refused)
        try:
            if path.startswith("/cam/"):
                return self.serve_picture(unquote(path[len("/cam/"):]))
            if path.startswith("/hls/"):
                return self.serve_hls(path, query)
            if path.startswith("/mjpeg/"):
                return self.serve_mjpeg(unquote(path[len("/mjpeg/"):]))
            if match := TILE.fullmatch(path):
                if match[1] != tiles.provider():
                    return self.fail(404, "That map's tiles aren't the ones in use now")
                body, kind = tiles.tile(*map(int, match.groups()[1:]))
                return self.send_body(body, kind, cache="private, max-age=86400")
            api = {
                "/api/state": state if self.local else lambda: for_devices(state()),
                "/api/setup": lambda: sets.for_pages(catalogue, prefs.get()),
                "/api/sources": lambda: catalogue.summary(prefs.get(), prefs.keys()),
                "/api/load": lambda: paths.read_json(paths.LOAD, {}),
                "/api/map": tiles.for_pages,
                "/api/watch": watch_list,
                "/api/detector": lambda: supervisor.status(),
                "/api/network": network_state,
                "/api/mine": mine_state,
            }.get(path)
            if api:
                return self.send_json(api())
            if path == "/api/cameras":
                return self.send_body(catalogue.listing(prefs.get()), "application/json", gzipped=True)
            if path == "/api/camera":
                detail = catalogue.detail(query.get("key", [""])[0], prefs.get())
                return self.send_json(detail) if detail else self.fail(404, "Not found")
            if path == "/api/alerts":
                return self.send_json(recent_alerts(int(query.get("after", ["0"])[0] or 0)))
            if match := SNAPSHOT.fullmatch(unquote(path)):
                file = DETECTIONS / match[1] / match[2]
                if file.is_file():
                    return self.send_body(file.read_bytes(), "image/jpeg", cache="max-age=86400")
            if path == "/api/mine/recordings":
                return self.send_json({"recordings": mine.recordings(query.get("id", [""])[0])})
            if (match := RECORDING.fullmatch(unquote(path))) and self.local:  # (recordings: this computer only)
                file = mine.recording_file(match[1], match[2])
                if file:
                    return self.send_file(file, "video/mp4")
            if path == "/api/places":
                return self.send_body(places(), "application/json", gzipped=True, cache="max-age=86400")
            if path in PAGES:
                file, kind = PAGES[path]
                return self.send_body((paths.WEB / file).read_bytes(), kind)
        except (BrokenPipeError, ConnectionResetError):
            return  # (the page stopped listening: a video closed, a page left)
        except OSError as e:
            return self.fail(502, str(e)[:200])
        except ValueError:
            return self.fail(400, "Bad request")
        except Exception as e:  # (a saved file of the wrong shape, say: an answer, not a dropped connection)
            self.log_message("%s: %s", self.path[:120], f"{type(e).__name__}: {e}"[:200])
            return self.fail(500, "Something went wrong here: see camwall's log")
        self.fail(404, "Not found")

    def refused(self, path):
        """Why this request may not go ahead, or None (on this computer, everything may)."""
        return None

    def do_POST(self):
        if self.foreign():
            return self.fail(403, "Not from this computer's camwall pages")
        if refused := self.refused(self.path):
            return self.fail(403, refused)
        handle = {
            "/api/settings": save_settings,
            "/api/setup": lambda body: sets.save(body, catalogue, prefs.get()),
            "/api/key": save_key,
            "/api/refresh": refresh,
            "/api/detector/install": install_detector,
            "/api/detector/test": test_alert,
            "/api/alerts/mark": mark_alert,
            "/api/login": set_login,
            "/api/quit": quit_app,
            "/api/network/code": lambda body: devices.new_code(),
            "/api/devices/remove": remove_device,
            "/api/pair": self.pair,
            "/api/mine/save": save_mine,
            "/api/mine/delete": delete_mine,
            "/api/mine/test": mine.test,
            "/api/mine/discover": lambda body: {"found": onvif.discover()},
            "/api/mine/onvif": onvif_streams,
        }.get(self.path)
        if handle is None:
            return self.fail(404, "Not found")
        # JSON only: another site's page can't send that here without a CORS preflight, which is never answered.
        length = self.headers.get("Content-Length", "0")
        length = int(length) if length.isdigit() else MAX_POST + 1
        if self.headers.get("Content-Type") != "application/json" or length > MAX_POST:
            return self.fail(400, "Bad request")
        try:
            body = json.loads(self.rfile.read(length))
            if not self.local and self.path == "/api/settings" and LOCAL_SETTINGS & set(body):
                raise PermissionError("Only the computer running camwall can change that")
            reply = handle(body)
        except PermissionError as e:
            return self.fail(403, str(e))
        except (ValueError, KeyError, TypeError, AttributeError, binascii.Error):
            return self.fail(400, "Bad request")
        self.send_json(reply)

    def pair(self, body):
        raise PermissionError("Pairing is for devices on the network")

    def redirect(self, to):
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- answers ----

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")  # (each answer is what its type says, never sniffed)
        super().end_headers()

    def send_body(self, body, kind, gzipped=False, cache="no-cache", status=200, extra=()):
        extra = [*extra, *self.__dict__.pop("set_cookie", [])]  # (a cookie goes with the one answer)
        if gzipped and "gzip" not in self.headers.get("Accept-Encoding", ""):
            body, gzipped = gzip.decompress(body), False
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        if gzipped:
            self.send_header("Content-Encoding", "gzip")
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_file(self, file, kind):
        """A file, or the part of it a video player asks for (Range), a piece at a time."""
        size = file.stat().st_size
        start, end = 0, size - 1
        match = RANGE.fullmatch(self.headers.get("Range", ""))
        if match and (match[1] or match[2]):
            start, end = (int(match[1]), int(match[2]) if match[2] else size - 1) if match[1] else (max(0, size - int(match[2])), size - 1)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                return self.end_headers()
            end = min(end, size - 1)
        self.send_response(206 if match else 200)
        self.send_header("Content-Type", kind)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-cache")
        if match:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(file, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0 and (chunk := f.read(min(STREAM_CHUNK * 4, left))):
                self.wfile.write(chunk)
                left -= len(chunk)

    def send_json(self, value):
        body = json.dumps(value, separators=(",", ":")).encode()
        if len(body) > 4096 and "gzip" in self.headers.get("Accept-Encoding", ""):
            return self.send_body(gzip.compress(body, 5), "application/json", gzipped=True)
        self.send_body(body, "application/json")

    def camera(self, key, what):
        """The listed camera with this key, or the one linked to it, that has its "image" or "video"."""
        settings = prefs.get()
        cam = catalogue.get(key, settings)
        if cam is None:
            self.fail(404, "Not a listed camera")
            return None
        return catalogue.part(key, what, settings)

    def serve_picture(self, key):
        cam = self.camera(key, "image")
        if cam is None:
            return
        if cam["module"] == mine.MODULE:
            return self.serve_mine(cam["id"])
        url = media_of(cam)["image"]
        if not url:
            return self.fail(404, "This camera has video only")
        source = catalogue.modules().get(cam["module"], {})
        try:
            pic = relay.picture(url, headers_of(cam), source.get("image_json"), bool(source.get("cache_bust")))
        except OSError as e:
            return self.fail(502, f"Camera unreachable: {str(e)[:150]}")
        if relay.stand_in(pic):
            return self.fail(503, "Out of service (its source shows a stand-in picture)")
        validators = [("ETag", pic.etag), *([("Last-Modified", pic.modified)] if pic.modified else []),
                      ("Date", pic.date or formatdate(usegmt=True))]
        if self.headers.get("If-None-Match") == pic.etag:
            self.send_response_only(304)
            for name, value in validators:
                self.send_header(name, value)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self.send_body(pic.body, pic.type, cache="no-store", extra=validators)

    def serve_mine(self, cam_id):
        """One of the user's own cameras: its newest picture, held until there's one newer than the page has."""
        reader = mine.reader(cam_id)
        if reader is None:
            return self.fail(404, "Not one of your cameras")
        known = self.headers.get("If-None-Match")
        frame, etag, at = reader.latest(known)
        if frame is None:
            return self.fail(503, reader.error or "No picture from the camera yet")
        if etag == known:
            self.send_response_only(304)
            for name, value in [("ETag", etag), *mine.frame_headers(at), ("Cache-Control", "no-store")]:
                self.send_header(name, value)
            self.end_headers()
            return
        self.send_body(frame, mine.picture_type(frame) or "image/jpeg", cache="no-store", extra=[("ETag", etag), *mine.frame_headers(at)])

    def serve_hls(self, path, query):
        parts = path.split("/")  # "", "hls", <key>, <file>
        if len(parts) != 4:
            return self.fail(404, "Not found")
        cam = self.camera(unquote(parts[2]), "video")
        if cam is None:
            return
        key = f"{cam['module']}/{cam['id']}"
        if parts[3] == "index.m3u8":
            fresh = media_of(cam)
            url = fresh["video"]
            if not url or fresh.get("video_type", cam.get("video_type")) != "hls":
                return self.fail(404, "This camera has no HLS video")
        elif parts[3] == "x" and relay.named(key, query.get("u", [""])[0]):
            url = query["u"][0]
        else:
            return self.fail(404, "Not found")
        try:
            resp, conn, final = relay.open_url(url, headers_of(cam))
        except OSError as e:
            return self.fail(502, f"Camera unreachable: {str(e)[:150]}")
        try:
            if resp.status != 200:
                resp.read(relay.MAX_BODY)
                return self.fail(502, f"The camera's server answered {resp.status}")
            kind = resp.getheader("Content-Type") or ""
            if "mpegurl" in kind.lower() or final.split("?")[0].lower().endswith(".m3u8"):
                text = resp.read(relay.MAX_BODY).decode("utf-8", "replace")
                return self.send_body(relay.rewrite(key, final, text).encode(), "application/vnd.apple.mpegurl", cache="no-store")
            base = kind.split(";")[0].strip().lower()
            self.stream(resp, base if base in SEGMENT_TYPES else "application/octet-stream", resp.getheader("Content-Length"))
        finally:
            if resp.isclosed():
                relay.done(conn, resp)
            else:
                conn.close()

    def serve_mjpeg(self, key):
        cam = self.camera(key, "video")
        if cam is None:
            return
        fresh = media_of(cam)
        url = fresh["video"]
        if not url or fresh.get("video_type", cam.get("video_type")) != "mjpeg":
            return self.fail(404, "This camera has no MJPEG video")
        try:
            resp, conn, _ = relay.open_url(url, headers_of(cam))
        except OSError as e:
            return self.fail(502, f"Camera unreachable: {str(e)[:150]}")
        try:
            if resp.status != 200:
                return self.fail(502, f"The camera's server answered {resp.status}")
            kind = resp.getheader("Content-Type") or "multipart/x-mixed-replace"
            first = resp.read1(STREAM_CHUNK)
            if not kind.lower().startswith(("multipart/x-mixed-replace", "image/jpeg")) \
                    or not first.lstrip(b"\r\n").startswith((b"--", b"\xff\xd8")):  # (never a page, or a playlist)
                return self.fail(502, "The camera's server didn't answer with MJPEG")
            self.stream(resp, kind, None, first)
        finally:
            conn.close()

    def stream(self, resp, kind, length, first=b""):
        """Pass a response on as it comes (a video segment, or an MJPEG stream that never ends), after the bytes of it
        already read (first)."""
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "sandbox; default-src 'none'")  # (a camera's bytes: never a page)
        if length:
            self.send_header("Content-Length", length)
        else:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if self.command == "HEAD":
            return
        self.wfile.write(first)
        while chunk := resp.read1(STREAM_CHUNK) if hasattr(resp, "read1") else resp.read(STREAM_CHUNK):
            self.wfile.write(chunk)

    def fail(self, status, text):
        """An error, with a line saying what went wrong (ASCII, as a status line must be)."""
        text = text.encode("ascii", "replace").decode().replace("\n", " ")
        self.close_connection = True  # (a body left unread mustn't be taken for the next request on this connection)
        if status >= 500:
            self.log_message("%s %s: %s", status, self.path[:120], text)
        self.send_body(text.encode(), "text/plain; charset=utf-8", cache="no-store", status=status)

    def log_request(self, code="-", size="-"):
        pass  # the wall asks a few times a second; only failures are printed


class NetworkHandler(Handler):
    """Requests from devices on the local network: a paired device may do what the pages do, but not what's kept for
    the computer running camwall (LOCAL_ONLY); an unpaired one may only pair."""

    local = False

    def foreign(self):
        host = self.headers.get("Host", "")
        return not host or self.headers.get("Origin") not in (None, f"http://{host}") or self.from_another_site()

    def refused(self, path):
        if path in LOCAL_ONLY:
            return "Only the computer running camwall can do that"
        if path in UNPAIRED:
            return None
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except http.cookies.CookieError:
            return "Pair this device first"
        paired = devices.check(cookie[devices.COOKIE].value if devices.COOKIE in cookie else None)
        return None if paired else "Pair this device first"

    def pair(self, body):
        token = devices.pair(body["code"], body.get("name", ""))
        self.set_cookie = [("Set-Cookie", f"{devices.COOKIE}={token}; Max-Age={devices.COOKIE_AGE}; Path=/; HttpOnly; SameSite=Strict")]
        print(f"Paired a device: {body.get('name', '')[:60]}")
        return {"ok": True}


def start(port):
    """Load the catalogue, keep it fresh, run the detector when it's wanted, and serve on 127.0.0.1:port (OSError if
    the port is taken)."""
    global supervisor
    server = Server(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    catalogue.load()
    threading.Thread(target=catalogue.keep, args=(wanted, prefs.keys), daemon=True).start()
    supervisor = Supervisor(port)
    threading.Thread(target=supervisor.keep, daemon=True).start()
    threading.Thread(target=tiles.forget, daemon=True).start()
    threading.Thread(target=withdrawn.keep, args=(catalogue.withdrawn_changed,), daemon=True).start()
    servers["local"] = server
    update_mine()
    mine.start_recording()
    apply_network()
    return server
