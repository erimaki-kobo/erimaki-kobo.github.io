#!/usr/bin/env python3
"""openai 1.2.0 on: `from .lib._old_api import *` binds the 0.x names (ChatCompletion, Completion, ...) to proxies that raise
APIRemovedInV1 when used. The names are created in a loop (`__locals[symbol] = ...`), which names_hist.py cannot see.
Read the SYMBOLS list of src/openai/lib/_old_api.py at each release; add the names to `openai` and to lib._old_api, and
list them in "proxies" {tag: {module: [names]}} so the lookup can say that importing works but using them raises.
Usage: python3 -I proxy_hist.py <clone> names_hist.json > out.json"""
import ast, json, subprocess, sys
REPO, H = sys.argv[1], json.load(open(sys.argv[2]))
H["proxies"] = {}
n = 0
for t in H["tags"]:
    r = subprocess.run(["git", "-C", REPO, "show", t + ":src/openai/lib/_old_api.py"], capture_output=True, text=True)
    if r.returncode:
        continue
    tree = ast.parse(r.stdout)
    sym = [n_ for n_ in tree.body if isinstance(n_, ast.Assign) and getattr(n_.targets[0], "id", "") == "SYMBOLS"]
    assert len(sym) == 1, t
    names = [e.value for e in sym[0].value.elts]
    init = subprocess.run(["git", "-C", REPO, "show", t + ":src/openai/__init__.py"], capture_output=True, text=True).stdout
    assert "from .lib._old_api import *" in init, t
    for m in ("", "lib._old_api"):
        H["mods"][t][m] = sorted(set(H["mods"][t][m]) | set(names))
    H["proxies"][t] = {"": names, "lib._old_api": names}
    n += 1
print("releases with the old-API proxies:", n, file=sys.stderr)
json.dump(H, sys.stdout, separators=(",", ":"))
