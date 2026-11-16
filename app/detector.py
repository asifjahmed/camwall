"""Running camwall's detector (the detector package), which needs heavy libraries (torch and the models' packages) that
camwall itself doesn't: they're installed into their own Python environment in the user's camwall folder when the user
asks (Settings › Alerts), or CAMWALL_DETECTOR_PYTHON names a Python that has them.

The detector runs while alerts are on and some camera has them; it's started again if it stops (after a pause that
grows if it keeps stopping), and stopped when it's no longer wanted."""

import collections
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import paths, sets
from . import settings as prefs

ENV = paths.USER / "detector-env"
READY = ENV / "camwall-ready"  # written once the install has finished
PACKAGES = ["torch", "torchvision", "open_clip_torch", "transformers", "ultralytics", "pillow"]  # (transformers: SigLIP's tokenizer)
CHECK_EVERY = 3
RESTART_AFTER = (5, 600)       # s before starting it again after it stops: first, at most
LOG_LINES = 200


def env_python():
    return ENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def env_works():
    """Whether the detector's environment still works: it's tied to the Python that made it, which a camwall moved to
    another folder, or updated to another Python, no longer has. (If not, setting it up again makes it anew.)"""
    try:
        made = dict(line.split(" = ", 1) for line in (ENV / "pyvenv.cfg").read_text(encoding="utf-8", errors="replace")
                    .splitlines() if " = " in line)
    except (OSError, ValueError):
        return False
    version = made.get("version") or made.get("version_info") or ""
    return env_python().exists() and Path(made.get("home", "")).is_dir() \
        and version.startswith(f"{sys.version_info[0]}.{sys.version_info[1]}.")


class Supervisor:
    def __init__(self, port):
        self.port = port
        self.process = None
        self.started = None
        self.stops = 0            # times in a row it stopped soon after starting
        self.next_start = 0.0
        self.error = None
        self.output = collections.deque(maxlen=LOG_LINES)
        self.installing = None    # {"step", "done", "failed", "lines"} while (and after) installing
        self.retired = False      # camwall is quitting: never started again
        self.lock = threading.Lock()

    def python(self):
        given = os.environ.get("CAMWALL_DETECTOR_PYTHON")
        if given:
            return given
        return str(env_python()) if READY.exists() and env_works() else None

    def wanted(self):
        """Alerts are on and some camera in a set alerts for something."""
        if not prefs.get()["detector"]:
            return False
        setup = sets.load()
        used = {key for s in setup["sets"] for key in s["cameras"]}
        return any(kinds for key, kinds in setup["alerts"].items() if key in used)

    def running(self):
        return self.process is not None and self.process.poll() is None

    def keep(self):
        """Forever: start and stop the detector as it's wanted."""
        while True:
            try:
                self.check()
            except Exception as e:  # (never let the supervisor die)
                self.error = f"{type(e).__name__}: {e}"
            time.sleep(CHECK_EVERY)

    def retire(self):
        """Stop it for good (camwall is quitting)."""
        with self.lock:
            self.retired = True
            self.stop()

    def check(self):
        with self.lock:
            if self.retired:
                return
            want = self.wanted() and self.python() is not None
            if self.process is not None and self.process.poll() is not None:
                code = self.process.returncode
                ran = time.monotonic() - self.started
                self.stops = self.stops + 1 if ran < 120 else 1
                wait = min(RESTART_AFTER[1], RESTART_AFTER[0] * 2 ** (self.stops - 1))
                self.error = f"It stopped (exit code {code}); starting it again in {wait} s"
                self.next_start = time.monotonic() + wait
                self.process = None
                print(f"Detector stopped (exit code {code})")
            if want and self.process is None and time.monotonic() >= self.next_start:
                self.start()
            elif not want and self.process is not None:
                self.stop()

    def start(self):
        self.process = subprocess.Popen(
            [self.python(), "-u", "-m", "detector", "--port", str(self.port)], cwd=paths.APP,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
            env={**os.environ, "CAMWALL_DATA": str(paths.USER), "PYTHONWARNINGS": "ignore"}, **paths.NO_WINDOW)
        self.started = time.monotonic()
        self.error = None
        threading.Thread(target=self._read, args=(self.process,), daemon=True).start()
        print("Detector started")

    def _read(self, process):
        for line in process.stdout:
            line = line.rstrip()
            if line and "warn" not in line.lower():
                self.output.append(line)
                print(f"detector: {line}", flush=True)

    def stop(self):
        process, self.process = self.process, None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
        self.stops = 0
        self.error = None
        print("Detector stopped (not wanted now)")

    def status(self):
        return {"installed": self.python() is not None, "running": self.running(), "wanted": self.wanted(),
                "error": self.error, "log": list(self.output)[-40:], "installing": self.installing,
                "packages": PACKAGES}

    # ---- installing its libraries ----

    def install(self):
        if self.installing and not self.installing["done"]:
            return
        self.installing = {"step": "Starting", "done": False, "failed": None, "lines": []}
        threading.Thread(target=self._install, daemon=True).start()

    def _install(self):
        state = self.installing
        steps = [
            ("Making its Python environment", [sys.executable, "-m", "venv", "--clear", str(ENV)]),
            ("Updating pip", [str(env_python()), "-m", "pip", "install", "--upgrade", "pip"]),
            ("Downloading the models' libraries (about 1 GB; this takes a while)",
             [str(env_python()), "-m", "pip", "install", "--progress-bar", "off", *PACKAGES]),
        ]
        try:
            for step, command in steps:
                state["step"] = step
                state["lines"].append(f"== {step}")
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                                           **paths.NO_WINDOW)
                for line in process.stdout:
                    state["lines"] = (state["lines"] + [line.rstrip()])[-60:]
                if process.wait():
                    raise RuntimeError(f"{step} failed (exit code {process.returncode})")
            READY.write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
            state["step"] = "Installed: the detector starts by itself, and downloads its models the first time"
        except Exception as e:
            state["failed"] = str(e)
            state["step"] = "Failed"
        finally:
            state["done"] = True
