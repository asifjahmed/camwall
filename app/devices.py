"""Phones, tablets and TVs on the local network. When the user lets them in (Settings › Phones and tablets), camwall
also listens on all of this computer's addresses, on the next port up. A device is let in once it has been paired
with a code shown on this computer's Settings page; it then keeps a cookie naming it (only a hash of which is kept
here). Pairing locks for a while after a few wrong codes."""

import hashlib
import secrets
import threading
import time

from . import paths

DEVICES = paths.USER / "devices.json"  # {hash of token: {"id", "name", "paired", "seen"}}
CODE_FOR = 600       # s a pairing code works
MAX_WRONG = 5        # wrong codes before pairing locks
LOCKED_FOR = 300     # s it stays locked
NAME_LENGTH = 60
COOKIE = "camwall_device"
COOKIE_AGE = 400 * 86400
SEEN_EVERY = 3600    # s between saves of when a device was last seen

_lock = threading.Lock()
_code = None         # (code, until)
_wrong = 0
_locked_until = 0.0


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


_cache = (None, {})  # (devices.json's modification time, its contents)


def _load():
    """The paired devices (read again only when the file has changed: a paired phone asks many times a second)."""
    global _cache
    try:
        stamp = DEVICES.stat().st_mtime_ns
    except OSError:
        return {}
    if stamp != _cache[0]:
        saved = paths.read_json(DEVICES, {})
        _cache = (stamp, {h: d for h, d in saved.items() if isinstance(d, dict)} if isinstance(saved, dict) else {})
    return {h: dict(d) for h, d in _cache[1].items()}


def _save(devices):
    global _cache
    paths.write_json(DEVICES, devices, private=True)
    _cache = (None, {})  # (read again next time, even where a file's time is too coarse to have changed)


def new_code():
    """A fresh six-digit code for pairing a device, and how many seconds it works for. (A lock from wrong guesses
    stays: a new code mustn't give a guesser more tries.)"""
    global _code
    with _lock:
        _code = (f"{secrets.randbelow(1_000_000):06d}", time.monotonic() + CODE_FOR)
        return {"code": _code[0], "seconds": CODE_FOR}


def pair(code, name):
    """A new device's token for the right code; PermissionError for a wrong or expired one, or while locked."""
    global _code, _wrong, _locked_until
    if not isinstance(code, str) or not isinstance(name, str):
        raise ValueError("pairing")
    name = " ".join(name.split())[:NAME_LENGTH] or "A device"
    if not name.isprintable():
        raise ValueError("name")
    with _lock:
        now = time.monotonic()
        if now < _locked_until:
            raise PermissionError("Too many wrong codes: try again in a few minutes")
        if not _code or now > _code[1] or not secrets.compare_digest(code.strip(), _code[0]):
            _wrong += 1
            if _wrong >= MAX_WRONG:
                _locked_until, _wrong, _code = now + LOCKED_FOR, 0, None
            raise PermissionError("That code isn't right, or has run out: get a new one on the computer running camwall")
        _code = None  # (a code pairs one device)
        token = secrets.token_urlsafe(32)
        devices = _load()
        devices[_hash(token)] = {"id": secrets.token_hex(4), "name": name, "paired": int(time.time()), "seen": int(time.time())}
        _save(devices)
        return token


def check(token):
    """Whether a cookie's token is a paired device's (and note when it was seen)."""
    if not token:
        return False
    with _lock:
        devices = _load()
        device = devices.get(_hash(token))
        if device and time.time() - device.get("seen", 0) > SEEN_EVERY:
            device["seen"] = int(time.time())
            _save(devices)
        return device is not None


def listing():
    return sorted(({k: d[k] for k in ("id", "name", "paired", "seen")} for d in _load().values()), key=lambda d: -d["paired"])


def remove(device_id):
    with _lock:
        devices = {h: d for h, d in _load().items() if d.get("id") != device_id}
        _save(devices)
