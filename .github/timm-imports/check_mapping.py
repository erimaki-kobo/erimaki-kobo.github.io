#!/usr/bin/env python3
"""Second reading of timm.models.layers (the 0.9 mapping) with regular expressions, in every release where it maps to timm.layers.
Usage: python3 -I check_mapping.py timm.git hist.json      Prints the releases checked; fails on any difference other than
torch, nn and F (a star import without __all__ passes along the modules a file imports)."""
import json, re, subprocess, sys
REPO, H = sys.argv[1], json.load(open(sys.argv[2]))
show = lambda t, p: subprocess.run(["git", "-C", REPO, "show", t + ":" + p], capture_output=True, text=True).stdout
n = 0
for t in H["tags"]:
    src = show(t, "timm/models/layers/__init__.py")
    if "timm.layers" not in src:
        continue
    flat = re.sub(r"\(([^)]*)\)", lambda m: m.group(1).replace("\n", " "), re.sub(r"\\\n", " ", src))
    names = set()
    for mod, lst in re.findall(r"^from (timm\.layers[\w.]*) import (.+)$", flat, re.M):
        if lst.strip() == "*":
            s2 = show(t, mod.replace(".", "/") + ".py")
            a = re.search(r"__all__\s*=\s*\[([^\]]*)\]", s2)
            names |= set(re.findall(r"['\"](\w+)['\"]", a.group(1))) if a else {x for g in re.findall(r"^(?:class|def)\s+(\w+)|^(\w+)\s*=", s2, re.M) for x in g if x and not x.startswith("_")}
        else:
            names |= {x.strip().split(" as ")[-1] for x in lst.split(",") if x.strip()}
    mine = set(H["mods"][t]["models.layers"])
    extra = {x for x in mine - names if not x.startswith("_")} - {"torch", "nn", "F", "warnings"}
    assert not (names - mine) and not extra, (t, sorted(names - mine)[:5], sorted(extra)[:5])
    n += 1
print("timm.models.layers mapping: %d releases, same names" % n)
