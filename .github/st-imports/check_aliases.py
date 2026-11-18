#!/usr/bin/env python3
"""Second reading of the module aliases with a regular expression: every '"sentence_transformers.x": "sentence_transformers.y"'
line and every name in a deprecated_modules list must be among the aliases alias_hist.py applied (or point to a module
that release lacks). Usage: python3 -I check_aliases.py <clone> names_hist_aliased.json"""
import json, re, subprocess, sys
REPO, H = sys.argv[1], json.load(open(sys.argv[2]))
n = 0
for t in H["tags"]:
    files = subprocess.run(["git", "-C", REPO, "grep", "-l", "-e", "DEPRECATED_MODULE_PATHS", "-e", "sys.modules\\[", t, "--", "sentence_transformers"],
                           capture_output=True, text=True).stdout.split()
    found = {}
    for f in files:
        src = subprocess.run(["git", "-C", REPO, "show", f], capture_output=True, text=True).stdout
        found.update(dict(re.findall(r'^\s*"sentence_transformers\.([\w.]+)":\s*"sentence_transformers\.([\w.]+)",', src, re.M)))
        found.update(dict(re.findall(r'sys\.modules\["sentence_transformers\.([\w.]+)"\]\s*=\s*sys\.modules\["sentence_transformers\.([\w.]+)"\]', src)))
        m = re.search(r"deprecated_modules = \[(.*?)\]\s*for module in deprecated_modules:\s*sys\.modules\[module\] = sys\.modules\[\"sentence_transformers\.([\w.]+)\"\]", src, re.S)
        if m:
            for old in re.findall(r'"sentence_transformers\.([\w.]+)"', m.group(1)):
                found[old] = m.group(2)
    got = H["aliases"][t]
    for old, new in found.items():
        assert got.get(old) == new or new not in H["mods"][t], (t, old, new)
    assert set(got) <= set(found), (t, sorted(set(got) - set(found))[:5])
    n += len(found)
print("aliases found by regular expression and matched: %d (sum over releases)" % n)
