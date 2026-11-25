"""usage: python3 -I np_attrs.py <bare clone of numpy/numpy> pypi.json > np_attrs.json
For the first release of every minor from 1.16.0 on, plus the latest: the tables numpy's module __getattr__ answers from.
  deprecated  {name: message}  still returns the object, with a DeprecationWarning (__deprecated_attrs__)
  expired_fn  {name: message}  returns a function that raises (__expired_functions__, NEP 32 financial functions)
  former      {name: message}  AttributeError with this message (__former_attrs__)
  expired     {name: message}  AttributeError "`np.X` was removed in the NumPy 2.0 release. <message>" (__expired_attributes__)
  special     {name: message}  `elif attr == "X": raise AttributeError("...")` in __getattr__
  future      [names]          FutureWarning, then AttributeError (__future_scalars__)
The table statements are evaluated with every outside name replaced by a string "<name>" (callable) and no builtins, so no numpy code
runs; the message templates only need str.format."""
import ast, json, re, subprocess, sys
REPO, P = sys.argv[1], json.load(open(sys.argv[2]))
key = lambda v: tuple(int(x) for x in v.split("."))
show = lambda t, p: subprocess.run(["git", "--git-dir", REPO, "show", "%s:%s" % (t, p)], capture_output=True, text=True)
vs = sorted((v for v in P["releases"] if re.fullmatch(r"\d+\.\d+\.\d+", v) and key(v) >= (1, 16, 0) and P["releases"][v]
             and not all(f.get("yanked") for f in P["releases"][v])), key=key)
first = {}
for v in vs:
    first.setdefault(key(v)[:2], v)
sel = sorted(set(first.values()) | {vs[-1]}, key=key)
TABLE = {"__deprecated_attrs__": "deprecated", "__expired_functions__": "expired_fn", "__former_attrs__": "former",
         "__future_scalars__": "future", "__expired_attributes__": "expired"}
HELPERS = re.compile(r"^_(msg|specific_msg|int_extended_msg|type_info|financial_names)$")


def body(tree):   # the statements inside `if __NUMPY_SETUP__: ... else:` (or the module itself)
    for n in tree.body:
        if isinstance(n, ast.If) and "NUMPY_SETUP" in ast.dump(n.test) and n.orelse:
            return n.orelse
    return tree.body


def target(n):
    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
        return n.targets[0].id
    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Subscript) and isinstance(n.targets[0].value, ast.Name):
        return n.targets[0].value.id   # __deprecated_attrs__["long"] = (...)
    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == "update" \
            and isinstance(n.value.func.value, ast.Name):
        return n.value.func.value.id
    return None


class Ph(str):   # a stand-in for a numpy object: a string that can also be called
    def __call__(self, *a, **k):
        return Ph(self + "()")

    def __getattr__(self, n):
        return Ph("%s.%s" % (self, n))


def run(stmts, extra=None):
    g = {"__builtins__": {}, "getattr": lambda o, n, *d: Ph("<%s.%s>" % (o, n))}
    for s in stmts:
        for x in ast.walk(s):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) and x.id not in g:
                g[x.id] = Ph("<%s>" % x.id)
    g.update(extra or {})
    for s in stmts:
        exec(compile(ast.Module([s], []), "numpy/__init__.py", "exec"), g)
    return g


out = {}
for v in sel:
    t = "v" + v
    src = show(t, "numpy/__init__.py")
    assert src.returncode == 0, t
    tree = ast.parse(src.stdout)
    stmts = [s for s in body(tree) if target(s) and (target(s) in TABLE or HELPERS.match(target(s)))]
    extra = {}
    ex = show(t, "numpy/_expired_attrs_2_0.py")
    if ex.returncode == 0:
        extra["__expired_attributes__"] = ast.literal_eval(ast.parse(ex.stdout).body[-1].value)
        assert "__expired_attributes__" in src.stdout, t
    g = run(stmts, extra)
    rec = {"date": min(f["upload_time"] for f in P["releases"][v])[:10]}
    for name, k in TABLE.items():
        val = g.get(name, extra.get(name))
        if val is None:
            rec[k] = [] if k == "future" else {}
        elif k == "future":
            rec[k] = sorted(val)
        elif k == "deprecated":
            rec[k] = {n: m[1] if isinstance(m, tuple) else m for n, m in val.items()}
        else:
            rec[k] = dict(val)
    special = {}
    for f in ast.walk(tree):
        if isinstance(f, ast.FunctionDef) and f.name == "__getattr__":
            for x in ast.walk(f):
                if isinstance(x, ast.If) and isinstance(x.test, ast.Compare) and isinstance(x.test.comparators[0], ast.Constant) \
                        and isinstance(x.test.comparators[0].value, str):
                    for r in (y for st in x.body for y in ast.walk(st)):   # this branch only, not the elif chain in orelse
                        if isinstance(r, ast.Raise) and isinstance(r.exc, ast.Call) and getattr(r.exc.func, "id", "") == "AttributeError" \
                                and r.exc.args and isinstance(r.exc.args[0], ast.Constant):
                            special.setdefault(x.test.comparators[0].value, r.exc.args[0].value)
    rec["special"] = special
    rec["has_core"] = show(t, "numpy/_core/__init__.py").returncode == 0
    out[v] = rec
    print(v, {k: len(rec[k]) for k in ("deprecated", "expired_fn", "former", "expired", "special", "future")}, rec["has_core"], file=sys.stderr)
json.dump(out, sys.stdout, indent=0)
