#!/usr/bin/env python3
"""Dates of llama-index (below 0.10.0) and llama-index-core (from 0.10.0) in one file for build_data.py.
usage: python3 -I merge_dates.py dates_li.json dates_core.json > dates_merged.json"""
import json, sys
a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
key = lambda v: tuple(int(x) for x in v.split(".")[:3] if x.isdigit())
d = {v: t for v, t in a["dates"].items() if key(v) < (0, 10, 0)}
d.update({v: t for v, t in b["dates"].items() if key(v) >= (0, 10, 0)})
json.dump({"dates": d, "yanked": [v for v in a["yanked"] if key(v) < (0, 10, 0)] + [v for v in b["yanked"] if key(v) >= (0, 10, 0)]}, sys.stdout)
