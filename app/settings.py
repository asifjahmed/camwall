"""The user's preferences (paths.SETTINGS), changed on the settings and welcome pages, and the API keys for sources
that need one (paths.KEYS, which no page is ever sent)."""

import re
import threading

from . import paths

DEFAULTS = {
    "welcomed": False,      # the welcome has been gone through (until then the wall opens it)
    "home": None,           # where the user is: {"label": "Ames, IA", "lat", "lon", "state": "IA"}
    "theme": "auto",        # the pages' colours: "auto" (as the system), "dark" or "light"
    "units": "mi",          # distances in "mi" or "km"
    "fit": "contain",       # a picture in its tile: "contain" (all of it) or "cover" (filling the tile)
    "labels": True,         # camera names on the wall
    "cycle": 0,             # s between switches to the next wall, for a screen left showing them (0: no switching)
    "sources": {},          # module -> True or False: a source switched on or off here
    "detector": True,       # watch the cameras with alerts (when the detector is installed)
    "power_saver": False,   # lighter detection, for a laptop on battery
    "muted": False,         # alerts make no sound and don't speak
    "sound": True,          # an alert chimes
    "voice": True,          # and says what was seen where
    "desktop": True,        # and shows a notification
    "quiet": None,          # {"from": "22:00", "to": "07:00"}: alerts are silent then, as when muted
    "network": False,       # phones and tablets on the local network may pair with camwall (devices.py)
    "tiles": None,          # the map's tiles: {"url": "https://…/{z}/{x}/{y}.png", "credit", "link"}, else OSM
}
OSM = {"url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "credit": "© OpenStreetMap contributors",
       "link": "https://www.openstreetmap.org/copyright"}
TILE_URL = re.compile(r"https://(?:\{s\}\.)?[A-Za-z0-9.-]+(?::(\d{1,5}))?/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%{}-]*")
LINK = re.compile(r"https://[A-Za-z0-9.-]+(?::\d{1,5})?(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?")
THEMES = ("auto", "dark", "light")
UNITS = ("mi", "km")
FITS = ("contain", "cover")
CYCLES = (0, 15, 30, 60, 120, 300)
FLAGS = ("welcomed", "labels", "detector", "power_saver", "muted", "sound", "voice", "desktop", "network")
CLOCK = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
LABEL_LENGTH = 80
MODULE = re.compile(r"[a-z0-9_]{1,60}")
KEY_LENGTH = 400
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH "
             "OK OR PA PR RI SC SD TN TX UT VT VA WA WV WI WY".split())

_lock = threading.Lock()
_settings = None


def get():
    """The settings as they are now (a copy)."""
    global _settings
    with _lock:
        if _settings is None:
            saved = paths.read_json(paths.SETTINGS, {})
            _settings = dict(DEFAULTS)
            if isinstance(saved, dict):
                for name, value in saved.items():
                    try:
                        _settings.update(_checked(name, value))
                    except (ValueError, TypeError, KeyError):
                        pass  # (a setting from another version, or edited by hand)
        return dict(_settings)


def _checked(name, value):
    if name in FLAGS:
        if not isinstance(value, bool):
            raise ValueError(name)
    elif name == "theme" and value not in THEMES or name == "units" and value not in UNITS \
            or name == "fit" and value not in FITS or name == "cycle" and (value not in CYCLES or isinstance(value, bool)):
        raise ValueError(name)
    elif name == "home":
        if value is not None:
            label, lat, lon, state = value["label"], value["lat"], value["lon"], value["state"]
            if not (isinstance(label, str) and 0 < len(label) <= LABEL_LENGTH and label.isprintable()
                    and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lat, lon))
                    and -90 <= lat <= 90 and -180 <= lon <= 180 and state in STATES):
                raise ValueError(name)
            value = {"label": label, "lat": float(lat), "lon": float(lon), "state": state}
    elif name == "sources":
        if not isinstance(value, dict) or not all(MODULE.fullmatch(k) and (v is None or isinstance(v, bool)) for k, v in value.items()):
            raise ValueError(name)
    elif name == "quiet":
        if value is not None:
            if not (CLOCK.fullmatch(value["from"]) and CLOCK.fullmatch(value["to"])):
                raise ValueError(name)
            value = {"from": value["from"], "to": value["to"]}
    elif name == "tiles":
        if value is not None:
            url, credit, link = value["url"], value["credit"], value.get("link") or None
            address = TILE_URL.fullmatch(url) if isinstance(url, str) and len(url) <= 400 else None
            if not (address and int(address[1] or 443) <= 65535 and all(part in url for part in ("{z}", "{x}", "{y}"))
                    and isinstance(credit, str) and 0 < len(credit.strip()) <= 200 and credit.isprintable()
                    and (link is None or isinstance(link, str) and len(link) <= 300 and LINK.fullmatch(link))):
                raise ValueError(name)
            value = {"url": url, "credit": credit.strip(), "link": link}
    elif name not in DEFAULTS:
        raise KeyError(name)
    return {name: value}


def update(changes):
    """Change some settings ({name: value}); ValueError for a value that won't do. A source switched to None goes back
    to its default. Returns them all."""
    if not isinstance(changes, dict):
        raise ValueError("settings")
    checked = {}
    for name, value in changes.items():
        checked.update(_checked(name, value))
    get()  # (loaded)
    with _lock:
        if "sources" in checked:  # (switching one source keeps the others as they are)
            merged = {**_settings["sources"], **checked["sources"]}
            checked["sources"] = {k: v for k, v in merged.items() if v is not None}
        _settings.update(checked)
        paths.write_json(paths.SETTINGS, _settings)
        return dict(_settings)


def tiles():
    """The map's tiles: the provider set on the settings page, else OpenStreetMap's."""
    return get()["tiles"] or OSM


# ---- API keys ----

def keys():
    saved = paths.read_json(paths.KEYS, {})
    return {k: v for k, v in saved.items() if isinstance(v, str)} if isinstance(saved, dict) else {}


def set_key(module, key):
    """Keep (or with key None, forget) the API key for a source."""
    if not MODULE.fullmatch(module or "") or key is not None and not (
            isinstance(key, str) and 0 < len(key.strip()) <= KEY_LENGTH and key.strip().isprintable()):
        raise ValueError("key")
    with _lock:
        saved = keys()
        if key is None:
            saved.pop(module, None)
        else:
            saved[module] = key.strip()
        paths.write_json(paths.KEYS, saved, private=True)
    return sorted(saved)

