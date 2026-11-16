"""Watching the cameras the user has given alerts, through camwall's own server: it asks it every WATCH_EVERY s which
cameras those are (/api/watch), fetches their new pictures from its relay (or, for a camera with only video, a frame
every few seconds of it, with ffmpeg), and judges every vehicle in them (models.py).

An alert comes once per vehicle, and no more than once a COOLDOWN per camera and kind: a snapshot is saved under
detections/<date>/ in the user's camwall folder, it's added to alerts.json (the wall shows it), and the user is told as
their settings say (notify.py). Near misses are kept under detections/candidates/ for a while, to see what it
nearly took for one. How much of the computer each camera takes goes to load.json, for the Cameras page.
"""

import http.client
import io
import json
import queue
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageOps

from app import paths

from . import models, notify
from .learn import Learner, pack

WATCH_EVERY = 5               # s between asks of which cameras to watch
PICTURE_EVERY = 2.0           # s between checks of a camera's picture (the relay says when it hasn't changed)
MINE_EVERY = 0.25             # s between pictures judged from the user's own cameras (their video makes 10 a second)
VIDEO_EVERY = 2.0             # s between frames taken from a camera's video
SAVER_EVERY = 6.0             # both, in power saver
CONFIRM = (2, 6.0)            # video: this many hits within this many s
SAME_VEHICLE = (0.3, 120)     # a hit overlapping an alerted box this much, within this many s, is that vehicle again
COOLDOWN = 60                 # s between alerts of one kind from one camera
REUSE = (0.85, 10.0)          # a box overlapping a judged one this much, judged this recently, keeps its scores
NEAR_EVERY = 600              # s between near misses saved per camera
NEAR_KEEP = 14 * 86400        # s near misses are kept
ALERTS_KEPT = 300
LOAD_EVERY = 30
DETECTIONS = paths.USER / "detections"
ALERTS = paths.USER / "alerts.json"
REFERENCES = paths.USER / "police-photos"   # the user's photos of local police vehicles, if any
YOLO_WEIGHTS = paths.USER / "models" / "yolo11s.pt"
SAFE_NAME = re.compile(r"[^\w .,-]+")


def log(msg):
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def spoken(name):
    """A camera's name as it's said: "I-35 at University Ave, 4094" -> "I-35 at University Ave"."""
    name = re.sub(r",?\s*\(?[A-Z]?\d{3,}\)?$", "", name)
    return re.sub(r"\s*\((?:[A-Z]\d+|\d+)\)", "", name).strip() or name


class Server:
    """camwall's server, which the detector reaches on this computer."""

    def __init__(self, port):
        self.port = port

    def get(self, path, headers=None, timeout=30):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request("GET", path, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.headers, resp.read()
        finally:
            conn.close()

    def json(self, path):
        status, _, body = self.get(path)
        if status != 200:
            raise OSError(f"{path}: {status}")
        return json.loads(body)


class Frames(threading.Thread):
    """Fetches one camera's new frames and keeps the newest for the detector."""

    def __init__(self, server, cam, ready, saver):
        super().__init__(daemon=True)
        self.server, self.ready, self.saver = server, ready, saver
        self.key, self.name, self.kinds = cam["key"], cam["name"], tuple(cam["kinds"])
        self.lat, self.lon = cam.get("lat"), cam.get("lon")
        self.video = None if cam["media"] & 1 else cam.get("video")  # (pictures, where it has them, are lighter)
        self.mine = bool(cam.get("mine"))  # the user's own: a new picture many times a second
        self.latest = None  # (jpeg, at)
        self.lock = threading.Lock()
        self.stopped = False
        self.process = None

    def take(self):
        with self.lock:
            frame, self.latest = self.latest, None
            return frame

    def keep(self, jpeg):
        with self.lock:
            self.latest = (jpeg, time.time())
        self.ready.put(self)

    def stop(self):
        self.stopped = True
        if self.process:
            self.process.kill()

    def run(self):
        if self.video:
            self.run_video()
        else:
            self.run_pictures()

    def run_pictures(self):
        etag = None
        while not self.stopped:
            started = time.monotonic()
            try:
                status, headers, body = self.server.get(f"/cam/{quote(self.key, safe='')}", {"If-None-Match": etag} if etag else {})
                if status == 200:
                    etag = headers.get("ETag")
                    self.keep(body)
                elif status != 304:
                    time.sleep(2 if self.mine else 10)  # (the camera is down or starting; the relay says so)
            except (OSError, http.client.HTTPException) as e:
                log(f"{self.name}: camwall isn't answering ({e}); trying again")
                time.sleep(5)
            every = (1.0 if self.mine else SAVER_EVERY) if self.saver() else (MINE_EVERY if self.mine else PICTURE_EVERY)
            time.sleep(max(0.0, every - (time.monotonic() - started)))

    def run_video(self):
        """ffmpeg reads the camera's video through the relay and hands over a frame every few seconds."""
        if not shutil.which("ffmpeg"):
            log(f"{self.name}: has only video, which needs ffmpeg (not found); not watched")
            return
        url = (f"http://127.0.0.1:{self.server.port}/hls/{quote(self.key, safe='')}/index.m3u8" if self.video == "hls"
               else f"http://127.0.0.1:{self.server.port}/mjpeg/{quote(self.key, safe='')}")
        while not self.stopped:
            every = SAVER_EVERY if self.saver() else VIDEO_EVERY
            self.process = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-i", url, "-vf", f"fps=1/{every}", "-q:v", "4", "-f", "mpjpeg", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **paths.NO_WINDOW)
            while not self.stopped and (jpeg := read_part(self.process.stdout)):
                self.keep(jpeg)
            self.process.kill()
            self.process.wait()
            if not self.stopped:
                time.sleep(15)  # (the video stopped: start again in a while)


def read_part(stream):
    """One JPEG from ffmpeg's multipart (mpjpeg) output; None when the stream ends."""
    length = None
    while line := stream.readline():
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
        elif line == b"\r\n" and length is not None:
            return stream.read(length)
    return None


class Watcher:
    def __init__(self, detector, server):
        self.detector, self.server = detector, server
        self.settings = {}
        self.judged = {}      # key -> [(box, scores, at)]
        self.hits = {}        # (key, kind) -> [(at, box)]
        self.alerted = {}     # (key, kind) -> [[box, last seen]]
        self.last_alert = {}
        self.saved_near = {}
        self.alerts = (paths.read_json(ALERTS, {}) or {}).get("alerts", [])
        self.learner = Learner(log)

    def saver(self):
        return bool(self.settings.get("power_saver"))

    def process(self, cam, jpeg, at):
        """Judge one frame; returns the vehicles judged afresh."""
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        night = models.dark(at, cam.lat, cam.lon)
        boxes = [b for b in self.detector.vehicles(img) if b[2] - b[0] >= models.MIN_WIDTH]
        previous = [j for j in self.judged.get(cam.key, []) if at - j[2] < REUSE[1]]
        results, fresh = [], []
        for box in boxes:  # parked and queued vehicles keep their recent scores
            match = max(previous, key=lambda j: models.iou(box, j[0]), default=None)
            if match and models.iou(box, match[0]) >= REUSE[0]:
                results.append((box, match[1], match[2], match[3]))
            else:
                fresh.append(box)
        if fresh:
            crops = [models.crop(img, b) for b in fresh]
            if night:
                crops = [ImageOps.grayscale(c).convert("RGB") for c in crops]
            scored, embeddings = self.detector.judge(crops)
            for scores, learned in zip(scored, self.learner.score(embeddings)):
                scores.update(learned)
            results += [(b, s, at, e) for b, s, e in zip(fresh, scored, embeddings)]
            for scores, embedding in zip(scored, embeddings):
                if models.ordinary(scores):
                    self.learner.add_ordinary(embedding)
        self.judged[cam.key] = results
        for box, scores, _, embedding in results:
            kind = models.verdict(scores, box[2] - box[0])
            if kind in cam.kinds and not self.learner.like_wrong(kind, embedding):
                self.hit(cam, kind, box, img, at, scores, night)
            elif (kind in cam.kinds or models.near_miss(scores, cam.kinds)) and not self.beside_alert(cam.key, box, at):
                self.save_near(cam, img, box, scores, at, night)
        return len(fresh)

    def embeddings(self, img, box, night):
        """The vehicle's embeddings as the learner keeps them: as seen, mirrored, and (by day) both in greyscale."""
        crop = models.crop(img, box)
        crops = [crop, ImageOps.mirror(crop)]
        crops = [ImageOps.grayscale(c).convert("RGB") for c in crops] if night else crops + [
            ImageOps.grayscale(c).convert("RGB") for c in crops]
        return pack(self.detector.embed(crops))

    def hit(self, cam, kind, box, img, at, scores, night=False):
        key = (cam.key, kind)
        if cam.video or cam.mine:  # frames come often: needs repeat hits close together
            track = [h for h in self.hits.get(key, []) if at - h[0] <= CONFIRM[1]] + [(at, box)]
            self.hits[key] = track
            if len(track) < CONFIRM[0]:
                return
        seen = [s for s in self.alerted.get(key, []) if at - s[1] <= SAME_VEHICLE[1]]
        self.alerted[key] = seen
        for s in seen:
            if models.iou(box, s[0]) >= SAME_VEHICLE[0]:  # already announced; it's still there
                s[0], s[1] = box, at
                return
        if at - self.last_alert.get(key, 0) < COOLDOWN:
            return
        seen.append([box, at])
        self.last_alert[key] = at
        path = snapshot(DETECTIONS / f"{datetime.now():%Y-%m-%d}", cam, kind, img, box, scores,
                        embeddings=self.embeddings(img, box, night))
        message = f"{models.LABELS[kind]} at {spoken(cam.name)}"
        self.record(cam, kind, message, path, at)
        loud = not self.settings.get("muted") and not quiet_now(self.settings.get("quiet"))
        log(f"ALERT {message} ({models.tag(scores)})" + ("" if loud else " (silent)"))
        threading.Thread(target=notify.announce, daemon=True, args=(message,), kwargs={
            "sound": loud and self.settings.get("sound", True), "voice": loud and self.settings.get("voice", True),
            "desktop": self.settings.get("desktop", True)}).start()

    def record(self, cam, kind, message, path, at):
        """Add an alert to ALERTS, which the wall shows."""
        self.alerts.append({"id": (self.alerts[-1]["id"] + 1) if self.alerts else 1, "at": round(at, 1), "key": cam.key,
                            "camera": cam.name, "kind": kind, "message": message,
                            "snapshot": path.relative_to(DETECTIONS).as_posix()})
        self.alerts = self.alerts[-ALERTS_KEPT:]
        try:
            paths.write_json(ALERTS, {"alerts": self.alerts}, compact=True)
        except OSError as e:
            log(f"alert not recorded ({e})")

    def beside_alert(self, key, box, at):
        """Whether a box overlaps a vehicle alerted here and still in view (its close-up shows some of that one)."""
        return any(at - seen <= SAME_VEHICLE[1] and models.overlap(box, alerted) >= 0.1
                   for (k, _), boxes in self.alerted.items() if k == key for alerted, seen in boxes)

    def save_near(self, cam, img, box, scores, at, night=False):
        if at - self.saved_near.get(cam.key, 0) < NEAR_EVERY:
            return
        self.saved_near[cam.key] = at
        snapshot(DETECTIONS / "candidates" / f"{datetime.now():%Y-%m-%d}", cam, "near", img, box, scores, boxed=False,
                 embeddings=self.embeddings(img, box, night))


def quiet_now(quiet):
    """Whether it's within the user's quiet hours ({"from": "22:00", "to": "07:00"}) now."""
    if not quiet:
        return False
    now = datetime.now().strftime("%H:%M")
    start, end = quiet["from"], quiet["to"]
    return start <= now < end if start <= end else now >= start or now < end


def snapshot(folder, cam, kind, img, box, scores, boxed=True, embeddings=None):
    """The frame (the vehicle boxed in red for an alert), a close-up of it (.crop.jpg) and its scores (.json)."""
    folder.mkdir(parents=True, exist_ok=True)
    name = SAFE_NAME.sub(" ", cam.name)[:60].strip()
    path = folder / f"{datetime.now():%H%M%S} {name} {kind}.jpg"
    marked = img.copy()
    ImageDraw.Draw(marked).rectangle(box, outline=(255, 40, 40), width=4)
    models.crop(marked, box, pad=0.6).save(path.with_name(path.stem + ".crop.jpg"), quality=85)
    (marked if boxed else img).save(path, quality=85)
    path.with_suffix(".json").write_text(json.dumps({"camera": cam.name, "key": cam.key, "kind": kind,
                                                     "box": [round(v, 1) for v in box],
                                                     "scores": {k: round(v, 4) for k, v in scores.items()},
                                                     **({"embeddings": embeddings} if embeddings else {})}))
    return path


def prune_near():
    """Near misses older than NEAR_KEEP go."""
    cutoff = time.time() - NEAR_KEEP
    for file in (DETECTIONS / "candidates").glob("*/*"):
        try:
            if file.stat().st_mtime < cutoff:
                file.unlink()
        except OSError:
            pass


def follow(server, cameras, ready, watcher):
    """Start and stop watching cameras as the user's alerts change; returns the settings that came with them."""
    wanted = server.json("/api/watch")
    watcher.settings = wanted["settings"]
    by_key = {c["key"]: c for c in wanted["cameras"]}
    for key in cameras.keys() - by_key.keys():
        cameras.pop(key).stop()
        log(f"stopped watching {key}")
    for key, c in by_key.items():
        cam = cameras.get(key)
        if cam and cam.name == c["name"] and (cam.video is None) == bool(c["media"] & 1) and cam.mine == bool(c.get("mine")):
            if cam.kinds != tuple(c["kinds"]):
                cam.kinds = tuple(c["kinds"])
                log(f"watching {cam.name} for {', '.join(models.LABELS[k].lower() for k in cam.kinds)}")
            continue
        if cam:
            cam.stop()
        cam = cameras[key] = Frames(server, c, ready, watcher.saver)
        cam.start()
        log(f"watching {cam.name} for {', '.join(models.LABELS[k].lower() for k in cam.kinds)}"
            + (f" (its {cam.video} video)" if cam.video else ""))


def report_load(load, span):
    cameras = {key: {"name": name, "fps": round(n / span, 3), "ms": round(1000 * busy / n), "share": round(busy / span, 4)}
               for key, (name, n, busy) in load.items()}
    paths.write_json(paths.LOAD, {"at": round(time.time()), "busy": round(sum(c["share"] for c in cameras.values()), 4),
                                  "cameras": cameras}, compact=True)


def run(port):
    server = Server(port)
    REFERENCES.mkdir(parents=True, exist_ok=True)
    YOLO_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    references = sorted(p for p in REFERENCES.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    detector = models.Detector(YOLO_WEIGHTS, references, log)
    watcher = Watcher(detector, server)
    ready = queue.Queue()
    cameras, followed, pruned = {}, 0.0, 0.0
    load, measuring = {}, time.monotonic()
    while True:
        if time.monotonic() - followed >= WATCH_EVERY:
            try:
                follow(server, cameras, ready, watcher)
            except (OSError, ValueError, KeyError, http.client.HTTPException) as e:
                log(f"camwall isn't answering ({e})")
            followed = time.monotonic()
        if time.monotonic() - pruned >= 3600:
            prune_near()
            pruned = time.monotonic()
        try:
            cam = ready.get(timeout=1)
        except queue.Empty:
            cam = None
        watcher.learner.refresh()  # (trains again in the background if the marks changed)
        frame = cam and not cam.stopped and cam.take()
        if frame:
            started = time.perf_counter()
            try:
                watcher.process(cam, *frame)
            except Exception as e:  # keep watching the other cameras
                log(f"{cam.name}: frame skipped ({e!r})")
            spent = load.setdefault(cam.key, [cam.name, 0, 0.0])
            spent[1] += 1
            spent[2] += time.perf_counter() - started
        if time.monotonic() - measuring >= LOAD_EVERY:
            try:
                report_load(load, time.monotonic() - measuring)
            except OSError as e:
                log(f"load not reported ({e})")
            load, measuring = {}, time.monotonic()
