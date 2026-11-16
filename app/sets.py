"""The user's camera sets, the walls they switch between, and which cameras alert for what (paths.SETUP). They're
changed on the cameras and welcome pages; the detector follows them.

setup.json: {"sets": [{"id", "name", "cameras": [key ...]}], "alerts": {key: [kind ...]}, "cameras": {key: {"name"}}},
"cameras" naming every camera in a set, for the detector and for a camera whose source no longer lists it."""

import re
import threading

from . import paths

KINDS = ("police", "ambulance", "fire")
SET_ID = re.compile(r"[a-z0-9]{1,16}")
MAX_SETS = 20
MAX_SET_CAMERAS = 64
SET_NAME_LENGTH = 40
KEY_LENGTH = 300
FIRST = {"id": "home", "name": "My cameras", "cameras": []}

_lock = threading.Lock()


def load():
    saved = paths.read_json(paths.SETUP)
    if not isinstance(saved, dict):
        saved = {}
    sets = [s for s in saved.get("sets") or [] if isinstance(s, dict) and isinstance(s.get("id"), str)
            and isinstance(s.get("name"), str) and isinstance(s.get("cameras"), list)
            and all(isinstance(key, str) for key in s["cameras"])]  # (one edited by hand or half-written: left out)
    alerts, cameras = saved.get("alerts"), saved.get("cameras")
    return {"sets": sets or [dict(FIRST)],
            "alerts": {k: v for k, v in alerts.items() if isinstance(v, list)} if isinstance(alerts, dict) else {},
            "cameras": {k: v for k, v in cameras.items() if isinstance(v, dict)} if isinstance(cameras, dict) else {}}


def for_pages(catalogue, settings):
    """The sets, the alerts, and what the pages show of each camera in a set: {key: {"name", "state", "media",
    "no_alerts", "credit", "disclaimer", "gone"}} ("no_alerts" when its source's terms forbid saving its pictures;
    "credit" and "disclaimer" when they ask for them to be shown; "gone" when its source no longer lists it, or is
    switched off)."""
    setup = load()
    cameras = {}
    for key in {key for s in setup["sets"] for key in s["cameras"]}:
        cam = catalogue.get(key, settings)
        if cam:
            cameras[key] = {"name": cam["name"], "state": cam["state"], "lat": cam["lat"], "lon": cam["lon"],
                            "media": catalogue.media(key, settings),
                            "video": catalogue.part(key, "video", settings).get("video_type")
                            if catalogue.media(key, settings) & 2 else None,
                            "no_alerts": catalogue.no_capture(key, settings),
                            "credit": catalogue.from_source(key, "credit", settings),
                            "disclaimer": catalogue.from_source(key, "disclaimer", settings)}
        else:
            cameras[key] = {"name": setup["cameras"].get(key, {}).get("name") or "A camera no longer listed", "gone": True}
    return {"sets": setup["sets"], "alerts": setup["alerts"], "cameras": cameras}


def save(body, catalogue, settings):
    """Replace the sets and alerts: {"sets": [{"id", "name", "cameras": [key ...]}], "alerts": {key: [kind ...]}}.
    ValueError if they won't do. A camera already in a set may stay while its source doesn't list it (it may come
    back); a new one must be listed."""
    sets, alerts = body["sets"], body["alerts"]
    if not isinstance(sets, list) or not 1 <= len(sets) <= MAX_SETS or not isinstance(alerts, dict):
        raise ValueError("sets")
    if not all(isinstance(kinds, list) and set(kinds) <= set(KINDS) for kinds in alerts.values()):
        raise ValueError("alerts")
    with _lock:
        before = load()
        known = {key for s in before["sets"] for key in s["cameras"]}
        kept = []
        for s in sets:
            name, keys = s["name"].strip(), s["cameras"]
            if not SET_ID.fullmatch(s["id"]) or not 1 <= len(name) <= SET_NAME_LENGTH or not name.isprintable() \
                    or not isinstance(keys, list) or len(keys) > MAX_SET_CAMERAS or len(set(keys)) != len(keys) \
                    or not all(isinstance(key, str) and len(key) <= KEY_LENGTH
                               and (key in known or catalogue.get(key, settings)) for key in keys):
                raise ValueError("set")
            kept.append({"id": s["id"], "name": name, "cameras": keys})
        if len({s["id"] for s in kept}) != len(kept):
            raise ValueError("set ids")
        used = {key for s in kept for key in s["cameras"]}
        names = {}
        for key in sorted(used):
            cam = catalogue.get(key, settings)
            names[key] = {"name": cam["name"]} if cam else before["cameras"].get(key, {"name": "A camera no longer listed"})
        paths.write_json(paths.SETUP, {
            "sets": kept,
            "alerts": {key: [k for k in KINDS if k in kinds] for key, kinds in alerts.items()
                       if key in used and kinds and not (catalogue.get(key, settings) and catalogue.no_capture(key, settings))},
            "cameras": names})
    return for_pages(catalogue, settings)
