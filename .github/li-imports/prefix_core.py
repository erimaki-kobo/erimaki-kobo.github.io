#!/usr/bin/env python3
"""llama-index 0.10 and later ship the old top level as llama_index.core (package llama-index-core); llama_index itself
is a namespace package that binds no names. names_hist.py read llama-index-core/llama_index/core, so its modules are
named relative to core; prefix them with "core" and make "" the empty namespace (only the submodule `core`).
usage: python3 -I prefix_core.py h1.json > h1p.json"""
import json, sys
h = json.load(open(sys.argv[1]))
P = lambda m: "core" + ("." + m if m else "")
for k in ("mods",):
    for t in h["tags"]:
        h[k][t] = {P(m): v for m, v in h[k][t].items()}
        h[k][t][""] = ["core"]
for k in ("lazy", "pkgs", "placeholders"):
    for t in h["tags"]:
        v = h[k][t]
        if isinstance(v, list):
            h[k][t] = [P(m) if isinstance(m, str) else m for m in v] + ([""] if k == "pkgs" else [])
        elif isinstance(v, dict):
            h[k][t] = {P(m): x for m, x in v.items()}
if isinstance(h.get("own_latest"), dict):
    h["own_latest"] = {P(m): v for m, v in h["own_latest"].items()}
json.dump(h, sys.stdout)
