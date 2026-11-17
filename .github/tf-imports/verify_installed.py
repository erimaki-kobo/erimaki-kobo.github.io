#!/usr/bin/env python3
"""Independent check of names_hist.json: install the real package and ask it.

Usage: python3 verify_installed.py names_hist.json <dir where `pip install --target` put transformers==X> X
Compares the names the installed package's lazy module serves (transformers._class_to_module) and what
`transformers.utils` / `transformers.file_utils` really bind with what names_hist.py read from the source by ast.
Run without torch installed: the package then lists the same names through its dummy objects.
"""
import importlib, json, sys
hist = json.load(open(sys.argv[1]))
sys.path.insert(0, sys.argv[2])
tag = "v" + sys.argv[3]
import transformers
assert transformers.__version__ == sys.argv[3], transformers.__version__
real = set(transformers._class_to_module)
mine = set(hist["top"][tag]["names"])
out = {"version": transformers.__version__, "top_real": len(real), "top_read": len(mine),
       "only_in_package": sorted(real - mine)[:12], "only_in_reading": sorted(mine - real)[:12],
       "n_only_in_package": len(real - mine), "n_only_in_reading": len(mine - real)}
for key in ("utils", "file_utils"):
    if tag not in hist[key]:
        continue
    m = importlib.import_module("transformers." + key)
    real_u = {n for n in vars(m) if not (n.startswith("__") and n.endswith("__"))}
    mine_u = set(hist[key][tag])
    # submodules become attributes of a package once imported; they are not names the file binds
    sub = {n for n in real_u - mine_u if type(vars(m)[n]).__name__ == "module"}
    out[key] = {"real": len(real_u - sub), "read": len(mine_u), "only_in_package": sorted(real_u - sub - mine_u)[:12],
                "only_in_reading": sorted(mine_u - real_u)[:12]}
print(json.dumps(out))
