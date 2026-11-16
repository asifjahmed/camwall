"""Every public camera camwall knows of: the lists the source modules (sources/) make, as shipped with the app
(data/catalogue/) or as fetched again on this computer (paths.CATALOGUE), whichever is newer.

A camera's key is "<module>/<its id>" ("oh_ohgo/CMH/CCTV2208_East.jpg"). A source is left out of what the pages list
and what the relay fetches when the user has switched it off; when its terms restrict apps like this one and the user
hasn't switched it on; or when its agency asked camwall to stop using it (withdrawn.py), whatever the user chose. A
camera two sources list (the same picture) is listed once, under the source with more cameras (usually the state's own
system) of those that are on; its other key still works, so a set keeps it.
"""

import gzip
import importlib
import json
import re
import threading
import time
import traceback
from collections import Counter
from datetime import datetime, timezone

import sources
from sources import check

from . import paths, withdrawn

SHIPPED = paths.DATA / "catalogue"  # <module>.json.gz
REFRESH_EVERY = 86400  # s: a list in use is fetched again once it's this old
RETRY = 3600           # s after a failed fetch before trying again
KEEP = 0.8             # a fetched list with fewer than this share of the cameras listed before isn't used...
PATIENCE = 7 * 86400  # s: ...while the list before is younger than this (sources' lists come back short at times)
MINE = "mine"          # the module name of the user's own cameras (mine.py)
DETAIL = ("road", "direction", "approach", "county", "city", "refresh", "online")


def _age(fetched):
    try:
        return time.time() - datetime.fromisoformat(fetched).timestamp()
    except (TypeError, ValueError):
        return float("inf")


def _place(cam):
    """A camera's name and where it is, roughly (to ~300 m): another source's copy of it has the same."""
    name = re.sub(r"[^a-z0-9]+", "", cam["name"].lower().replace("@", "at"))
    return f"{name}|{round(cam['lat'] * 300)}|{round(cam['lon'] * 300)}"


PLACEHOLDER = 3     # a picture or video URL this many of one source's cameras share is its "camera unavailable" card
SAME_AS = ("same_as", "duplicate_of", "same_camera_as", "same_picture_as")


def _same_as(cam, module):
    """The keys a source says are the same camera as this one, in its extra: "module:id", or an id of its own."""
    found = []
    for field in SAME_AS:
        value = (cam.get("extra") or {}).get(field)
        for ref in value if isinstance(value, list) else [value] if value else []:
            m = re.match(r"([a-z]{2}_[a-z0-9_]+)[:/ ]+(\S+)", str(ref))
            found.append(f"{m[1]}/{m[2]}" if m else f"{module}/{ref}")
    return found


def _has(cam, what):
    """Whether a camera has a picture, or video: a video's URL may come only from its source's resolve(), when it's
    opened (signed links that expire), and then it's listed with a video_type and no URL."""
    return bool(cam.get(what) or what == "video" and cam.get("video_type"))


def _resolves(module):
    """Whether a source's module gives video links when a camera is opened (resolve())."""
    try:
        return hasattr(importlib.import_module(f"sources.{module}"), "resolve")
    except Exception:
        return False


def _valid(data):
    return isinstance(data, dict) and isinstance(data.get("source"), dict) and isinstance(data.get("cameras"), list) \
        and isinstance(data.get("fetched"), str)


class Catalogue:
    def __init__(self):
        self.lock = threading.RLock()
        self.lists = {}         # module -> {"source", "fetched", "cameras", "origin": "shipped" | "fetched"}
        self.status = {}        # module -> {"tried": time, "error": message or None, "fetching": bool}
        self.cameras = {}       # key -> camera dict, with "module" and "state"
        self.groups = []        # [[key ...]] of the cameras several sources list, best first (see view())
        self._views = {}
        self.version = 0        # goes up whenever the cameras change
        self._listing = None    # (what it was made from, gzipped JSON)
        self._modules = {}      # module -> its SOURCE, for every source module there is

    # ---- loading ----

    def load(self):
        known = set(sources.modules())
        for folder, origin in ((SHIPPED, "shipped"), (paths.CATALOGUE, "fetched")):
            for file in sorted([*folder.glob("*.json"), *folder.glob("*.json.gz")]):
                try:
                    data = json.loads(gzip.decompress(file.read_bytes()) if file.suffix == ".gz" else file.read_bytes())
                except (OSError, ValueError, EOFError):
                    continue
                module = file.name.split(".")[0]
                if not _valid(data) or module not in known:
                    continue  # (a list from a source camwall no longer has: its cameras show as gone)
                before = self.lists.get(module)
                if before is None or _age(data["fetched"]) < _age(before["fetched"]):
                    self.lists[module] = {**data, "origin": origin}
        with self.lock:
            self._index()

    def _index(self):
        """Key every camera, and group the ones several sources list: the same picture or video URL, the same name
        within a few hundred metres, or a source saying so (extra.same_as). A group is listed once (view() says which
        camera, for the sources that are on), and linked to another in it that has what that one lacks (video, say).
        A URL many of one source's cameras share is its "unavailable" card, not one camera."""
        cameras, size = {}, {}
        for module, data in self.lists.items():
            state = data["source"].get("state")
            size[module] = len(data["cameras"])
            resolves = _resolves(module)
            for cam in data["cameras"]:
                if not (isinstance(cam, dict) and isinstance(cam.get("id"), str) and isinstance(cam.get("name"), str)
                        and all(isinstance(cam.get(c), (int, float)) for c in ("lat", "lon"))):
                    continue  # (a saved list edited by hand, or damaged: its broken cameras left out)
                if cam.get("video_type") and not cam.get("video") and not resolves:
                    cam = {k: v for k, v in cam.items() if k != "video_type"}  # (an old list's: no video to be had now)
                cameras[f"{module}/{cam['id']}"] = {**cam, "module": module, "state": cam.get("state") or state}
        parent = {}
        sources_in = {}  # a group's root -> the sources of the cameras in it

        def root(key):
            while parent.get(key, key) != key:
                parent[key] = parent.get(parent[key], parent[key])
                key = parent[key]
            return key

        def join(key, other):
            a, b = root(key), root(other)
            if a != b:
                parent[a] = b
                sources_in[b] = sources_in.pop(a, {cameras[a]["module"]}) | sources_in.get(b, {cameras[b]["module"]})

        shared = Counter((cam["module"], cam.get(what)) for cam in cameras.values() for what in ("image", "video"))
        first = {}  # token -> first key with it
        public = sorted(key for key, cam in cameras.items() if cam["module"] != MINE)  # (the user's own: never taken
        for key in public:                                                         # for a public camera)
            cam = cameras[key]
            for other in _same_as(cam, cam["module"]):
                if other in cameras and other != key:
                    join(key, other)
            for token in (cam.get("image"), cam.get("video")):  # (the same picture or video: the same camera)
                if token and shared[cam["module"], token] < PLACEHOLDER:
                    if token in first:
                        join(key, first[token])
                    else:
                        first[token] = key
        group_sources = lambda key: sources_in.get(root(key), {cameras[root(key)]["module"]})  # noqa: E731
        at = {}  # name and place -> the keys there
        for key in public:  # (then by name and place: two groups only if they share no source, since one source's
            if token := _place(cameras[key]):                       # views of a site can share a name)
                for other in at.setdefault(token, []):
                    if root(key) != root(other) and not group_sources(key) & group_sources(other):
                        join(key, other)
                at[token].append(key)
        groups = {}
        for key in cameras:
            groups.setdefault(root(key), []).append(key)
        grouped = []
        for keys in groups.values():
            if len(keys) > 1:  # (best first: more of pictures and video, then the source with more cameras)
                keys.sort(key=lambda k: (-(_has(cameras[k], "image") + _has(cameras[k], "video")), -size[cameras[k]["module"]], k))
                grouped.append(keys)
        self.cameras, self.groups = cameras, grouped
        self._views = {}
        self.version += 1

    def view(self, settings):
        """For these settings: (keys hidden as copies of a camera listed under another key, {key: the camera from
        another source that has what it lacks}). Of each group, the best camera whose source is on is listed; copies
        from sources that are off never count."""
        made_from = (self.version, json.dumps(settings.get("sources", {}), sort_keys=True))
        if made_from in self._views:
            return self._views[made_from]
        hidden, linked = set(), {}
        for keys in self.groups:
            on = [k for k in keys if self.source_on(self.cameras[k]["module"], settings)]
            hidden.update(k for k in keys if not on or k != on[0])
            if not on:
                continue
            best = self.cameras[on[0]]
            lacking = "video" if not _has(best, "video") else "image" if not _has(best, "image") else None
            if lacking and (other := next((k for k in on[1:] if _has(self.cameras[k], lacking)), None)):
                linked[on[0]] = other
        self._views = {made_from: (hidden, linked)}  # (one set of settings at a time)
        return hidden, linked

    def withdrawn_changed(self):
        """What's withdrawn changed: what the pages list is made again (and they see a new version)."""
        with self.lock:
            self.version += 1
            self._views, self._listing = {}, None

    def media(self, key, settings):
        """1 for a picture, 2 for video, 3 for both, counting a linked camera's."""
        cam, other = self.cameras[key], self.cameras.get(self.view(settings)[1].get(key, ""), {})
        return (1 if _has(cam, "image") or _has(other, "image") else 0) | (2 if _has(cam, "video") or _has(other, "video") else 0)

    def from_source(self, key, field, settings):
        """A field of the SOURCE behind the camera's picture or video (its own, or a linked camera's), if either has it:
        "no_capture" (why its pictures mustn't be saved; an alert saves them), "credit" or "disclaimer"."""
        for what in ("image", "video"):
            if value := self.modules().get(self.part(key, what, settings)["module"], {}).get(field):
                return value

    def no_capture(self, key, settings):
        return self.from_source(key, "no_capture", settings)

    def part(self, key, what, settings):
        """The camera (itself or the one linked to it) that has its "image" or "video"."""
        cam, linked = self.cameras[key], self.view(settings)[1]
        if _has(cam, what) or key not in linked:
            return cam
        return self.cameras[linked[key]]

    def set_mine(self, cameras, source):
        """The user's own cameras (mine.py), listed like a source's."""
        with self.lock:
            self.lists[MINE] = {"source": source, "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "cameras": cameras, "origin": MINE}
            self._index()

    def modules(self):
        """Every source: module -> its SOURCE (from the module, or from its list if the module has gone)."""
        if not self._modules:
            for name in sources.modules():
                try:
                    self._modules[name] = importlib.import_module(f"sources.{name}").SOURCE
                except Exception:
                    print(f"Source {name} doesn't load:\n{traceback.format_exc()}")
        return {**{m: d["source"] for m, d in self.lists.items()}, **self._modules}

    # ---- what's on ----

    def source_on(self, module, settings):
        if module in withdrawn.current():
            return False
        choice = settings.get("sources", {}).get(module)
        if choice is not None:
            return choice
        source = self.modules().get(module)
        return source is not None and not source.get("restricted")

    def get(self, key, settings):
        """A camera by its key, or None if it isn't listed or its source is off."""
        cam = self.cameras.get(key)
        return cam if cam and self.source_on(cam["module"], settings) else None

    def listing(self, settings):
        """Every camera the pages can list, as gzipped JSON: {"version", "cameras": [[key, name, lat, lon, media,
        state, online]]}, media being 1 for a picture, 2 for video, 3 for both."""
        made_from = (self.version, json.dumps(settings.get("sources", {}), sort_keys=True))
        if self._listing and self._listing[0] == made_from:
            return self._listing[1]
        with self.lock:
            on = {m for m in self.lists if self.source_on(m, settings)}
            hidden = self.view(settings)[0]
            rows = [[key, cam["name"], round(cam["lat"], 5), round(cam["lon"], 5),
                     self.media(key, settings), cam["state"],
                     0 if cam.get("online") is False else 1]
                    for key, cam in self.cameras.items() if cam["module"] in on and key not in hidden]
        body = gzip.compress(json.dumps({"version": self.version, "cameras": rows}, separators=(",", ":")).encode(), 6)
        self._listing = (made_from, body)
        return body

    def detail(self, key, settings):
        """What a page shows of one camera (no URLs: it's seen through the relay)."""
        cam = self.get(key, settings)
        if cam is None:
            return None
        source = self.modules().get(cam["module"], {})
        return {"key": key, "name": cam["name"], "lat": cam["lat"], "lon": cam["lon"], "state": cam["state"],
                "image": bool(self.media(key, settings) & 1),
                "video": self.part(key, "video", settings).get("video_type") if self.media(key, settings) & 2 else None,
                **{f: cam[f] for f in DETAIL if cam.get(f) is not None},
                "source": {"module": cam["module"], **{f: source.get(f) for f in ("name", "covers", "site", "terms", "credit",
                                                                                  "disclaimer")}}}

    def summary(self, settings, keys):
        """Every source, for the settings page."""
        out = []
        for module, source in sorted(self.modules().items(), key=lambda item: (str(item[1].get("state")), item[0])):
            if module == MINE:
                continue
            data, status = self.lists.get(module), self.status.get(module, {})
            out.append({
                "module": module, **{f: source.get(f) for f in ("name", "state", "covers", "site", "terms", "restricted",
                                                                  "credit", "disclaimer", "notes")},
                "needs_key": source.get("key"), "has_key": module in keys, "on": self.source_on(module, settings),
                "withdrawn": withdrawn.current().get(module),
                "cameras": len(data["cameras"]) if data else 0, "fetched": data and data["fetched"],
                "origin": data and data["origin"], "error": status.get("error"), "fetching": status.get("fetching", False)})
        return out

    # ---- fetching lists again ----

    def refresh(self, module, keys):
        """Fetch a source's list now. ValueError or OSError if it fails or looks broken; the old list stays."""
        self.status[module] = {**self.status.get(module, {}), "fetching": True}
        try:
            code = importlib.import_module(f"sources.{module}")
            key = keys.get(module)
            if code.SOURCE.get("key") and not key:
                raise ValueError("it needs a key")
            seen, good = set(), []
            for cam in code.cameras(sources.get, key):
                if isinstance(cam, dict) and not check.camera_problems(cam, code.SOURCE) and cam["id"] not in seen:
                    seen.add(cam["id"])
                    good.append(cam)
            before = self.lists.get(module)
            if not good or (before and len(good) < KEEP * len(before["cameras"]) and _age(before["fetched"]) < PATIENCE):
                raise ValueError(f"it listed {len(good)} cameras" + (f", {len(before['cameras'])} before" if before else ""))
            data = {"module": module, "source": code.SOURCE, "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "cameras": good}
            paths.write_json(paths.CATALOGUE / f"{module}.json", data, compact=True)
            with self.lock:
                self.lists[module] = {**data, "origin": "fetched"}
                self._modules[module] = code.SOURCE
                self._index()
            self.status[module] = {"tried": time.time(), "error": None}
            return len(good)
        except Exception as e:
            self.status[module] = {"tried": time.time(), "error": str(e)[:300] or type(e).__name__}
            raise

    def due(self, module):
        data, status = self.lists.get(module), self.status.get(module, {})
        if status.get("fetching") or time.time() - status.get("tried", 0) < RETRY:
            return False
        return data is None or _age(data["fetched"]) > REFRESH_EVERY

    def keep(self, wanted, keys):
        """Forever: fetch again the lists of the sources wanted() names once they're a day old."""
        while True:
            for module in wanted():
                if module != MINE and module in self.modules() and self.due(module):
                    try:
                        n = self.refresh(module, keys())
                        print(f"Camera list from {module}: {n} cameras")
                    except Exception as e:
                        print(f"Camera list from {module} not used ({e}); trying again in an hour")
            time.sleep(60)
