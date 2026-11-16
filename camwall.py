#!/usr/bin/env python3
"""camwall: live traffic cameras from across the United States, on your own computer.

    python3 camwall.py              start it and open it in the browser
    python3 camwall.py --no-open    start it without opening the browser
    python3 camwall.py --port 8790  on another port (default 8780)

If camwall is already running, this just opens it. Settings and camera sets are kept in the user's app-data folder
(CAMWALL_DATA to use another).
"""

import argparse
import json
import signal
import sys
import threading
import urllib.request
import webbrowser

from app import VERSION, paths, server

PORT = 8780


def running(port):
    """Whether camwall already answers on this port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=2) as resp:
            return json.load(resp).get("app") == "camwall"
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-open", action="store_true", help="don't open the browser")
    args = parser.parse_args()
    if sys.stdout is None or sys.stderr is None:  # (pythonw, on Windows: no console, so what's printed goes to a file)
        paths.USER.mkdir(parents=True, exist_ok=True)
        log = open(paths.USER / "camwall.log", "a", buffering=1, encoding="utf-8", errors="replace")
        sys.stdout, sys.stderr = sys.stdout or log, sys.stderr or log
    url = f"http://127.0.0.1:{args.port}/"
    if running(args.port):
        print(f"camwall is already running: {url}")
        if not args.no_open:
            webbrowser.open(url)
        return
    try:
        httpd = server.start(args.port)
    except OSError as e:
        sys.exit(f"Can't use port {args.port} ({e.strerror}); try --port with another")
    print(f"camwall {VERSION}: {url}   (Ctrl-C to stop; your settings are in {paths.USER})")
    if not args.no_open:
        webbrowser.open(url)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=httpd.shutdown, daemon=True).start())
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()  # (the detector, and ffmpeg reading the user's own cameras)


if __name__ == "__main__":
    main()
