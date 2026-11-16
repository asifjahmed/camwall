"""Checks a camera source: runs it, validates what it gives, tries some of its pictures and video, and saves its list
to sources/out/<module>.json.

    python3 -m sources.check oh_ohgo              # check one source (and try 5 cameras' pictures and video)
    python3 -m sources.check oh_ohgo --media 20   # try 20
    python3 -m sources.check --all                # every source, a line each
    python3 -m sources.check --all --unrestricted # every source whose terms don't restrict apps like this one
    python3 -m sources.check --all --crawler      # and leave out those whose robots.txt asks crawlers to stay away

A source that needs a key gets it from the environment, as CAMWALL_KEY_<MODULE> (CAMWALL_KEY_NY_511NY).
"""

import argparse
import base64
import importlib
import json
import os
import random
import sys
import time
import traceback
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import sources

OUT = Path(__file__).parent / "out"
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH "
             "OK OR PA PR RI SC SD TN TX UT VT VA WA WV WI WY".split())
US = (17.5, 71.5, -179.9, -64.5)  # south, north, west, east: Puerto Rico to Alaska
FIELDS = {"id", "name", "lat", "lon", "image", "video", "video_type", "state", "road", "direction", "approach", "county",
          "city", "refresh", "online", "extra"}
SOURCE_FIELDS = {"name", "state", "covers", "site", "terms", "key", "headers", "restricted", "no_capture", "credit",
                 "disclaimer", "notes", "cache_bust", "image_json"}
PEEK = 256 * 1024  # bytes read of a video stream
LONGEST = {"id": 200, "name": 200, "road": 200, "direction": 100, "approach": 100, "county": 100, "city": 100,
           "image": 2000, "video": 2000, "extra": 4000}  # characters (the longest listed now: a name of 120)
DEAD_OK = 0.25     # share of the cameras tried that may fail (agencies list dead cameras as working) for a source to pass


def source_problems(source):
    p = [f"SOURCE has no {f}" for f in ("name", "state", "covers", "site") if not source.get(f)]
    states = source.get("state") if isinstance(source.get("state"), list) else [source.get("state")]
    p += [f"SOURCE state {s!r} isn't a state" for s in states if s not in STATES]
    p += [f"SOURCE has an unknown field {f!r}" for f in set(source) - SOURCE_FIELDS]
    if not isinstance(source.get("headers") or {}, dict):
        p.append("SOURCE headers isn't a dict")
    return p


def camera_problems(cam, source):
    if not isinstance(cam, dict):
        return ["not a dict"]
    p = []
    if not isinstance(cam.get("id"), str) or not cam["id"].strip():
        p.append("no id (a string)")
    if not isinstance(cam.get("name"), str) or not cam["name"].strip():
        p.append("no name")
    lat, lon = cam.get("lat"), cam.get("lon")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lat, lon)):
        p.append("no lat/lon (floats)")
    elif not (US[0] <= lat <= US[1] and US[2] <= lon <= US[3]):
        p.append("outside the US")
    if not cam.get("image") and not cam.get("video") and not cam.get("video_type"):  # (video_type alone: resolve() gives it)
        p.append("no image or video")
    for field in ("image", "video"):
        url = cam.get(field)
        if url is not None and not (isinstance(url, str) and url.startswith(("https://", "http://"))):
            p.append(f"{field} isn't a URL")
    if cam.get("video") and cam.get("video_type") not in ("hls", "mjpeg"):
        p.append("video_type isn't hls or mjpeg")
    state = cam.get("state") or (source.get("state") if isinstance(source.get("state"), str) else None)
    if state not in STATES:
        p.append("no state")
    if set(cam) - FIELDS:
        p.append("unknown field " + ", ".join(sorted(set(cam) - FIELDS)))
    if cam.get("refresh") is not None and not (isinstance(cam["refresh"], (int, float)) and not isinstance(cam["refresh"], bool)
                                               and 0 < cam["refresh"] <= 86400):
        p.append("refresh isn't a number of seconds")
    if cam.get("video_type") is not None and cam["video_type"] not in ("hls", "mjpeg"):
        p.append("video_type isn't hls or mjpeg")
    if cam.get("online") is not None and not isinstance(cam["online"], bool):
        p.append("online isn't true or false")
    for field, most in LONGEST.items():  # (a list that's gone wrong, or hostile, isn't sent to every page)
        value = cam.get(field)
        if value is not None and len(value if isinstance(value, str) else json.dumps(value, default=str)) > most:
            p.append(f"{field} is too long")
    return p


def kind_of(body):
    if body[:2] == b"\xff\xd8":
        return "jpeg"
    if body[:4] == b"\x89PNG":
        return "png"
    if body[:4] == b"GIF8":
        return "gif"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "webp"
    return None


def peek(url, headers):
    """The first bytes of a stream that may never end (MJPEG)."""
    request = urllib.request.Request(url, headers={"User-Agent": sources.USER_AGENT, **headers})
    with urllib.request.urlopen(request, timeout=sources.TIMEOUT) as resp:
        return resp.read(PEEK)


def try_image(url, headers, json_field=None):
    body = sources.get(url, headers=headers)
    if json_field:
        body = base64.b64decode(json.loads(body).get(json_field) or "")
    kind = kind_of(body)
    if not kind:
        raise OSError(f"not a picture ({len(body)} bytes starting {body[:24]!r})")
    return f"{kind} {len(body) // 1024} KB"


def try_hls(url, headers):
    text = sources.get(url, headers=headers).decode(errors="replace")
    if not text.startswith("#EXTM3U"):
        raise OSError(f"not an HLS playlist ({text[:60]!r})")
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        raise OSError("an empty playlist")
    if "#EXT-X-STREAM-INF" in text:  # a master playlist: its first variant
        url = urljoin(url, lines[0])
        text = sources.get(url, headers=headers).decode(errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
        if not lines:
            raise OSError("an empty variant playlist")
    segment = sources.get(urljoin(url, lines[-1]), headers=headers)
    if not (segment[:1] == b"\x47" or segment[4:8] in (b"ftyp", b"styp", b"moof", b"sidx")):
        raise OSError(f"a segment that isn't MPEG-TS or MP4 ({segment[:16]!r})")
    return f"hls, segment {len(segment) // 1024} KB"


def try_mjpeg(url, headers):
    body = peek(url, headers)
    if b"\xff\xd8" not in body:
        raise OSError(f"no JPEG frame in the first {len(body) // 1024} KB")
    return f"mjpeg, {len(body) // 1024} KB read"


def try_media(module, cam, key):
    headers = module.SOURCE.get("headers") or {}
    if hasattr(module, "resolve"):
        cam = {**cam, **module.resolve(sources.get, cam, key)}
    results = []
    if cam.get("image"):
        results.append("image " + try_image(cam["image"], headers, module.SOURCE.get("image_json")))
    if cam.get("video"):
        results.append("video " + (try_hls if cam.get("video_type") == "hls" else try_mjpeg)(cam["video"], headers))
    return "; ".join(results)


SEED = None


def check(name, media=5, save=True, quiet=False):
    """Runs one source. True if all went well."""
    say = (lambda *a: None) if quiet else print
    try:
        module = importlib.import_module(f"sources.{name}")
    except Exception:
        print(f"FAIL {name}: doesn't import\n{traceback.format_exc()}")
        return False
    source = getattr(module, "SOURCE", None)
    if not isinstance(source, dict) or not callable(getattr(module, "cameras", None)):
        print(f"FAIL {name}: needs SOURCE (a dict) and cameras(get, key=None)")
        return False
    problems = source_problems(source)
    key = os.environ.get(f"CAMWALL_KEY_{name.upper()}")
    if source.get("key") and not key:
        print(f"FAIL {name}: needs a key ({source['key']}); set CAMWALL_KEY_{name.upper()} to check it")
        return False
    started = time.monotonic()
    try:
        cams = list(module.cameras(sources.get, key))
    except Exception:
        print(f"FAIL {name}: cameras() failed after {time.monotonic() - started:.1f} s\n{traceback.format_exc()}")
        return False
    seconds = time.monotonic() - started
    bad = Counter()
    for cam in cams:
        for problem in camera_problems(cam, source):
            bad[problem] += 1
    ids = Counter(cam.get("id") for cam in cams if isinstance(cam, dict))
    duplicates = {i: n for i, n in ids.items() if n > 1}
    good = [c for c in cams if isinstance(c, dict) and not camera_problems(c, source)]
    online = [c for c in good if c.get("online") is not False]
    images = sum(1 for c in good if c.get("image"))
    videos = Counter(c.get("video_type") for c in good if c.get("video") or c.get("video_type"))
    say(f"{name}: {source.get('name')} ({source.get('state')}): {len(cams)} cameras in {seconds:.1f} s; "
        f"{images} with pictures, {sum(videos.values())} with video ({', '.join(f'{n} {t}' for t, n in videos.items()) or 'none'}), "
        f"{len(good) - len(online)} out of service")
    if good:
        lats, lons = [c["lat"] for c in good], [c["lon"] for c in good]
        say(f"  spread: lat {min(lats):.3f} to {max(lats):.3f}, lon {min(lons):.3f} to {max(lons):.3f}")
        for cam in random.Random(1).sample(good, min(3, len(good))):
            say("  e.g.", json.dumps(cam)[:300])
    for problem in source_problems(source):
        say("  PROBLEM:", problem)
    for problem, n in bad.most_common():
        say(f"  PROBLEM: {n} cameras: {problem}")
    if duplicates:
        problems.append("duplicate ids")
        say(f"  PROBLEM: {len(duplicates)} ids used more than once, e.g. {list(duplicates)[:5]}")
    if not cams:
        problems.append("no cameras")
        say("  PROBLEM: no cameras")
    failed = 0
    for cam in random.Random(SEED).sample(online, min(media, len(online))):
        try:
            say(f"  media {cam['id']}: {try_media(module, cam, key)}")
        except Exception as e:
            failed += 1
            say(f"  media {cam['id']}: FAILED {e}")
    tried = min(media, len(online))
    if failed and failed <= DEAD_OK * tried:
        say(f"  ({failed} of {tried} cameras tried gave nothing: taken for dead cameras the source still lists)")
    ok = not problems and not bad and failed <= DEAD_OK * tried
    if save and good:
        OUT.mkdir(exist_ok=True)
        (OUT / f"{name}.json").write_text(json.dumps({
            "module": name, "source": source, "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seconds": round(seconds, 1), "cameras": good}, separators=(",", ":")))
    say(f"  {'OK' if ok else 'PROBLEMS'}" + (f" (saved {len(good)} to sources/out/{name}.json)" if save and good else ""))
    if quiet:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {len(good)}/{len(cams)} cameras, {len(online)} in service, "
              f"{seconds:.0f} s{f', {failed}/{min(media, len(online))} media failed' if failed else ''}")
    return ok


def withdrawn():
    """The sources withdrawn at their agencies' request (data/withdrawn.json; see app/withdrawn.py)."""
    try:
        return set(json.loads((Path(__file__).resolve().parent.parent / "data" / "withdrawn.json").read_text())["withdrawn"])
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("module", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--unrestricted", action="store_true", help="with --all: leave out the restricted sources")
    parser.add_argument("--crawler", action="store_true",
                        help="with --all, run unattended: also leave out restricted sources and those NOT_FOR_CRAWLERS")
    parser.add_argument("--media", type=int, default=5, help="cameras whose pictures and video to try")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--seed", type=int, help="pick the same cameras to try each run (default: different ones)")
    args = parser.parse_args()
    if args.all == bool(args.module):
        parser.error("give a module, or --all")
    if (args.unrestricted or args.crawler) and not args.all:
        parser.error("--unrestricted and --crawler go with --all")
    global SEED
    SEED = args.seed
    names = sources.modules() if args.all else [args.module]
    if args.unrestricted or args.crawler:  # (and never one withdrawn at its agency's request)
        names = [n for n in names if n not in withdrawn()
                 and not getattr(importlib.import_module(f"sources.{n}"), "SOURCE", {}).get("restricted")]
    if args.crawler:  # (and a source that needs a key is checked only when one is given)
        codes = {n: importlib.import_module(f"sources.{n}") for n in names}
        names = [n for n, code in codes.items() if not getattr(code, "NOT_FOR_CRAWLERS", False)
                 and (not code.SOURCE.get("key") or os.environ.get(f"CAMWALL_KEY_{n.upper()}"))]
    results = [check(n, args.media, not args.no_save, quiet=args.all) for n in names]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
