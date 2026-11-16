"""camwall and the computer it runs on: starting it when the user logs in (a macOS LaunchAgent, a Windows Startup
shortcut, or an XDG autostart entry), and this computer's addresses on the local network (for phones and tablets)."""

import os
import socket
import subprocess
import sys
from pathlib import Path

from . import paths

LABEL = "com.camwall.app"


def _command():
    """How to start camwall without opening the browser."""
    python = sys.executable
    if sys.platform == "win32" and python.lower().endswith("python.exe"):
        python = python[:-len("python.exe")] + "pythonw.exe"  # (no console window)
    return [python, str(paths.APP / "camwall.py"), "--no-open"]


def _login_file():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "camwall.bat"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart" / "camwall.desktop"


def starts_at_login():
    return _login_file().exists()


def start_at_login(on):
    file = _login_file()
    if not on:
        file.unlink(missing_ok=True)
        return False
    file.parent.mkdir(parents=True, exist_ok=True)
    command = _command()
    if sys.platform == "darwin":
        args = "".join(f"<string>{_xml(a)}</string>" for a in command)
        file.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array>{args}</array>
  <key>RunAtLoad</key><true/>
  <key>WorkingDirectory</key><string>{_xml(str(paths.APP))}</string>
  <key>StandardOutPath</key><string>{_xml(str(paths.USER / "camwall.log"))}</string>
  <key>StandardErrorPath</key><string>{_xml(str(paths.USER / "camwall.log"))}</string>
</dict></plist>
""")
    elif sys.platform == "win32":
        file.write_text('@echo off\r\nstart "" ' + " ".join(f'"{a}"' for a in command) + "\r\n")
    else:
        file.write_text("[Desktop Entry]\nType=Application\nName=camwall\nComment=Live traffic cameras\n"
                        f"Exec={' '.join(_shell(a) for a in command)}\nX-GNOME-Autostart-enabled=true\n")
    return True


def _xml(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _shell(arg):
    return arg if all(c.isalnum() or c in "/._-" for c in arg) else "'" + arg.replace("'", "'\\''") + "'"


def local_addresses():
    """This computer's IPv4 addresses on its local networks (what a phone on the same Wi-Fi would use)."""
    found = set()
    try:  # the address used to reach the internet (no packet is sent)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            found.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    return sorted(a for a in found if a.startswith(("192.168.", "10.")) or a.startswith("172.") and 16 <= int(a.split(".")[1]) <= 31)


def hostname():
    name = socket.gethostname()
    if sys.platform == "darwin":
        try:
            local = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=5).stdout.strip()
            if local:
                return f"{local}.local"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return name
