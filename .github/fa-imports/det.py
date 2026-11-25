#!/usr/bin/env python3
"""Does flash_attn_varlen_func take `deterministic=` at a few tags? usage: python3 -I det.py fa.git > det.json"""
import ast, json, subprocess, sys
out = {}
for t in ("2.0.1", "2.2.0", "2.3.0", "2.4.1", "2.8.3"):
    src = subprocess.run(["git", "-C", sys.argv[1], "show", "v%s:flash_attn/flash_attn_interface.py" % t], capture_output=True, check=True).stdout
    f = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "flash_attn_varlen_func"][0]
    out[t] = "deterministic" in [a.arg for a in f.args.args + f.args.kwonlyargs]
json.dump(out, sys.stdout)
