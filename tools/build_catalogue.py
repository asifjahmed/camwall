"""Builds the camera lists shipped with camwall (data/catalogue/<module>.json.gz), so a new install shows every camera at
once; each install then fetches the lists it uses again itself, daily.

    python3 tools/build_catalogue.py              fetch every source now
    python3 tools/build_catalogue.py oh_ohgo ...  just these
    python3 tools/build_catalogue.py --from-out   use what sources.check last saved (sources/out/)
    python3 tools/build_catalogue.py --relabel    keep the shipped cameras, with each source's SOURCE as it is now

Sources whose terms restrict apps like this one, sources that need a key, and sources whose terms forbid copying their
list on (SHIPPED = False) aren't shipped: an install fetches those itself, for where its user lives or when turned on.
"""

import argparse
import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib

import sources
from sources import check

SHIPPED = Path(__file__).resolve().parent.parent / "data" / "catalogue"
OUT = Path(__file__).resolve().parent.parent / "sources" / "out"
KEEP = 0.8  # a list with fewer than this share of the shipped one's cameras is taken to have come back short


def shippable(code):
    """Whether a source's list may be shipped: not restricted, needing no key, not one whose terms forbid copying it on
    (SHIPPED = False), which each install fetches for itself, and not withdrawn at its agency's request."""
    return not code.SOURCE.get("restricted") and not code.SOURCE.get("key") and getattr(code, "SHIPPED", True) \
        and code.__name__.rsplit(".", 1)[-1] not in check.withdrawn()


def shipped(code, cameras):
    """The cameras as shipped. A source whose links are tokens that expire, which its resolve() gives fresh when a
    camera is opened, names them in EXPIRING: "video" (shipped as None) or "image" (shipped without its query)."""
    expiring = getattr(code, "EXPIRING", ())
    out = []
    for cam in cameras:
        if "video" in expiring and cam.get("video"):
            cam = {**cam, "video": None}
        if "image" in expiring and cam.get("image"):
            cam = {**cam, "image": cam["image"].split("?")[0]}
        if cam.get("video_type") and not cam.get("video") and not hasattr(code, "resolve"):
            cam = {k: v for k, v in cam.items() if k != "video_type"}  # (no link, and nothing to give one)
        out.append(cam)
    return out


def fetch(module):
    code = importlib.import_module(f"sources.{module}")
    if not shippable(code):
        return module, None, "not shipped (restricted terms or needs a key)"
    started = time.monotonic()
    seen, good = set(), []
    for cam in code.cameras(sources.get, None):
        if isinstance(cam, dict) and not check.camera_problems(cam, code.SOURCE) and cam["id"] not in seen:
            seen.add(cam["id"])
            good.append(cam)
    if not good:
        raise ValueError("no cameras")
    return module, {"module": module, "source": code.SOURCE, "cameras": shipped(code, good),
                    "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")}, f"{len(good)} cameras in {time.monotonic() - started:.0f} s"


def from_out(module):
    data = json.loads((OUT / f"{module}.json").read_text())
    code = importlib.import_module(f"sources.{module}")
    if not shippable(code):
        return module, None, "not shipped (restricted terms or needs a key)"
    return module, {"module": module, "source": code.SOURCE, "cameras": shipped(code, data["cameras"]),
                    "fetched": data["fetched"]}, f"{len(data['cameras'])} cameras (from sources/out)"


def relabel(module):
    if module not in sources.modules():
        return module, None, "not shipped (its module is gone)"
    data = json.loads(gzip.decompress((SHIPPED / f"{module}.json.gz").read_bytes()))
    code = importlib.import_module(f"sources.{module}")
    if not shippable(code):
        return module, None, "not shipped (restricted terms or needs a key)"
    return module, {**data, "source": code.SOURCE, "cameras": shipped(code, data["cameras"])}, \
        f"{len(data['cameras'])} cameras (relabelled)"


def short(module, data):
    """Why a list isn't used in place of the one shipped now, if it has far fewer cameras (as app/catalogue.py)."""
    try:
        before = json.loads(gzip.decompress((SHIPPED / f"{module}.json.gz").read_bytes()))["cameras"]
    except (OSError, ValueError, KeyError):
        return None
    if len(data["cameras"]) < KEEP * len(before):
        return f"KEPT the shipped list: this one has {len(data['cameras'])} cameras, the shipped one {len(before)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("modules", nargs="*")
    parser.add_argument("--from-out", action="store_true")
    parser.add_argument("--relabel", action="store_true")
    args = parser.parse_args()
    names = args.modules or (sorted(p.stem for p in OUT.glob("*.json")) if args.from_out else
                             sorted(p.name[:-len(".json.gz")] for p in SHIPPED.glob("*.json.gz")) if args.relabel else
                             sources.modules())
    SHIPPED.mkdir(parents=True, exist_ok=True)
    total, failed = 0, []

    def one(module):
        try:
            return (from_out if args.from_out else relabel if args.relabel else fetch)(module)
        except Exception as e:
            return module, None, f"FAILED: {str(e)[:200]}"

    with ThreadPoolExecutor(8) as pool:
        for module, data, note in pool.map(one, names):
            if data and (kept := short(module, data)):
                print(f"{module}: {kept}")
                failed.append(module)
                continue
            print(f"{module}: {note}")
            if data:
                (SHIPPED / f"{module}.json.gz").write_bytes(gzip.compress(json.dumps(data, separators=(",", ":")).encode(), 9, mtime=0))
                (SHIPPED / f"{module}.json").unlink(missing_ok=True)
                total += len(data["cameras"])
            elif note.startswith("not shipped"):
                (SHIPPED / f"{module}.json.gz").unlink(missing_ok=True)
                (SHIPPED / f"{module}.json").unlink(missing_ok=True)
            else:
                failed.append(module)
    print(f"\n{total:,} cameras shipped in {SHIPPED}" + (f"; failed: {', '.join(failed)}" if failed else ""))


if __name__ == "__main__":
    main()
