#!/usr/bin/env python3
"""Join names_hist.json files of one library read from different roots (langchain 0.x in libs/langchain, 1.x in
libs/langchain_v1). Usage: python3 -I merge_hist.py a.json b.json ... > merged.json   (in release order)"""
import json, sys
out = None
for f in sys.argv[1:]:
    h = json.load(open(f))
    if out is None:
        out = h
        continue
    assert not set(h["tags"]) & set(out["tags"]), f
    out["tags"] += h["tags"]
    out["finals"] += h["finals"]
    for k in ("mods", "lazy", "pkgs", "placeholders"):
        out[k].update(h[k])
    out["stale"] += h["stale"]
    out["own_latest"] = h["own_latest"]
json.dump(out, sys.stdout, separators=(",", ":"))
