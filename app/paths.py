"""Where camwall's files are: its own (read-only once installed) and the user's (settings, camera sets, the camera lists
fetched on this computer)."""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
WEB = APP / "web"          # the pages
DATA = APP / "data"        # shipped with the app: places.json, catalogue/<module>.json (the camera lists when built)


def user_dir():
    """The user's camwall folder: CAMWALL_DATA if set, else the system's place for app data."""
    if os.environ.get("CAMWALL_DATA"):
        return Path(os.environ["CAMWALL_DATA"]).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "camwall"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "camwall"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "camwall"


USER = user_dir()
SETTINGS = USER / "settings.json"   # the user's preferences (settings.py)
SETUP = USER / "setup.json"         # camera sets and alerts (setup.py)
KEYS = USER / "keys.json"           # API keys for sources that need one: {module: key}; never sent to a page
CATALOGUE = USER / "catalogue"      # camera lists fetched here: <module>.json, newer than the shipped ones
LOAD = USER / "load.json"           # the detector's report of how busy it is

# For starting a console program (ffmpeg, pip) without a console window of its own on Windows, where camwall runs
# under pythonw and has none.
NO_WINDOW = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32" else {}

_write_lock = threading.Lock()


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def write_json(path, value, private=False, compact=False):
    """Write a JSON file whole or not at all (a crash mid-write leaves the old one). private: readable by this user
    only. compact: no indenting (for big lists)."""
    with _write_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(value, separators=(",", ":")) if compact else json.dumps(value, indent=1))
        if private:
            os.chmod(tmp, 0o600)
        for tries in range(20):
            try:
                tmp.replace(path)
                break
            except PermissionError:  # (on Windows, while another thread or the detector is reading it)
                if sys.platform != "win32" or tries == 19:
                    raise
                time.sleep(0.05)
