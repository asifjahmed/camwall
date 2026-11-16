"""Sources withdrawn at their agencies' request. When an agency asks camwall to stop using its cameras, its source is
named in data/withdrawn.json in camwall's repository; every copy of camwall reads that file from GitHub once a day and
turns those sources off, whatever its user chose, so a removal reaches the copies already installed, not only new
downloads. The file can only turn sources off. A copy that can't reach GitHub uses the list it last read (and the one
it shipped with).

    {"withdrawn": {"<module>": "why, as the settings page shows it"}}
"""

import json
import re
import threading
import time

from . import paths, relay

URL = "https://raw.githubusercontent.com/asifjahmed/camwall/main/data/withdrawn.json"
SHIPPED = paths.DATA / "withdrawn.json"
KEPT = paths.USER / "withdrawn.json"  # the last list read from GitHub
CHECK_EVERY = 86400  # s
RETRY = 3600         # s after a failed check
MAX_SIZE = 256 * 1024
MODULE = re.compile(r"[a-z]{2}_[a-z0-9_]{1,60}")

_lock = threading.Lock()
_withdrawn = None  # module -> why


def parse(body):
    """{module: why} from the file's bytes; ValueError if it isn't such a list."""
    if len(body) > MAX_SIZE:
        raise ValueError("too big")
    try:
        data = json.loads(body)
    except RecursionError:
        raise ValueError("not JSON") from None
    if not isinstance(data, dict) or not isinstance(data.get("withdrawn"), dict):
        raise ValueError("not a list of withdrawn sources")
    return {module: (why if isinstance(why, str) else "")[:300] for module, why in data["withdrawn"].items()
            if MODULE.fullmatch(module)}


def _read(file):
    try:
        return parse(file.read_bytes())
    except (OSError, ValueError):
        return {}


def current():
    """{module: why} of every source withdrawn: those in the list shipped with this copy, and in the last one read."""
    global _withdrawn
    with _lock:
        if _withdrawn is None:
            _withdrawn = {**_read(SHIPPED), **_read(KEPT)}
        return _withdrawn


def check():
    """Read the list from GitHub now. Whether that changed what's withdrawn; OSError or ValueError if it can't be had
    (what's withdrawn stays as it was)."""
    global _withdrawn
    status, _, body = relay.fetch(URL)
    if status != 200:
        raise OSError(f"GitHub answered {status}")
    fetched = parse(body)
    paths.write_json(KEPT, {"withdrawn": fetched})
    before = current()
    with _lock:
        _withdrawn = {**_read(SHIPPED), **fetched}
        return _withdrawn != before


def keep(changed):
    """Forever: check the list once a day (an hour after a failure), calling changed() when it changes."""
    while True:
        try:
            if check():
                changed()
            wait = CHECK_EVERY
        except Exception as e:
            print(f"The list of withdrawn sources wasn't read ({e}); trying again in an hour")
            wait = RETRY
        time.sleep(wait)
