#!/usr/bin/env python3
"""Add the module aliases a library installs at import time to names_hist.json (sentence-transformers).

Usage: python3 -I alias_hist.py <clone> names_hist.json <source root> > names_hist_aliased.json
Three forms are read from the source of each release (nothing is run):
  1. DEPRECATED_MODULE_PATHS = {"pkg.old": "pkg.new", ...} with a meta path finder that serves "pkg.new" for "pkg.old"
     (5.4.0 on); the finder must be installed by the top-level __init__.py (setup_deprecated_module_imports()).
  2. a list of old paths and `for m in that_list: sys.modules[m] = sys.modules["pkg.new"]` (4.0.0 on)
  3. `sys.modules["pkg.old"] = sys.modules["pkg.new"]` (5.0.0 on)
An alias makes "old" a module with the names of "new", and its last part a name of its parent.
The script stops if a file assigns to sys.modules in a form it does not know.
"""
import ast, json, os, sys, warnings
warnings.simplefilter("ignore", SyntaxWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch
REPO, H, ROOT = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3].strip("/")
PKG = ROOT.rsplit("/", 1)[-1]
want, text = fetch.load(REPO, H["tags"], root=ROOT)
strip = lambda d: d[len(PKG) + 1:] if d.startswith(PKG + ".") else ("" if d == PKG else None)


def aliases_in(src, where):
    tree = ast.parse(src)
    lists, out = {}, {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            v = n.value
            if isinstance(v, ast.List) and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in v.elts):
                lists[n.targets[0].id] = [e.value for e in v.elts]
            if n.targets[0].id == "DEPRECATED_MODULE_PATHS":
                assert isinstance(v, ast.Dict), where
                for k, x in zip(v.keys, v.values):
                    out[k.value] = x.value
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Subscript) \
                and isinstance(n.targets[0].value, ast.Name) and n.targets[0].value.id == "sys" or \
                isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Subscript) \
                and isinstance(n.targets[0].value, ast.Attribute) and n.targets[0].value.attr == "modules":
            t, v = n.targets[0], n.value
            ok_v = isinstance(v, ast.Subscript) and isinstance(v.value, ast.Attribute) and v.value.attr == "modules" and isinstance(v.slice, ast.Constant)
            if isinstance(t.slice, ast.Constant) and ok_v:
                out[t.slice.value] = v.slice.value                                   # form 3
            elif isinstance(t.slice, ast.Name) and ok_v:
                loop = [f for f in ast.walk(tree) if isinstance(f, ast.For) and n in f.body]
                assert loop and isinstance(loop[0].iter, ast.Name) and loop[0].iter.id in lists, where
                for old in lists[loop[0].iter.id]:
                    out[old] = v.slice.value                                         # form 2
            else:
                raise SystemExit("%s: unknown assignment to sys.modules: %s" % (where, ast.get_source_segment(src, n)))
    return out


H["aliases"] = {}
n_alias = 0
for t in H["tags"]:
    al = {}
    for p, sha in want[t].items():
        src = text[sha]
        if "sys.modules[" in src and "] =" in src or "DEPRECATED_MODULE_PATHS" in src:
            al.update(aliases_in(src, t + " " + p))
    if any("DEPRECATED_MODULE_PATHS" in text[sha] for sha in want[t].values()):
        assert "setup_deprecated_module_imports()" in text[want[t]["__init__.py"]], t
    mods = H["mods"][t]
    used = {}
    for old, new in sorted(al.items()):
        o, nw = strip(old), strip(new)
        assert o is not None and nw is not None, (t, old, new)
        if nw not in mods:
            continue                                  # an alias to a module this release does not have: nothing to serve
        mods[o] = sorted(set(mods.get(o, [])) | set(mods[nw]))
        parent, leaf = (o.rsplit(".", 1) if "." in o else ("", o))
        if parent in mods:
            mods[parent] = sorted(set(mods[parent]) | {leaf})
        used[o] = nw
    H["aliases"][t] = used
    n_alias += len(used)
    if used:
        print(t, "aliases:", len(used), file=sys.stderr)
print("module aliases applied (sum over releases):", n_alias, file=sys.stderr)
json.dump(H, sys.stdout, separators=(",", ":"))
