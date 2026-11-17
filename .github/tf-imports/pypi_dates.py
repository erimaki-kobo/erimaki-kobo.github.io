#!/usr/bin/env python3
"""Release dates of transformers from PyPI (earliest upload of each release, UTC) and which releases are yanked.

Usage: curl -sS https://pypi.org/pypi/transformers/json -o pypi.json && python3 -I pypi_dates.py pypi.json > tf_pypi.json
"""
import json, re, sys
d = json.load(open(sys.argv[1]))
dates, yanked = {}, []
for v, files in d["releases"].items():
    if not files or not re.fullmatch(r"\d+\.\d+\.\d+", v):
        continue
    dates[v] = min(f["upload_time_iso_8601"] for f in files)[:10]
    if all(f.get("yanked") for f in files):
        yanked.append(v)
key = lambda v: tuple(int(x) for x in v.split("."))
json.dump({"dates": dict(sorted(dates.items(), key=lambda kv: key(kv[0]))), "yanked": sorted(yanked, key=key)}, sys.stdout)
