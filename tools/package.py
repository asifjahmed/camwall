"""Builds camwall's downloads in dist/: each has its own Python (python-build-standalone), so nothing else needs
installing to run it (the detector installs its own libraries when the user turns it on).

    python3 tools/package.py mac        camwall-<version>-mac-apple-silicon.dmg and -mac-intel.dmg (needs a Mac)
    python3 tools/package.py windows    camwall-<version>-windows.zip
    python3 tools/package.py linux      camwall-<version>-linux.tar.gz
    python3 tools/package.py all

Run tools/build_catalogue.py first, so the downloads carry today's camera lists. The Mac app isn't signed: until it's
signed and notarized with an Apple Developer ID, macOS asks the user to allow it (System Settings › Privacy &
Security › Open Anyway) the first time.
"""

import hashlib
import io
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
CACHE = DIST / "cache"
sys.path.insert(0, str(ROOT))
from app import VERSION  # noqa: E402

PYTHON_RELEASE = "20261026"
PYTHON_VERSION = "3.13.18"
PYTHONS = {
    "mac-apple-silicon": "aarch64-apple-darwin",
    "mac-intel": "x86_64-apple-darwin",
    "windows": "x86_64-pc-windows-msvc",
    "linux": "x86_64-unknown-linux-gnu",
}
BASE = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PYTHON_RELEASE}"
PAYLOAD = ["camwall.py", "app", "web", "data", "sources", "detector", "README.md", "LICENSE", "THIRD_PARTY.md"]
SKIP = {"__pycache__", "out", ".DS_Store"}


def python_for(target):
    """The standalone Python for a target, downloaded once and checked against the release's SHA256SUMS."""
    name = f"cpython-{PYTHON_VERSION}+{PYTHON_RELEASE}-{PYTHONS[target]}-install_only_stripped.tar.gz"
    CACHE.mkdir(parents=True, exist_ok=True)
    file = CACHE / name
    sums = CACHE / f"SHA256SUMS-{PYTHON_RELEASE}"
    if not sums.exists():
        urllib.request.urlretrieve(f"{BASE}/SHA256SUMS", sums)
    expected = next((line.split()[0] for line in sums.read_text().splitlines() if line.endswith(name)), None)
    if not expected:
        sys.exit(f"{name} isn't in the release's SHA256SUMS")
    if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
        print(f"Downloading {name}")
        urllib.request.urlretrieve(f"{BASE}/{name.replace('+', '%2B')}", file)
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            file.unlink()
            sys.exit(f"{name}: checksum doesn't match")
    return file


def copy_payload(to):
    to.mkdir(parents=True, exist_ok=True)
    for item in PAYLOAD:
        source = ROOT / item
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, to / item, ignore=lambda d, names: [n for n in names if n in SKIP or n.endswith(".pyc")])
        else:
            shutil.copy2(source, to / item)


def _anonymous(member):
    """A file as packaged: owned by no one in particular (not the builder's account)."""
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    return member


def unpack_python(target, to):
    with tarfile.open(python_for(target)) as tar:
        tar.extractall(to, filter="tar")  # (makes to/python)


def icon_png(size, out):
    """The app icon as a PNG (Quick Look renders the SVG)."""
    tmp = DIST / "icon-render"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", str(tmp), str(ROOT / "web" / "icon.svg")], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.move(tmp / "icon.svg.png", out)
    shutil.rmtree(tmp)


def mac_icns(out):
    iconset = DIST / "camwall.iconset"
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir(parents=True)
    big = DIST / "icon-1024.png"
    icon_png(1024, big)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            subprocess.run(["sips", "-z", str(size * scale), str(size * scale), str(big), "--out",
                            str(iconset / f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png")], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
    shutil.rmtree(iconset)
    big.unlink()


INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>camwall</string>
  <key>CFBundleDisplayName</key><string>camwall</string>
  <key>CFBundleIdentifier</key><string>com.camwall.app</string>
  <key>CFBundleVersion</key><string>{version}</string>
  <key>CFBundleShortVersionString</key><string>{version}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>camwall</string>
  <key>CFBundleIconFile</key><string>camwall</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
"""

MAC_LAUNCHER = """#!/bin/bash
# Starts camwall (or, if it's running, opens it) with the Python inside this app.
here="$(cd "$(dirname "$0")/../Resources" && pwd)"
exec "$here/python/bin/python3" "$here/app/camwall.py" "$@"
"""


def build_mac(target):
    name = f"camwall-{VERSION}-{target}"
    work = DIST / name
    shutil.rmtree(work, ignore_errors=True)
    app = work / "camwall.app" / "Contents"
    (app / "MacOS").mkdir(parents=True)
    (app / "Resources").mkdir()
    (app / "Info.plist").write_text(INFO_PLIST.format(version=VERSION))
    launcher = app / "MacOS" / "camwall"
    launcher.write_text(MAC_LAUNCHER)
    launcher.chmod(0o755)
    mac_icns(app / "Resources" / "camwall.icns")
    unpack_python(target, app / "Resources")
    copy_payload(app / "Resources" / "app")
    (work / "Applications").symlink_to("/Applications")
    dmg = DIST / f"{name}.dmg"
    dmg.unlink(missing_ok=True)
    subprocess.run(["hdiutil", "create", "-volname", "camwall", "-srcfolder", str(work), "-ov", "-format", "UDZO",
                    str(dmg)], check=True, stdout=subprocess.DEVNULL)
    print(f"{dmg} ({dmg.stat().st_size // 1024 // 1024} MB)")
    return work


WINDOWS_LAUNCHER = """@echo off
rem Starts camwall (or, if it's running, opens it) with the Python in this folder.
start "" "%~dp0python\\pythonw.exe" "%~dp0app\\camwall.py" %*
"""

UNIX_LAUNCHER = """#!/bin/sh
# Starts camwall (or, if it's running, opens it) with the Python in this folder.
here="$(cd "$(dirname "$0")" && pwd)"
exec "$here/python/bin/python3" "$here/app/camwall.py" "$@"
"""

READ_ME = """camwall {version}

Live traffic cameras from across the United States, with alerts, on your own computer.

{how}

camwall opens in your web browser at http://127.0.0.1:8780/. Your settings and camera walls are kept in your user
folder, not here, so you can replace this folder with a newer version at any time.
"""


def build_folder(target, launcher_name, launcher, how):
    name = f"camwall-{VERSION}-{target}"
    work = DIST / name
    shutil.rmtree(work, ignore_errors=True)
    folder = work / "camwall"
    unpack_python(target, folder)
    copy_payload(folder / "app")
    (folder / launcher_name).write_text(launcher)
    (folder / launcher_name).chmod(0o755)
    (folder / "README.txt").write_text(READ_ME.format(version=VERSION, how=how))
    return work, folder


def build_windows():
    work, folder = build_folder("windows", "camwall.bat", WINDOWS_LAUNCHER,
                                "To start it, double-click camwall.bat. (Windows may ask you to allow it the first time.)")
    out = DIST / f"camwall-{VERSION}-windows.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for file in sorted(folder.rglob("*")):
            z.write(file, file.relative_to(work))
    print(f"{out} ({out.stat().st_size // 1024 // 1024} MB)")


def build_linux():
    """Built straight from the Python's archive into the download (its terminfo has names that differ only in case,
    which a Mac's disk can't hold side by side)."""
    name = f"camwall-{VERSION}-linux"
    work = DIST / name
    shutil.rmtree(work, ignore_errors=True)
    copy_payload(work / "app")
    out = DIST / f"{name}.tar.gz"
    with tarfile.open(out, "w:gz") as tar, tarfile.open(python_for("linux")) as python:
        for member in python.getmembers():
            data = python.extractfile(member) if member.isfile() else None
            member.name = f"camwall/{member.name}"
            tar.addfile(member, data)
        tar.add(work / "app", arcname="camwall/app", filter=_anonymous)
        for file_name, text, mode in (("camwall", UNIX_LAUNCHER, 0o755),
                                      ("README.txt", READ_ME.format(version=VERSION, how="To start it, run ./camwall in this folder."), 0o644)):
            info = tarfile.TarInfo(f"camwall/{file_name}")
            body = text.encode()
            info.size, info.mode = len(body), mode
            tar.addfile(info, io.BytesIO(body))
    shutil.rmtree(work)
    print(f"{out} ({out.stat().st_size // 1024 // 1024} MB)")


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("mac", "all"):
        if sys.platform != "darwin":
            print("The Mac app can only be built on a Mac; skipped")
        else:
            build_mac("mac-apple-silicon")
            build_mac("mac-intel")
    if what in ("windows", "all"):
        build_windows()
    if what in ("linux", "all"):
        build_linux()


if __name__ == "__main__":
    main()
