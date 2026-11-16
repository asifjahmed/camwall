"""Writes research/COVERAGE.md from sources/out/ (what sources.check last saved), counting a camera several sources
list once, as the app does (app/catalogue.py).

    python3 tools/coverage.py
    python3 tools/coverage.py --leave-out fl_x --to <file>   # without some sources, written elsewhere
"""

import argparse
import collections
import json
import sys
from datetime import date
from pathlib import Path

CAMWALL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAMWALL))

import sources  # noqa: E402
from app import catalogue as cm  # noqa: E402

NAMES = {"AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut",
"DE":"Delaware","DC":"District of Columbia","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois",
"IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts",
"MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada",
"NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota",
"OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","PR":"Puerto Rico","RI":"Rhode Island","SC":"South Carolina",
"SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
"WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"}


def main(leave_out=(), to=CAMWALL / "research" / "COVERAGE.md"):
    c = cm.Catalogue()
    known = set(sources.modules()) - set(leave_out)
    for f in sorted((CAMWALL / "sources" / "out").glob("*.json")):
        d = json.loads(f.read_text())
        if d["module"] in known:  # (not a source since removed, or one left out)
            c.lists[d["module"]] = {**d, "origin": "shipped"}
    c._index()
    mods = c.modules()
    every = {"sources": {m: True for m in mods}}
    rows = collections.defaultdict(lambda: {"all": 0, "on": 0, "video": 0, "mods": set()})
    hidden_all, linked_all = c.view(every)
    hidden_def, _ = c.view({})
    total = on = video = 0
    for key, cam in c.cameras.items():
        st = cam.get("state"); st = st[0] if isinstance(st, list) else st
        r = rows[st]; r["mods"].add(cam["module"])
        if key in hidden_all: continue
        has_video = cm._has(cam, "video") or (key in linked_all and cm._has(c.cameras[linked_all[key]], "video"))
        r["all"] += 1; total += 1
        r["video"] += has_video; video += has_video
        if c.source_on(cam["module"], {}) and key not in hidden_def:
            r["on"] += 1; on += 1
    srcs = len(c.lists)
    out = [f"# Coverage", "",
           f"{total:,} distinct public cameras from {srcs} sources ({video:,} with live video); {on:,} from sources that are on by "
           f"default. Built from sources/out/ on {date.today().isoformat()}; the same camera listed by two sources is counted "
           f"once (see app/catalogue.py).", "",
           "| State | Cameras | On by default | With video | Sources |", "|---|---:|---:|---:|---|"]
    for code, name in sorted(NAMES.items(), key=lambda x: x[1]):
        r = rows.get(code)
        if not r or not r["all"]:
            out.append(f"| {name} | 0 | 0 | 0 | none |"); continue
        out.append(f"| {name} | {r['all']:,} | {r['on']:,} | {r['video']:,} | {', '.join(sorted(r['mods']))} |")
    odd = [s for s in rows if s not in NAMES]
    if odd:
        out.append("\nCameras with an unrecognised state: " + ", ".join(f"{s} ({rows[s]['all']})" for s in odd))
    Path(to).write_text("\n".join(out) + "\n")
    print(f"{total:,} distinct, {on:,} on by default, {video:,} with video, {srcs} sources; odd states: {odd}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--leave-out", nargs="*", default=(), metavar="MODULE")
    parser.add_argument("--to", type=Path, default=CAMWALL / "research" / "COVERAGE.md")
    args = parser.parse_args()
    main(args.leave_out, args.to)
