"""Builds data/places.json, for finding where someone is from their ZIP code, town or county, from the Census
Bureau's gazetteer files (public domain): https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html

    python3 tools/build_places.py GAZETTEER_DIR      (holding the 2024 zcta, place and counties .txt files)

places.json: {"zips": {"50010": [lat, lon]}, "places": [[name, state, lat, lon, kind]], "states": {"IA": [south, west,
north, east]}}, kind being "c" for a city, town or village, "p" for an unincorporated place and "k" for a county.
"""

import csv
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "places.json"


def rows(path):
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            yield {k.strip(): v.strip() for k, v in row.items() if k}


def place_name(name):
    """"Abbeville city" -> "Abbeville"; "Nashville-Davidson metropolitan government (balance)" -> "Nashville-Davidson"."""
    name = re.sub(r"\s*\(.*\)$", "", name)
    words = name.split()
    while len(words) > 1 and (words[-1].islower() or words[-1] == "CDP"):
        words.pop()
    return " ".join(words)


def main(folder):
    folder = Path(folder)
    zips = {r["GEOID"]: [round(float(r["INTPTLAT"]), 4), round(float(r["INTPTLONG"]), 4)]
            for r in rows(next(folder.glob("*zcta*.txt")))}
    places, bounds = [], {}
    for r in rows(next(folder.glob("*place*.txt"))):
        lat, lon = round(float(r["INTPTLAT"]), 4), round(float(r["INTPTLONG"]), 4)
        places.append([place_name(r["NAME"]), r["USPS"], lat, lon, "c" if r["FUNCSTAT"] == "A" else "p"])
    for r in rows(next(folder.glob("*counties*.txt"))):
        lat, lon = round(float(r["INTPTLAT"]), 4), round(float(r["INTPTLONG"]), 4)
        places.append([r["NAME"], r["USPS"], lat, lon, "k"])
    for name, state, lat, lon, kind in places:
        lon = lon - 360 if lon > 0 else lon  # the western Aleutians, across the date line
        b = bounds.setdefault(state, [lat, lon, lat, lon])
        bounds[state] = [min(b[0], lat), min(b[1], lon), max(b[2], lat), max(b[3], lon)]
    places.sort(key=lambda p: (p[0].lower(), p[1]))
    OUT.write_text(json.dumps({"zips": zips, "places": places, "states": bounds}, separators=(",", ":")))
    print(f"{OUT}: {len(zips)} ZIP codes, {len(places)} places, {len(bounds)} states, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1])
