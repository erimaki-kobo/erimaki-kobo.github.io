#!/usr/bin/env python3
"""Check the page's key Triton facts against the triton git tags, a source independent of the wheels the data was read from.

usage: python3 -I anchors.py triton.git out/triton.json > anchors.json
The git tree keeps the package in python/triton/ (in later releases the build also copies parts of third_party/ into it).
Each fact names a file and a word that must be found in
it at one tag and missing at the other; the data must say the same for those releases.
"""
import json, re, subprocess, sys

G, D = sys.argv[1], json.load(open(sys.argv[2]))
FACTS = [  # (module, name, git path, regex, release that has it, release without it)
    ("ops", "matmul", "python/triton/ops/matmul.py", r"def |class ", "3.1.0", "3.2.0"),
    ("language", "libdevice", "python/triton/language/libdevice.py", r"def ", "2.0.0", "2.1.0"),
    ("language.extra.cuda", "libdevice", "python/triton/language/extra/cuda/libdevice.py", r"def ", "3.0.0", "2.3.0"),
    ("compiler.compiler", "triton_key", "python/triton/compiler/compiler.py", r"^def triton_key\b", "3.4.0", "3.5.0"),
    ("runtime.autotuner", "PTXASError", "python/triton/runtime/autotuner.py", r"\bPTXASError\b", "3.3.0", "3.2.0"),
    ("language", "make_tensor_descriptor", "python/triton/language/__init__.py", r"\bmake_tensor_descriptor\b", "3.4.0", "3.3.0"),
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
