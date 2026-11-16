"""The map's tiles, fetched here for the pages and kept a week. OpenStreetMap's tile policy asks an app to send a
User-Agent naming it, to keep each tile at least 7 days, and to fetch only the tiles someone is looking at; going
through camwall does all three, whichever provider is set (settings.tiles). Pages ask for /tiles/<provider>/z/x/y, so
that a browser never shows one provider's tiles it kept under another's credit."""

import hashlib
import os
import sys
import threading
import time

from . import paths, relay
from . import settings as prefs

CACHE = paths.USER / "tiles"   # <provider>/<z>/<x>/<y>
KEEP = 7 * 86400               # s a tile is used before it's fetched again
FORGET = 30 * 86400            # s after which a tile not fetched again is deleted
MAX_CACHE = 500 * 1024 ** 2    # bytes of tiles kept at most (the oldest go first)
MAX_TILE = 2 * 1024 ** 2       # bytes a tile may be
FAILED_FOR = 60                # s a tile that couldn't be had isn't asked for again
MAX_ZOOM = 19

_lock = threading.Lock()
_fetching = {}  # file -> a lock held while it's fetched (one fetch for many asks)
_failed = {}    # file -> (until, why)


def provider(address=None):
    """The provider's id: a hash of its tile address."""
    return hashlib.sha256((address or prefs.tiles()["url"]).encode()).hexdigest()[:16]


def for_pages():
    """What the pages need for the map: where its tiles are, and the credit to show (never the address, which may
    hold the user's key)."""
    tiles = prefs.tiles()
    return {"id": provider(tiles["url"]), "credit": tiles["credit"], "link": tiles.get("link")}


def kind(body):
    """A tile's type, from its first bytes; None if it isn't a picture."""
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if body.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    return None


def tile(z, x, y):
    """(body, type) of a map tile, kept or fetched now. ValueError for a tile that can't exist; OSError if it can't be
    had (a tile kept from before is used then, however old)."""
    if not (0 <= z <= MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise ValueError("no such tile")
    address = prefs.tiles()["url"]
    file = CACHE / provider(address) / str(z) / str(x) / str(y)
    with _lock:
        fetching = _fetching.setdefault(file, threading.Lock())
    with fetching:  # (the page asks for many tiles at once, sometimes the same one twice)
        try:
            return _get(file, address, z, x, y)
        finally:
            with _lock:
                _fetching.pop(file, None)


def _get(file, address, z, x, y):
    kept = _kept(file)
    if kept and time.time() - kept[1] < KEEP:
        return kept[0], kind(kept[0])
    until, why = _failed.get(file, (0, None))
    if time.monotonic() < until:
        if kept:
            return kept[0], kind(kept[0])
        raise OSError(why)
    url = address.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
    try:
        status, _, body = relay.fetch(url.replace("{s}", "a").replace("{r}", ""))
        if status != 200 or not kind(body) or len(body) > MAX_TILE:
            raise OSError(f"the map's tile server answered {status}"
                          f"{'' if kind(body) else ' (not a picture)'}{' (too big)' if len(body) > MAX_TILE else ''}")
    except OSError as e:
        now = time.monotonic()
        if len(_failed) > 5000:  # (a long time offline: forget the failures that have run out)
            for old in [k for k, (until, _) in list(_failed.items()) if until < now]:
                _failed.pop(old, None)
        _failed[file] = (now + FAILED_FOR, str(e))
        if kept:
            return kept[0], kind(kept[0])
        raise
    _failed.pop(file, None)
    _keep(file, body)
    return body, kind(body)


def _kept(file):
    """(body, when it was fetched) of a kept tile that's a picture, or None."""
    try:
        body, fetched = file.read_bytes(), file.stat().st_mtime
    except OSError:
        return None
    return (body, fetched) if kind(body) else None


def _keep(file, body):
    """Keep a tile, if it can be: one that can't be written is still shown."""
    part = file.with_name(f"{file.name}.{threading.get_ident()}.part")
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        part.write_bytes(body)
        for tries in range(20):
            try:
                part.replace(file)
                return
            except PermissionError:  # (on Windows, while it's being read)
                if sys.platform != "win32" or tries == 19:
                    raise
                time.sleep(0.05)
    except OSError:
        part.unlink(missing_ok=True)


def forget():
    """Forever, once a day: delete the tiles not fetched again in FORGET, then the oldest while there are more than
    MAX_CACHE bytes of them, and the folders this leaves empty."""
    while True:
        kept = []
        for folder, _, files in os.walk(CACHE, topdown=False):
            for name in files:
                file = os.path.join(folder, name)
                try:
                    stat = os.stat(file)
                    age = time.time() - stat.st_mtime
                    if age > FORGET or name.endswith(".part") and age > 3600:  # (a part left by a failed write)
                        os.unlink(file)
                    else:
                        kept.append((stat.st_mtime, stat.st_size, file))
                except OSError:
                    continue  # (gone meanwhile)
        total = sum(size for _, size, _ in kept)
        for _, size, file in sorted(kept):
            if total <= MAX_CACHE:
                break
            try:
                os.unlink(file)
                total -= size
            except OSError:
                pass
        for folder, _, _ in os.walk(CACHE, topdown=False):
            if folder != str(CACHE):
                try:
                    os.rmdir(folder)  # (only if empty)
                except OSError:
                    pass
        time.sleep(86400)
