"""The user's own cameras, at home or at their business: IP cameras, recorders and hubs, reached by RTSP, MJPEG, a
snapshot address or HLS (brands.py has the usual addresses; onvif.py finds them). Each is in the catalogue as
"mine/<id>", on the map where the user says it is (home, unless they say otherwise), and is shown and watched like any
other camera.

my_cameras.json holds them, without passwords: those are in the system keychain (secrets.py). A camera's video is
turned into pictures by ffmpeg only while something is looking (a page, or the detector), and stops IDLE_STOP s after
the last look. Unlike public cameras, these may be on private addresses: they're the user's own, added by them. One
on a home network can also be reached through a tunnel when this computer is away from home (tunnel.py).
"""

import base64
import functools
import re
import shutil
import secrets as random
import subprocess
import threading
import time
import urllib.error
import urllib.request
from email.utils import formatdate
from urllib.parse import quote, unquote, urlsplit

from . import brands, paths, secrets, tunnel
from . import settings as prefs

MODULE = "mine"      # their module name in the catalogue
FILE = paths.USER / "my_cameras.json"
ID = re.compile(r"[a-z0-9]{8}")
NAME_LENGTH = 60
URL_LENGTH = 1000
SCHEMES = {"rtsp": ("rtsp", "rtsps"), "mjpeg": ("http", "https"), "snapshot": ("http", "https"), "hls": ("http", "https")}
LONG_POLL = 10       # s a request for a picture waits for a newer one
IDLE_STOP = 30       # s without a request before a camera's stream is closed
WALL_FPS = 10        # pictures a second made from a camera's video (POWER_SAVER_FPS in power saver)
POWER_SAVER_FPS = 3
SNAPSHOT_EVERY = 1.0  # s between fetches of a snapshot camera's picture
TEST_WAIT = 20       # s a test waits for a picture
RECORDINGS = paths.USER / "recordings"  # <id>/<date> <time>.mp4, a minute each, kept as long as each camera says
RECORD_HOURS = (0, 2, 6, 24, 72, 168)   # how long a camera's recording can be kept (0: not recorded)
RECORDABLE = ("rtsp", "hls")            # (their video is copied as it is; MJPEG and snapshots would need encoding)
DISK_LOW = 5 * 1024 ** 3                # bytes free under which the oldest recordings go, whatever their camera says
LOW_DISK_KEEP = 60                      # recorded minutes each camera keeps however low the disk is (its last hour)
TUNNEL = re.compile(r"([\w.-]{1,100}):(\d{1,5})")  # a SOCKS5 proxy, "host:port"
PORTS = {"rtsp": 554, "rtsps": 322, "http": 80, "https": 443}
SEGMENT = re.compile(r"(\d{4}-\d\d-\d\d) (\d\d)-(\d\d)-(\d\d)\.mp4")
BOOT = random.token_hex(4)
SOURCE = {"name": "My cameras", "state": "US", "covers": "Your own cameras", "site": "", "terms": None, "key": None,
          "headers": {}, "restricted": None, "notes": None}

_lock = threading.Lock()
_readers = {}  # id -> Reader


def _account(cam_id):
    return f"camera-{cam_id}"


def load():
    saved = paths.read_json(FILE, [])
    return [c for c in saved if _whole(c)] if isinstance(saved, list) else []


def _whole(c):
    """A saved camera with what the rest of camwall takes for granted (one edited by hand may not have it)."""
    return isinstance(c, dict) and ID.fullmatch(str(c.get("id"))) is not None \
        and all(isinstance(c.get(k), str) for k in ("name", "kind", "url")) \
        and all(c.get(k) is None or isinstance(c.get(k), (int, float)) and not isinstance(c.get(k), bool)
                for k in ("lat", "lon", "record"))


def listing():
    """The cameras as the pages see them: no passwords, and how each is doing."""
    return [{**c, "has_password": bool(secrets.get(_account(c["id"]))),
             "error": _readers[c["id"]].error if c["id"] in _readers else None} for c in load()]


def catalogue_cameras(home):
    """The cameras as catalogue entries (pictures through the relay, from "mine://<id>")."""
    lat, lon, state = (home["lat"], home["lon"], home["state"]) if home else (39.83, -98.58, "KS")
    return [{"id": c["id"], "name": c["name"], "lat": c.get("lat") if c.get("lat") is not None else lat,
             "lon": c.get("lon") if c.get("lon") is not None else lon, "state": state, "image": f"mine://{c['id']}",
             "extra": {"mine": True, "kind": c["kind"]}} for c in load()]


def _checked(body):
    name = " ".join(str(body["name"]).split())[:NAME_LENGTH]
    kind, url = body["kind"], str(body["url"]).strip()
    if not name or not name.isprintable() or kind not in brands.KINDS:
        raise ValueError("name or kind")
    parts = urlsplit(url)
    if parts.scheme not in SCHEMES[kind] or not parts.hostname or len(url) > URL_LENGTH or not url.isprintable():
        raise ValueError(f"a {kind} camera's address starts {' or '.join(s + '://' for s in SCHEMES[kind])}")
    username, password = str(body.get("username") or "").strip(), body.get("password")
    if parts.username is not None:  # (a pasted address with its login in it: kept apart)
        username = username or unquote(parts.username)
        password = password if password else unquote(parts.password or "")
        url = parts._replace(netloc=parts.netloc.rsplit("@", 1)[1]).geturl()
    lat, lon = body.get("lat"), body.get("lon")
    if (lat is None) != (lon is None) or lat is not None and not (
            all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lat, lon)) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("place")
    brand = body.get("brand") if any(b["id"] == body.get("brand") for b in brands.BRANDS) else None
    record = body.get("record") or 0
    if record not in RECORD_HOURS or record and kind not in RECORDABLE:
        raise ValueError("recording")
    proxy = str(body.get("tunnel") or "").strip()
    if proxy and not ((m := TUNNEL.fullmatch(proxy)) and 0 < int(m[2]) < 65536):
        raise ValueError("a tunnel is a SOCKS5 proxy's host:port, such as 127.0.0.1:1055")
    return {"name": name, "kind": kind, "url": url, "username": username[:200], "bearer": bool(body.get("bearer")),
            "lat": lat, "lon": lon, "brand": brand, "record": record, "sound": bool(record and body.get("sound")),
            "tunnel": proxy or None}, password


def save(body):
    """Add a camera, or change one (body["id"]); password None keeps the one it has. Returns the camera."""
    camera, password = _checked(body)
    with _lock:
        cameras = load()
        cam_id = body.get("id")
        if cam_id is not None and (not ID.fullmatch(str(cam_id)) or not any(c["id"] == cam_id for c in cameras)):
            raise ValueError("no such camera")
        cam_id = cam_id or random.token_hex(4)
        camera = {"id": cam_id, **camera}
        cameras = [camera if c["id"] == cam_id else c for c in cameras] if body.get("id") else [*cameras, camera]
        if password is not None:
            if password:
                secrets.put(_account(cam_id), str(password))
            else:
                secrets.delete(_account(cam_id))
        paths.write_json(FILE, cameras, private=True)
        reader = _readers.pop(cam_id, None)
    if reader:
        reader.stop()
    if camera.get("record"):
        globals()["reader"](cam_id)  # (recording starts now, not when it's first looked at)
    return camera


def delete(cam_id):
    if not ID.fullmatch(cam_id):  # (it names a folder that's removed)
        raise ValueError("no such camera")
    with _lock:
        cameras = [c for c in load() if c["id"] != cam_id]
        paths.write_json(FILE, cameras, private=True)
        reader = _readers.pop(cam_id, None)
    secrets.delete(_account(cam_id))
    if reader:
        reader.stop()
    shutil.rmtree(RECORDINGS / cam_id, ignore_errors=True)


def reader(cam_id):
    """The reader of one of the cameras (made when first asked for), or None if there's no such camera."""
    with _lock:
        if cam_id not in _readers:
            config = next((c for c in load() if c["id"] == cam_id), None)
            if config is None:
                return None
            _readers[cam_id] = Reader(config, secrets.get(_account(cam_id)) or "")
        return _readers[cam_id]


def _routed(config, direct=True):
    """("direct" | "tunnel", the camera's address as this computer can reach it now): its own, or, when it has a tunnel
    and doesn't answer directly (or `direct` is False), a port here that the tunnel carries to it."""
    if not config.get("tunnel"):
        return "direct", config["url"]
    parts = urlsplit(config["url"])
    target = (parts.hostname, parts.port or PORTS.get(parts.scheme, 80))
    if direct and tunnel.answers(target):
        return "direct", config["url"]
    host, port = config["tunnel"].rsplit(":", 1)
    return "tunnel", parts._replace(netloc=f"127.0.0.1:{tunnel.port_for((host, int(port)), target)}").geturl()


def _with_login(url, username, password):
    if not username and not password:
        return url
    parts = urlsplit(url)
    host = parts.netloc.rsplit("@", 1)[-1]
    return parts._replace(netloc=f"{quote(username, safe='')}:{quote(password, safe='')}@{host}").geturl()


def _mask(text):
    return re.sub(r"(rtsps?|https?)://[^@\s/]*@", r"\1://***@", text)


def _opener(config, password):
    """urllib that logs in to a camera however it asks (Basic or Digest), or sends a hub's token."""
    manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    if config["username"] and not config["bearer"]:
        manager.add_password(None, config["url"], config["username"], password)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(manager), urllib.request.HTTPDigestAuthHandler(manager))
    opener.addheaders = [("User-Agent", "camwall")] + ([("Authorization", f"Bearer {password}")] if config["bearer"] else [])
    return opener


def _ffmpeg(config, password, fps, frames=None, pictures=True, record=None, url=None):
    """ffmpeg reading a camera (at `url`, if not its own: see _routed): pictures (fps a second, or `frames` of them) as
    MJPEG on its output, and/or its video copied as it is into a minute-long file at a time in `record` (a folder).
    Its sound is recorded only when the user has turned that on for the camera ("sound"); else camwall doesn't listen."""
    if not shutil.which("ffmpeg"):
        raise NoFFmpeg()
    url = url or config["url"]
    url = url if config["bearer"] else _with_login(url, config["username"], password)
    head = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if config["kind"] == "rtsp":
        head += ["-rtsp_transport", "tcp", _socket_timeout(), "10000000"]
    elif config["kind"] == "mjpeg":  # (no timestamps in it: ffmpeg would take it for 25 fps and drop most)
        head += ["-use_wallclock_as_timestamps", "1"]
    elif config["kind"] == "hls" and not frames:  # (at its own pace: else each segment's frames come in a burst)
        head += ["-re"]
    if config["bearer"]:
        head += ["-headers", f"Authorization: Bearer {password}\r\n"]
    out = []
    if pictures:
        out += ["-map", "0:v:0", "-vf", f"fps={fps}", "-c:v", "mjpeg", "-q:v", "5",
                *(["-frames:v", str(frames)] if frames else []), "-f", "mpjpeg", "pipe:1"]
    if record:
        sound = ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "64k"] if config.get("sound") else []  # (AAC: MP4 can't hold G.711)
        out += ["-map", "0:v:0", *sound, "-c:v", "copy", "-f", "segment", "-segment_time", "60",
                "-reset_timestamps", "1", "-strftime", "1", "-segment_format", "mp4",
                "-segment_format_options", "movflags=+frag_keyframe+empty_moov+default_base_moof",
                str(record / "%Y-%m-%d %H-%M-%S.mp4")]
    return head + ["-i", url] + out


def read_part(stream):
    """One JPEG from ffmpeg's multipart (mpjpeg) output; None when the stream ends."""
    length = None
    while line := stream.readline():
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
        elif line == b"\r\n" and length is not None:
            return stream.read(length)
    return None


def test(body):
    """One picture from a camera as it would be saved, within TEST_WAIT s: {"ok", "jpeg" (base64) or "error"}. With no
    password given, an existing camera's own is used."""
    config, password = _checked(body)
    if password is None and body.get("id"):
        password = secrets.get(_account(str(body["id"]))) or ""
    password = password or ""
    try:
        url = _routed(config)[1]
        if config["kind"] == "snapshot":
            with _opener(config, password).open(url, timeout=TEST_WAIT) as resp:
                jpeg = resp.read(20 * 1024 * 1024)
            if not picture_type(jpeg):
                return {"ok": False, "error": "That address doesn't give a picture"}
        else:
            process = subprocess.Popen(_ffmpeg(config, password, 1, frames=1, url=url), stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, **paths.NO_WINDOW)
            try:
                out, err = process.communicate(timeout=TEST_WAIT)
            except subprocess.TimeoutExpired:
                process.kill()
                return {"ok": False, "error": "No picture came within 20 seconds: is the address right, and the camera on?"}
            start = out.find(b"\xff\xd8")
            if start < 0:
                return {"ok": False, "error": _explain(err.decode(errors="replace"))}
            jpeg = out[start:out.rfind(b"\xff\xd9") + 2]
        return {"ok": True, "jpeg": base64.b64encode(jpeg).decode()}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "The camera turned down that username and password" if e.code in (401, 403)
                else f"The camera answered {e.code}"}
    except NoFFmpeg as e:
        return {"ok": False, "error": str(e)}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "error": f"Couldn't reach it ({_mask(str(getattr(e, 'reason', e)))})"}


class NoFFmpeg(OSError):
    def __str__(self):
        return ("This camera needs ffmpeg, which isn't installed: brew install ffmpeg on a Mac, winget install ffmpeg "
                "on Windows, or your Linux system's ffmpeg package")


@functools.cache
def _socket_timeout():
    """ffmpeg's option for an RTSP camera's socket timeout: -timeout from ffmpeg 5, -stimeout before (where -timeout
    meant waiting for the camera to connect to it)."""
    try:
        version = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10, **paths.NO_WINDOW).stdout
        major = int(re.search(r"ffmpeg version n?(\d+)\.", version)[1])
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        return "-timeout"  # (a build without a plain version number, as most are now: a recent one)
    return "-timeout" if major >= 5 else "-stimeout"


def _explain(err):
    """ffmpeg's complaint in plain words."""
    text = _mask(err.strip().splitlines()[-1] if err.strip() else "")
    if re.search(r"401|Unauthorized", err):
        return "The camera turned down that username and password"
    if re.search(r"404|Not Found", err):
        return "The camera has nothing at that path: check the address"
    if re.search(r"Connection refused", err):
        return "Nothing answered on that port: check the address and port, and that the camera's RTSP is turned on"
    if re.search(r"timed out|Operation timed out|No route|unreachable", err, re.I):
        return "The camera didn't answer: is it on, and on this network?"
    return text or "No picture came from it"


class Reader:
    """The newest picture of one of the user's cameras, made while something is asking for it."""

    def __init__(self, config, password):
        self.config, self.password = config, password
        self.cond = threading.Condition()
        self.frame = self.etag = None
        self.at = 0.0
        self.seq = 0
        self.wanted = 0.0
        self.error = None
        self.stopped = False
        self.process = None
        self.route = None
        self.skip_direct = 0.0  # monotonic time until which the camera isn't tried directly (tunnel.SKIP_DIRECT)
        self.power_saver = lambda: prefs.get()["power_saver"]
        threading.Thread(target=self._run, daemon=True).start()

    def latest(self, etag):
        """Newest picture as (jpeg, etag, unix time), waiting up to LONG_POLL for one other than `etag`."""
        deadline = time.monotonic() + LONG_POLL
        with self.cond:
            self.wanted = time.monotonic()
            self.cond.notify_all()
            while not self.stopped and (self.frame is None or self.etag == etag):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.cond.wait(remaining)
            return self.frame, self.etag, self.at

    def stop(self):
        with self.cond:
            self.stopped = True
            self.cond.notify_all()
        if self.process:
            self.process.kill()

    def _unwatched(self):
        return time.monotonic() - self.wanted > IDLE_STOP

    def _recording(self):
        return bool(self.config.get("record")) and self.config["kind"] in RECORDABLE

    def _idle(self):
        """Nothing for it to do: no one is looking, and it isn't recorded."""
        return self.stopped or self._unwatched() and not self._recording()

    def _keep(self, jpeg):
        with self.cond:
            self.seq += 1
            self.frame, self.etag, self.at = jpeg, f'"{BOOT}-{self.config["id"]}-{self.seq}"', time.time()
            self.cond.notify_all()

    def _run(self):
        while not self.stopped:
            with self.cond:
                while self._idle() and not self.stopped:
                    self.cond.wait()
            if self.stopped:
                return
            try:
                planned = self._snapshots() if self.config["kind"] == "snapshot" else self._stream()
            except NoFFmpeg as e:
                self.error = str(e)
                planned = False
            except Exception as e:  # (never let a camera's thread die)
                self.error = _mask(f"{type(e).__name__}: {e}")
                planned = False
            if planned:
                continue  # (started again at once: what was wanted of it changed)
            with self.cond:
                self.frame = None  # a stopped stream's last picture isn't current
            if not self._idle():
                time.sleep(5)  # (it failed: try again in a moment)

    def _url(self):
        """Where to reach the camera now (_routed), saying when that changes."""
        route, url = _routed(self.config, direct=time.monotonic() >= self.skip_direct)
        if route != self.route and self.config.get("tunnel"):
            print(f"{self.config['name']}: {'reached directly' if route == 'direct' else 'not reachable directly; using its tunnel'}",
                  flush=True)
        self.route = route
        return url

    def _snapshots(self):
        opener = _opener(self.config, self.password)
        url = self._url()
        while not self._idle():
            started = time.monotonic()
            try:
                with opener.open(url, timeout=15) as resp:
                    jpeg = resp.read(20 * 1024 * 1024)
                if picture_type(jpeg):
                    self._keep(jpeg)
                    self.error = None
                else:
                    self.error = "Its address didn't give a picture"
            except (urllib.error.URLError, OSError) as e:
                self.error = _mask(str(getattr(e, "reason", e)))
                return False
            time.sleep(max(0.0, SNAPSHOT_EVERY - (time.monotonic() - started)))
        return False

    def _stream(self):
        """ffmpeg, making pictures while something looks and recording if the camera is recorded: one connection to
        the camera for both (some cameras allow only one). It's started again when what's wanted changes."""
        saving, pictures, record = self.power_saver(), not self._unwatched(), self._recording()
        folder = None
        if record:
            folder = RECORDINGS / self.config["id"]
            folder.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(
            _ffmpeg(self.config, self.password, POWER_SAVER_FPS if saving else WALL_FPS, pictures=pictures, record=folder,
                    url=self._url()),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if pictures else subprocess.DEVNULL, stderr=subprocess.PIPE,
            **paths.NO_WINDOW)
        errors = []
        threading.Thread(target=lambda: errors.extend(self.process.stderr.read().decode(errors="replace").splitlines()[-5:]),
                         daemon=True).start()
        frames, started, planned = 0, time.monotonic(), False
        try:
            if pictures:
                while not self.stopped and (jpeg := read_part(self.process.stdout)):
                    frames += 1
                    self._keep(jpeg)
                    if self._unwatched():  # (no one looking now: recording only, or nothing)
                        planned = record
                        break
                    if frames % 30 == 0 and self.power_saver() != saving:
                        planned = True  # (started again at the other rate)
                        break
            else:  # recording only, until something looks (then pictures are made too) or it stops
                with self.cond:
                    self.frame = None  # (no pictures being made: the last one would only get older)
                    while not self.stopped and self._unwatched() and self.process.poll() is None:
                        self.cond.wait(1)
                planned = not self.stopped and self.process.poll() is None
            if frames or not pictures and time.monotonic() - started > 30:
                self.error = None
        finally:
            self.process.kill()
            self.process.wait()
        failed = not planned and not self.stopped and (pictures and not frames or not pictures and time.monotonic() - started < 30)
        if failed:
            time.sleep(0.2)
            self.error = _explain("\n".join(errors))
            if self.route == "direct" and self.config.get("tunnel") and not frames:
                self.skip_direct = time.monotonic() + tunnel.SKIP_DIRECT  # (something else at its address, maybe)
        return planned


def picture_type(body):
    """A picture's MIME type, or None if it isn't one."""
    return {b"\xff\xd8": "image/jpeg", b"\x89P": "image/png", b"GI": "image/gif"}.get(body[:2])


def stop_all():
    """Stop every camera's ffmpeg (camwall is quitting)."""
    with _lock:
        readers = list(_readers.values())
        _readers.clear()
    for r in readers:
        r.stop()


def frame_headers(at):
    return [("Last-Modified", formatdate(at, usegmt=True)), ("X-Frame-Time", str(round(at * 1000))), ("X-Long-Poll", "1")]


# ---- recordings ----

def recordings(cam_id):
    """A camera's recorded minutes, newest first: [{"file", "start" (unix time), "bytes"}]."""
    folder = RECORDINGS / cam_id
    if not ID.fullmatch(cam_id) or not folder.is_dir():
        return []
    out = []
    for file in folder.glob("*.mp4"):
        if m := SEGMENT.fullmatch(file.name):
            start = time.mktime(time.strptime(f"{m[1]} {m[2]}:{m[3]}:{m[4]}", "%Y-%m-%d %H:%M:%S"))
            out.append({"file": file.name, "start": start, "bytes": file.stat().st_size})
    return sorted(out, key=lambda r: -r["start"])


def recording_file(cam_id, name):
    """A recorded minute's file, or None."""
    if not ID.fullmatch(cam_id) or not SEGMENT.fullmatch(name):
        return None
    file = RECORDINGS / cam_id / name
    return file if file.is_file() else None


def keep_recordings():
    """Forever: drop recorded minutes older than their camera keeps, and while the disk is low the oldest of all,
    down to each camera's last LOW_DISK_KEEP minutes."""
    while True:
        try:
            saved = paths.read_json(FILE) if FILE.exists() else []
            if isinstance(saved, list):  # (unreadable just now, say half-written: nothing is dropped for its sake)
                keep = {str(c.get("id")): c.get("record") or 0 for c in saved if isinstance(c, dict)}
                for folder in RECORDINGS.glob("*") if RECORDINGS.exists() else []:
                    hours = keep.get(folder.name, 0)  # (a camera no longer saved: its recordings go)
                    if not isinstance(hours, (int, float)):
                        continue  # (a camera edited by hand to something that isn't hours: its recordings stay)
                    for file in folder.glob("*.mp4"):
                        if time.time() - file.stat().st_mtime > hours * 3600 + 120:
                            file.unlink(missing_ok=True)
            if shutil.disk_usage(paths.USER).free < DISK_LOW:
                spare = []
                for folder in RECORDINGS.glob("*") if RECORDINGS.exists() else []:
                    spare += sorted(folder.glob("*.mp4"), key=lambda f: f.stat().st_mtime)[:-LOW_DISK_KEEP]
                for file in sorted(spare, key=lambda f: f.stat().st_mtime):
                    if shutil.disk_usage(paths.USER).free >= DISK_LOW:
                        break
                    file.unlink(missing_ok=True)
        except Exception:  # (never let this thread die: recordings would grow until the disk is full)
            pass
        time.sleep(60)


def start_recording():
    """At start: recorded cameras record from now, not from when they're first looked at."""
    for camera in load():
        if camera.get("record") and camera["kind"] in RECORDABLE:
            reader(camera["id"])
    threading.Thread(target=keep_recordings, daemon=True).start()
