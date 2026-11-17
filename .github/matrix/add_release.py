#!/usr/bin/env python3
"""Append one release to matrix.json from facts gathered by hand (see README.md).

Usage: python3 -I add_release.py matrix.json facts.json
facts.json holds one release record plus the read date; this script refuses anything
that is not strictly newer than the last release, and checks the record's shape against
the previous row so a missing field cannot slip in.
"""
import json, re, sys
from pathlib import Path

mp, fp = Path(sys.argv[1]), Path(sys.argv[2])
M = json.loads(mp.read_text())
F = json.loads(fp.read_text())
rel, prev = F["release"], M["releases"][-1]


def vkey(v):
    return [int(x) for x in re.findall(r"\d+", v)]


assert vkey(rel["v"]) > vkey(prev["v"]), (rel["v"], prev["v"])
assert list(rel.keys()) == list(prev.keys()), sorted(set(rel) ^ set(prev))
for k in rel:
    assert type(rel[k]) is type(prev[k]), k
assert rel["torch"] in M["torch"], "add the torch release to matrix.json['torch'] first"
assert rel["torch_pypi_cuda"] == M["torch"][rel["torch"]]["pypi_cuda"]
assert rel["soname"] == "libcudart.so.%d" % rel["cuda_major"] and str(rel["cuda_major"]) in M["driver_min"]
assert re.fullmatch(r"\d{4}-\d\d-\d\d", rel["date"]) and re.fullmatch(r"\d{4}-\d\d-\d\d", F["as_of"])

M["releases"].append(rel)
M["as_of"] = F["as_of"]
M["scope"] = re.sub(r"to v[0-9.]+$", "to v" + rel["v"], M["scope"])
assert M["scope"].endswith("to v" + rel["v"])
M.setdefault("pypi_x86_64_wheel_bytes", {}).update(F["pypi_x86_64_wheel_bytes"])
M["sources"].update(F.get("sources", {}))
mp.write_text(json.dumps(M, indent=1) + "\n")
print("added", rel["v"], "->", len(M["releases"]), "releases; as_of", M["as_of"])
