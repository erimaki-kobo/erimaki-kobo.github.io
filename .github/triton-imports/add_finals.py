#!/usr/bin/env python3
"""wheel_repo.py tags only the releases it read; add every other PyPI release to "finals", so "last release that has it"
is the real last patch release. usage: python3 -I add_finals.py hist.json dates.json > hist_finals.json"""
import json, re, sys
h, d = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
key = lambda v: tuple(map(int, v.lstrip("v").split(".")))
lo = key(h["tags"][0])
allv = [v for v in d["dates"] if re.fullmatch(r"\d+\.\d+\.\d+", v) and key(v) >= lo and v not in d["yanked"]]
h["finals"] = sorted(set(h["finals"]) | {"v" + v for v in allv}, key=key)
json.dump(h, sys.stdout)
