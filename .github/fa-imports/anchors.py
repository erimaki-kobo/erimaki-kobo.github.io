#!/usr/bin/env python3
"""Check the page's key flash-attn facts by plain-text search in the git tags (independent of the ast reading).

usage: python3 -I anchors.py fa.git out/flash_attn.json > anchors.json
Each fact names a file and a word that must be found in
it at one tag and missing at the other; the data must say the same for those releases.
"""
import json, re, subprocess, sys

G, D = sys.argv[1], json.load(open(sys.argv[2]))
FACTS = [  # (module, name, git path, regex, release that has it, release without it)
    ("flash_attn_interface", "flash_attn_unpadded_func", "flash_attn/flash_attn_interface.py", r"^def flash_attn_unpadded_func\b", "1.0.0", "2.0.1"),
    ("flash_attn_interface", "flash_attn_varlen_func", "flash_attn/flash_attn_interface.py", r"^def flash_attn_varlen_func\b", "2.0.1", "1.0.0"),
    ("", "flash_attn_func", "flash_attn/__init__.py", r"import flash_attn_func\b", "2.0.1", "1.0.0"),
    ("flash_attention", "FlashMHA", "flash_attn/flash_attention.py", r"^class FlashMHA\b", "1.0.0", "2.0.1"),
    ("flash_attn_interface", "flash_attn_with_kvcache", "flash_attn/flash_attn_interface.py", r"^def flash_attn_with_kvcache\b", "2.2.0", "2.1.0"),
]
R = [r[0] for r in D["releases"]]


def git_has(tag, path, rx):
    p = subprocess.run(["git", "-C", G, "show", "v%s:%s" % (tag, path)], capture_output=True)
    return p.returncode == 0 and re.search(rx, p.stdout.decode("utf-8", "replace"), re.M) is not None


def data_has(mod, name, v):
    i = R.index(v)
    if name in D["names"].get(mod, {}):
        rg = D["ranges"][D["names"][mod][name]]
    elif (mod + "." + name) in D["mods"]:
        rg = D["ranges"][D["mods"][mod + "." + name]]
    else:
        rg = []
    return any(a <= i and (b == 0 or i < b) for a, b in zip(rg[::2], rg[1::2]))


out = []
for mod, name, path, rx, has, hasnt in FACTS:
    for v, want in ((has, True), (hasnt, False)):
        g, d = git_has(v, path, rx), data_has(mod, name, v)
        out.append({"module": mod, "name": name, "release": v, "expected": want, "git": g, "data": d})
        assert g == want and d == want, out[-1]
print("anchors: %d facts, %d release checks, git and data agree" % (len(FACTS), len(out)), file=sys.stderr)
json.dump(out, sys.stdout, indent=0)
