#!/usr/bin/env python3
"""Add the names a vLLM module serves through a module-level __getattr__ to names_hist.json.

usage: python3 -I getattr_hist.py <bare clone> names_hist.json vllm > out.json
vLLM keeps moved names importable for a while with a deprecation warning: vllm/utils/__init__.py in 0.11 to 0.13 has
`_DEPRECATED_MAPPINGS = {"get_open_port": "network_utils", ...}` and a `def __getattr__(name)` that imports the name from
the new module; vllm/__init__.py has MODULE_ATTRS for its lazy top level. For every module that defines a module-level
__getattr__, the keys of each module-level dict whose keys and values are all strings and that the __getattr__ body uses
are added to that module's names. The script stops if a __getattr__ uses no such dict but does more than raise, so a new
pattern is not missed silently. Added names are listed in "via_getattr" {tag: {module: [names]}}.
"""
import ast, json, os, sys, warnings
warnings.simplefilter("ignore", SyntaxWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch

REPO, H, ROOT = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3].strip("/")
want, text = fetch.load(REPO, H["tags"], root=ROOT)


def modname(p):
    m = p[:-3].replace("/", ".")
    return m[:-9] if m.endswith(".__init__") else ("" if m == "__init__" else m)


def served(src, where):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    ga = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "__getattr__"]
    for n in tree.body:   # also `else:` branches of `if TYPE_CHECKING:`
        if isinstance(n, ast.If):
            ga += [m for m in n.orelse if isinstance(m, ast.FunctionDef) and m.name == "__getattr__"]
    if not ga:
        return set()
    dicts = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and isinstance(n.value, ast.Dict) and n.value.keys:
            ks, vs = n.value.keys, n.value.values
            if all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in ks) and \
               all(isinstance(v, ast.Constant) and isinstance(v.value, str) for v in vs):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(t, ast.Name):
                        dicts[t.id] = [k.value for k in ks]
    out = set()
    for f in ga:
        used = {x.id for x in ast.walk(f) if isinstance(x, ast.Name)}
        hit = [d for d in dicts if d in used]
        for d in hit:
            out |= set(dicts[d])
        if not hit:
            body = [s for s in f.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
            assert all(isinstance(s, ast.Raise) for s in body) or all(isinstance(s, (ast.Raise, ast.If, ast.Return, ast.Import, ast.ImportFrom))
                                                                      for s in body) and not any(isinstance(x, ast.Call) and getattr(x.func, "id", "") == "import_module" for x in ast.walk(f)), where
    return out


H["via_getattr"] = {}
cache = {}
n_add = 0
for t in H["tags"]:
    for p, sha in want[t].items():
        m = modname(p)
        if sha not in cache:
            cache[sha] = served(text[sha], (t, p))
        add = cache[sha] - set(H["mods"][t].get(m, []))
        if cache[sha]:
            H["mods"][t][m] = sorted(set(H["mods"][t].get(m, [])) | cache[sha])
        if add:
            H["via_getattr"].setdefault(t, {})[m] = sorted(add)
            n_add += len(add)
print("names added through __getattr__:", n_add, "in", sum(len(v) for v in H["via_getattr"].values()), "module-releases", file=sys.stderr)
json.dump(H, sys.stdout)
