#!/usr/bin/env python3
"""Add the names a module serves through a module-level __getattr__ (langchain 0.1 to 0.3, langchain_classic).

Usage: python3 -I getattr_hist.py <clone> names_hist.json <root at each tag: "default" or "1.=libs/x"> > out.json
langchain modules forward unknown names to langchain_community (or to a lookup table), with a deprecation warning, and
only when langchain-community is installed. Read from the source of each module that defines __getattr__:
  - the strings of __all__,
  - the keys of module-level dicts whose values all name a langchain_* module (DEPRECATED_LOOKUP, MODULE_LOOKUP, ...),
  - the target: those values, or the module named by `from langchain_community import x` / `from langchain_community.x
    import ...` / `importlib.import_module("langchain_community....")` inside __getattr__.
Names whose target is another package are listed in "deferred" {tag: {module: {name: target module}}}; the lookup tells the reader that
they need the target package. The script stops if a __getattr__ forwards somewhere it cannot name.
"""
import ast, json, os, sys, warnings
warnings.simplefilter("ignore", SyntaxWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch
REPO, H, ROOTS = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
default, over = ROOTS.split("|")[0], [x.split("=", 1) for x in ROOTS.split("|")[1:]]
PKG = default.rstrip("/").rsplit("/", 1)[-1]


def root_of(t):
    v = t.split("==")[-1].lstrip("v")
    for pre, r in over:
        if v.startswith(pre):
            return r
    return default


H["deferred"] = {}
total = 0
cache = {}
by_root = {}
for t in H["tags"]:
    by_root.setdefault(root_of(t), []).append(t)
for root, tags in by_root.items():
    want, text = fetch.load(REPO, tags, root=root)
    for t in tags:
        dfr = {}
        for p, sha in want[t].items():
            src = text[sha]
            if "def __getattr__" not in src:
                continue
            m = p[:-3].replace("/", ".")
            m = m[:-len(".__init__")] if m.endswith(".__init__") else "" if m == "__init__" else m
            if sha not in cache:
                tree = ast.parse(src)
                ga = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "__getattr__"]
                if not ga:
                    cache[sha] = None
                    continue
                allv, lookups, targets = [], {}, set()
                for n in tree.body:
                    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                        name, v = n.targets[0].id, n.value
                        if name == "__all__" and isinstance(v, (ast.List, ast.Tuple)):
                            allv = [e.value for e in v.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                        elif isinstance(v, ast.Dict) and v.keys and all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in v.keys) \
                                and all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in v.values):
                            used = {x.id for x in ast.walk(ga[0]) if isinstance(x, ast.Name)} | {
                                x.id for c in tree.body if isinstance(c, ast.Assign) and isinstance(c.value, ast.Call)
                                for x in ast.walk(c.value) if isinstance(x, ast.Name)}
                            if name in used or all(x.value.startswith("langchain") for x in v.values):
                                # values: "langchain_community.x" (another package) or "human" / "__module__" (_dynamic_imports,
                                # a submodule of this package, resolved below)
                                lookups.update({k.value: x.value for k, x in zip(v.keys, v.values)})
                # create_importer(__package__, module_lookup={...}, deprecated_lookups={...}, fallback_module="...")
                for n in tree.body:
                    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and getattr(n.value.func, "id", "") == "create_importer":
                        for kw in n.value.keywords:
                            if kw.arg in ("module_lookup", "deprecated_lookups") and isinstance(kw.value, ast.Dict):
                                lookups.update({k.value: x.value for k, x in zip(kw.value.keys, kw.value.values)})
                            elif kw.arg in ("module_lookup", "deprecated_lookups") and isinstance(kw.value, ast.Name):
                                pass            # a module-level dict, read above
                            elif kw.arg == "fallback_module" and isinstance(kw.value, ast.Constant):
                                targets.add(kw.value.value)
                for n in ast.walk(ga[0]):
                    if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("langchain_community"):
                        if n.module == "langchain_community":
                            targets |= {"langchain_community." + a.name for a in n.names}
                        else:
                            targets.add(n.module)
                    if isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) == "import_module" and n.args \
                            and isinstance(n.args[0], ast.Constant) and str(n.args[0].value).startswith("langchain"):
                        targets.add(n.args[0].value)
                cache[sha] = (allv, lookups, sorted(targets))
            c = cache[sha]
            if c is None:
                continue
            allv, lookups, targets = c
            served = {}
            for n in allv:
                if n not in lookups:
                    served[n] = targets[0] if len(targets) == 1 else (targets and "langchain_community") or "?"
            for n, v in lookups.items():
                if v == "__module__":
                    v = PKG + "." + (m + "." if m else "") + n           # import_attr: the attribute is the submodule itself
                elif not v.startswith("langchain"):
                    v = PKG + "." + (m + "." if m else "") + v           # relative module of this package
                served[n] = v
            have = set(H["mods"][t].get(m, []))
            new = {n: v for n, v in served.items() if n not in have}
            if new:
                assert all(v != "?" for v in new.values()), (t, p, [n for n, v in new.items() if v == "?"][:5])
                H["mods"][t][m] = sorted(have | set(new))
                ext = {n: v for n, v in new.items() if v.split(".")[0] != PKG}     # needs another package installed
                if ext:
                    dfr[m] = ext
                total += len(new)
        H["deferred"][t] = dfr
        es = {}
        for p, sha in want[t].items():
            if "import *" not in text[sha]:
                continue
            m = p[:-3].replace("/", ".")
            m = m[:-len(".__init__")] if m.endswith(".__init__") else "" if m == "__init__" else m
            for n in ast.walk(ast.parse(text[sha])):      # also inside try/except (a star import cannot sit in a function)
                if isinstance(n, ast.ImportFrom) and n.level == 0 and any(a.name == "*" for a in n.names) and n.module.split(".")[0] != PKG:
                    es.setdefault(m, []).append(n.module)
        H.setdefault("ext_star", {})[t] = es
    print(root, len(tags), "releases", file=sys.stderr)
print("names served through __getattr__ (sum over releases):", total, file=sys.stderr)
json.dump(H, sys.stdout, separators=(",", ":"))
