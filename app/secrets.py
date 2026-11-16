"""Passwords for the user's own cameras, kept in the system's keychain where there is one: the macOS keychain (through
`security`, given on its standard input so the password never shows in a process list), the Secret Service on Linux
(`secret-tool`), or the Windows Credential Manager. Without one, a file only this user can read (paths.USER /
"passwords.json"). No page is ever sent one."""

import ctypes
import json
import os
import shutil
import subprocess
import sys

from . import paths

SERVICE = "camwall"
FALLBACK = paths.USER / "passwords.json"


def _quote(text):
    """For `security -i`, which splits its input like a shell."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _mac_set(account, password):
    command = f"add-generic-password -U -a {_quote(account)} -s {_quote(SERVICE)} -w {_quote(password)}\n"
    result = subprocess.run(["security", "-i"], input=command, capture_output=True, text=True, timeout=20)
    if result.returncode or "error" in result.stderr.lower():
        raise OSError("the keychain wouldn't keep it")


def _mac_get(account):
    result = subprocess.run(["security", "find-generic-password", "-a", account, "-s", SERVICE, "-w"],
                            capture_output=True, text=True, timeout=20)
    return result.stdout.rstrip("\n") if result.returncode == 0 else None


def _mac_delete(account):
    subprocess.run(["security", "delete-generic-password", "-a", account, "-s", SERVICE], capture_output=True, timeout=20)


def _linux_set(account, password):
    result = subprocess.run(["secret-tool", "store", "--label", f"camwall: {account}", "service", SERVICE, "account", account],
                            input=password, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise OSError("the keyring wouldn't keep it")


def _linux_get(account):
    result = subprocess.run(["secret-tool", "lookup", "service", SERVICE, "account", account], capture_output=True, text=True, timeout=20)
    return result.stdout if result.returncode == 0 and result.stdout else None


def _linux_delete(account):
    subprocess.run(["secret-tool", "clear", "service", SERVICE, "account", account], capture_output=True, timeout=20)


class _Credential(ctypes.Structure):
    _fields_ = [("Flags", ctypes.c_uint32), ("Type", ctypes.c_uint32), ("TargetName", ctypes.c_wchar_p),
                ("Comment", ctypes.c_wchar_p), ("LastWritten", ctypes.c_uint64), ("CredentialBlobSize", ctypes.c_uint32),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_char)), ("Persist", ctypes.c_uint32),
                ("AttributeCount", ctypes.c_uint32), ("Attributes", ctypes.c_void_p), ("TargetAlias", ctypes.c_wchar_p),
                ("UserName", ctypes.c_wchar_p)]


def _win_target(account):
    return f"{SERVICE}:{account}"


def _win_set(account, password):
    blob = password.encode("utf-16-le")
    cred = _Credential(Type=1, TargetName=_win_target(account), CredentialBlobSize=len(blob),
                       CredentialBlob=ctypes.cast(ctypes.create_string_buffer(blob, len(blob)), ctypes.POINTER(ctypes.c_char)),
                       Persist=2, UserName=account)
    if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(cred), 0):
        raise OSError("the Credential Manager wouldn't keep it")


def _win_get(account):
    found = ctypes.POINTER(_Credential)()
    if not ctypes.windll.advapi32.CredReadW(_win_target(account), 1, 0, ctypes.byref(found)):
        return None
    try:
        cred = found.contents
        return ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize).decode("utf-16-le")
    finally:
        ctypes.windll.advapi32.CredFree(found)


def _win_delete(account):
    ctypes.windll.advapi32.CredDeleteW(_win_target(account), 1, 0)


def _store():
    if sys.platform == "darwin" and shutil.which("security"):
        return _mac_set, _mac_get, _mac_delete
    if sys.platform == "win32":
        return _win_set, _win_get, _win_delete
    if shutil.which("secret-tool") and os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return _linux_set, _linux_get, _linux_delete
    return None


def _file():
    saved = paths.read_json(FALLBACK, {})
    return saved if isinstance(saved, dict) else {}


def put(account, password):
    store = _store()
    if store:
        try:
            store[0](account, password)
            return
        except (OSError, subprocess.SubprocessError):
            pass  # (no keychain after all: the file)
    saved = _file()
    saved[account] = password
    paths.write_json(FALLBACK, saved, private=True)


def get(account):
    store = _store()
    if store:
        try:
            found = store[1](account)
            if found is not None:
                return found
        except (OSError, subprocess.SubprocessError):
            pass
    return _file().get(account)


def delete(account):
    store = _store()
    if store:
        try:
            store[2](account)
        except (OSError, subprocess.SubprocessError):
            pass
    saved = _file()
    if saved.pop(account, None) is not None:
        paths.write_json(FALLBACK, saved, private=True)
