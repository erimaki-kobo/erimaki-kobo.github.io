#!/usr/bin/env python3
"""The early repository (early_repo.py) tags only the first release of each minor; add every other PyPI release below
the first git tag to "finals", so the page's "last release that has it" is the real last patch release.
usage: python3 -I add_finals.py merged.json dates.json 3.41.0 > merged_finals.json"""
import json, re, sys
h, d, below = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
key = lambda v: tuple(map(int, v.split(".")))
early = [v for v in d["dates"] if re.fullmatch(r"\d+\.\d+\.\d+", v) and (3, 0, 0) <= key(v) < key(below) and v not in d["yanked"]]
h["finals"] = sorted(set(h["finals"]) | {"gradio@" + v for v in early}, key=lambda t: key(t.split("@")[1]))
json.dump(h, sys.stdout)
