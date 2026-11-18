#!/usr/bin/env python3
"""Which names `from diffusers import X` and `from diffusers.<any module> import X` can resolve, at the first release of
every minor version of diffusers (and the newest release).

Usage: python3 -I names_hist.py <bare blobless clone> dates.json <source root, e.g. src/diffusers> > names_hist.json
Nothing from diffusers is imported or run; every .py file under src/diffusers at each tag is read with ast.

A module that replaces itself with `_LazyModule(...)` (most __init__.py files from 0.21.0 on) serves
  - the string lists of `_import_structure`, the keys of `_additional_imports`, and `extra_objects`,
  - read along the path with the optional backends installed. The other path (`except OptionalDependencyNotAvailable:`)
    hands out placeholders from a dummy module; for the top-level module they are kept apart in "placeholders".
Any other module serves every name it binds at module level: def, class, assignment, import (also of other packages:
`from diffusers.models.embeddings import nn` does import), and what `from .x import *` brings in. A star import of a dummy
module is the missing-backend path and is left out. Code under `if TYPE_CHECKING:` is not bound at run time and is skipped.
A lazy entry counts only if the submodule it names exists and binds the name; the others are listed in "stale".
For every package, its own submodules are importable names too (`from diffusers import models`).
The script stops on a statement about `_import_structure` it does not know, and if `_LazyModule.__getattr__` ever looks at
the spelling of a name.
"""
import ast, json, os, sys, warnings
warnings.simplefilter("ignore", SyntaxWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch

REPO, PYPI, ROOT = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3].strip("/")
PKG = ROOT.rsplit("/", 1)[-1]          # import name of the library: src/peft -> peft, timm -> timm
tags, finals = fetch.tags(REPO, PYPI, every="--every-release" in sys.argv)
want, text = fetch.load(REPO, tags, root=ROOT)
LAZY_VARS = {"_import_structure", "_dummy_objects", "_additional_imports"}


def strs(node, where):
    assert isinstance(node, (ast.List, ast.Tuple)), (where, ast.dump(node)[:200])
    out = []
    for e in node.elts:
        assert isinstance(e, ast.Constant) and isinstance(e.value, str), (where, ast.dump(e)[:200])
        out.append(e.value)
    return out


def is_tc(test):
    """`if TYPE_CHECKING:` or `if TYPE_CHECKING or DIFFUSERS_SLOW_IMPORT:`"""
    names = {n.id for n in ast.walk(test) if isinstance(n, ast.Name)}
    return "TYPE_CHECKING" in names


def mentions(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} & LAZY_VARS


def analyse(src, where):
    tree = ast.parse(src)
    res = {"names": set(), "stars": [], "dummies": [], "lazy": None}
    is_lazy = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_LazyModule" for n in ast.walk(tree)) \
        and not any(isinstance(n, ast.ClassDef) and n.name == "_LazyModule" for n in tree.body)
    aliases = {}        # local name -> (level, dotted module) for `from .utils import dummy_pt_objects`
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level >= 1:
            for a in n.names:
                if a.name.startswith("dummy_"):
                    aliases[a.asname or a.name] = (n.level, ((n.module + ".") if n.module else "") + a.name)

    def targets(t, out):
        if isinstance(t, ast.Name):
            out.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                targets(e, out)

    def plain(body):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                res["names"].add(n.name)
            elif isinstance(n, ast.ImportFrom):
                for a in n.names:
                    if a.name == "*":
                        if n.level >= 1 and (n.module or "").rsplit(".", 1)[-1].startswith("dummy_"):
                            res["dummies"].append((n.level, n.module))      # placeholders for a missing backend
                        elif n.level >= 1:
                            res["stars"].append((n.level, n.module or ""))
                        elif (n.module or "").split(".")[0] == PKG:
                            res["stars"].append((0, n.module[len(PKG) + 1:] if "." in n.module else ""))   # `from timm.layers.x import *`
                    else:
                        res["names"].add(a.asname or a.name)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    res["names"].add(a.asname or a.name.split(".")[0])
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    targets(t, res["names"])
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                targets(n.target, res["names"])
            elif isinstance(n, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                if isinstance(n, ast.If) and is_tc(n.test):
                    plain(n.orelse)
                    continue
                for part in ("body", "orelse", "finalbody"):
                    plain(getattr(n, part, []))
                for h in getattr(n, "handlers", []):
                    plain(h.body)

    L = {"names": set(), "keys": set(), "dummies": [], "missing": set(), "struct": {}, "extra": set()}

    def dummy_ref(node):
        assert isinstance(node, ast.Name) and node.id in aliases, (where, ast.dump(node)[:200])
        L["dummies"].append(aliases[node.id])

    def dict_keys(node):
        assert isinstance(node, ast.Dict), (where, ast.dump(node)[:200])
        ks = []
        for k in node.keys:
            assert isinstance(k, ast.Constant) and isinstance(k.value, str), where
            ks.append(k.value)
        return ks

    def add(key, names, replace=False):
        """`_import_structure[key] = [...]` replaces the list and keeps the key's place; extend/append/+= add to it."""
        if replace or key not in L["struct"]:
            L["struct"][key] = list(names) if replace else L["struct"].get(key, []) + list(names)
        else:
            L["struct"][key] += list(names)

    def structure(node):
        for k, v in zip(dict_keys(node), node.values):
            add(k, strs(v, where), replace=True)

    def sub_key(t):
        """_import_structure["key"] -> "key" """
        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id in LAZY_VARS:
            assert isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str), where
            return t.value.id, t.slice.value
        return None

    def lazy(body):
        for n in body:
            if isinstance(n, ast.If):
                if not is_tc(n.test):
                    lazy(n.body)
                lazy(n.orelse)
                continue
            if isinstance(n, ast.Try):
                for part in (n.body, n.orelse, n.finalbody):
                    lazy(part)
                for h in n.handlers:
                    # `except OptionalDependencyNotAvailable:` is the path with a backend missing: placeholders, often the
                    # whole dummy file of the library. Read it apart; the answer follows the path with the backends installed.
                    if isinstance(h.type, ast.Name) and h.type.id == "OptionalDependencyNotAvailable":
                        keep = L["struct"], L["extra"]
                        L["struct"], L["extra"] = {}, set()
                        lazy(h.body)
                        L["missing"] |= L["extra"] | {x for v in L["struct"].values() for x in v}
                        L["struct"], L["extra"] = keep
                    else:
                        lazy(h.body)
                continue
            if not mentions(n):
                if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and getattr(n.value.func, "id", "") == "_LazyModule":
                    pass
                else:
                    continue
            # --- statements about the lazy tables: every shape must be known ---
            if isinstance(n, ast.Assign) and len(n.targets) == 1:
                t, v = n.targets[0], n.value
                if isinstance(t, ast.Name) and t.id == "_import_structure":
                    L["struct"].clear()
                    structure(v)
                    continue
                if isinstance(t, ast.Name) and t.id in ("_dummy_objects", "_additional_imports"):
                    assert isinstance(v, ast.Dict) and not v.keys, where
                    continue
                sk = sub_key(t)
                if sk and sk[0] == "_import_structure":
                    if isinstance(v, ast.ListComp):
                        # [name for name in dir(dummy_x) if not name.startswith("_")]
                        it = v.generators[0].iter
                        assert isinstance(it, ast.Call) and it.func.id == "dir" and len(v.generators) == 1, where
                        dummy_ref(it.args[0])
                    else:
                        add(sk[1], strs(v, where), replace=True)
                    continue
                if sk and sk[0] == "_additional_imports":
                    L["extra"].add(sk[1])
                    continue
                if isinstance(t, ast.Subscript) and isinstance(v, ast.Call) and getattr(v.func, "id", "") == "_LazyModule":
                    assert v.args[2].id == "_import_structure", where
                    for kw in v.keywords:
                        if kw.arg == "extra_objects":
                            L["extra"] |= set(dict_keys(kw.value))
                        else:
                            assert kw.arg == "module_spec", (where, kw.arg)
                    continue
            if isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Add):
                sk = sub_key(n.target)
                if sk and sk[0] == "_import_structure":
                    add(sk[1], strs(n.value, where))
                    continue
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute):
                c, f = n.value, n.value.func
                sk = sub_key(f.value)
                if sk and sk[0] == "_import_structure" and f.attr in ("extend", "append") and len(c.args) == 1:
                    if f.attr == "extend":
                        add(sk[1], strs(c.args[0], where))
                    else:
                        assert isinstance(c.args[0], ast.Constant) and isinstance(c.args[0].value, str), where
                        add(sk[1], [c.args[0].value])
                    continue
                if isinstance(f.value, ast.Name) and f.attr == "update" and len(c.args) == 1:
                    a = c.args[0]
                    if f.value.id == "_import_structure":
                        structure(a)
                        continue
                    if f.value.id in ("_dummy_objects", "_additional_imports"):
                        if isinstance(a, ast.Call) and a.func.id == "get_objects_from_module":
                            dummy_ref(a.args[0])
                        else:
                            L["extra"] |= set(dict_keys(a))
                        continue
            if isinstance(n, ast.For) and isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Attribute) \
                    and getattr(n.iter.func.value, "id", "") in ("_dummy_objects", "_additional_imports") and n.iter.func.attr == "items":
                assert len(n.body) == 1 and n.body[0].value.func.id == "setattr", where
                continue
            raise SystemExit("%s: unknown statement about the lazy tables:\n%s" % (where, ast.get_source_segment(src, n)))

    if is_lazy:
        lazy(tree.body)
        via = {}            # _LazyModule fills name -> key in dict order, so the last key that lists a name wins
        for k, v in L["struct"].items():
            for x in v:
                via[x] = k
        res["lazy"] = {"names": sorted(set(via) | L["extra"]), "keys": sorted(L["struct"]), "dummies": L["dummies"],
                       "missing": sorted(L["missing"]), "via": via}
    plain(tree.body)
    # for a dummy module: the classes and functions it defines (what dir() adds apart from the two helpers it imports)
    res["defs"] = sorted(n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and not n.name.startswith("_"))
    res["all"] = None
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "__all__" and isinstance(n.value, (ast.List, ast.Tuple)):
            res["all"] = [e.value for e in n.value.elts if isinstance(e, ast.Constant)]
    res["names"] = sorted(res["names"])
    own = set()
    def defs(body):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                own.add(n.name)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    targets(t, own)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                targets(n.target, own)
            elif isinstance(n, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                if isinstance(n, ast.If) and is_tc(n.test):
                    defs(n.orelse)
                    continue
                for part in ("body", "orelse", "finalbody"):
                    defs(getattr(n, part, []))
                for h in getattr(n, "handlers", []):
                    defs(h.body)
    defs(tree.body)
    res["own"] = sorted(own)
    return res


def lazy_getattr_check(src, where):
    tree = ast.parse(src)
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef) and cls.name == "_LazyModule":
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in ("__getattr__", "__getattribute__"):
                    for c in ast.walk(fn):
                        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) and c.func.value.id == "name" \
                                and c.func.attr in ("startswith", "endswith", "replace", "removesuffix", "removeprefix", "lower", "upper"):
                            raise SystemExit("%s: _LazyModule.__getattr__ looks at the spelling of the name (%s); model it first" % (where, c.func.attr))
                        if isinstance(c, ast.Compare) and isinstance(c.left, ast.Name) and c.left.id == "name" \
                                and any(isinstance(x, ast.Constant) for x in c.comparators):
                            raise SystemExit("%s: _LazyModule.__getattr__ compares the name with a constant; model it first" % where)
            return True
    return False


cache = {}
stale = {}
res = {"tags": tags, "finals": finals, "mods": {}, "lazy": {}, "pkgs": {}, "placeholders": {}}
for t in tags:
    files = want[t]
    mods = {}
    for p, sha in files.items():
        m = p[:-3].replace("/", ".")
        pkg = m.endswith("__init__")
        m = m[:-len(".__init__")] if m.endswith(".__init__") else "" if m == "__init__" else m
        if sha not in cache:
            cache[sha] = analyse(text[sha], t + " " + p)
        mods[m] = (cache[sha], pkg)
    # every file that defines _LazyModule (utils/import_utils.py in diffusers, _lazy_module.py or import_utils.py in trl)
    lz = [p for p, sha in files.items() if lazy_getattr_check(text[sha], t + " " + p)]
    assert bool(lz) == any(a["lazy"] for a, _ in mods.values()), (t, lz)

    def rel(m, pkg, level, target):
        if level == 0:          # absolute import inside the library: target is already the module path
            return target
        base = m.split(".") if m else []
        if not pkg:
            base = base[:-1]
        base = base[:len(base) - (level - 1)]
        return ".".join(base + ([target] if target else []))

    done = {}

    def names_of(m, stack=()):
        if m in done:
            return done[m]
        a, pkg = mods[m]
        if a["lazy"]:
            # _LazyModule imports the submodule named by the key and takes the attribute from it: follow that
            out = set()
            for n in a["lazy"]["names"]:
                key = a["lazy"]["via"].get(n)
                if key is None:
                    out.add(n)          # extra_objects, _additional_imports: set on the module directly
                    continue
                d = rel(m, pkg, 1, key)
                if d in mods and d not in stack and n in names_of(d, stack + (m,)):
                    out.add(n)
                else:
                    # "nofile": the submodule the entry names is not there (RuntimeError: Failed to import ...);
                    # "noname": it is there but does not bind the name (ImportError: cannot import name)
                    stale.setdefault((m, n, key, "nofile" if d not in mods else "noname"), []).append(t)
        else:
            out = set(a["names"])
            for level, target in a["stars"]:
                d = rel(m, pkg, level, target)
                if d in mods and d not in stack:
                    src = mods[d][0]
                    out |= set(src["all"]) if src["all"] is not None else {n for n in names_of(d, stack + (m,)) if not n.startswith("_")}
        if pkg:
            pre = m + "." if m else ""
            out |= {k[len(pre):] for k in mods if k.startswith(pre) and k != m and "." not in k[len(pre):]}
        done[m] = out
        return out

    res["mods"][t] = {m: sorted(names_of(m)) for m in sorted(mods)}
    # the placeholders the top-level module hands out with a backend missing (for the check in test_data.py)
    a = mods[""][0]
    ph = set(a["lazy"]["missing"]) if a["lazy"] else set()
    for level, target in (a["lazy"]["dummies"] if a["lazy"] else a["dummies"]):
        d = rel("", True, level, target)
        assert d in mods, (t, d)
        ph |= set(mods[d][0]["defs"])
    res["placeholders"][t] = sorted(ph)
    res["lazy"][t] = sorted(m for m, (a, _) in mods.items() if a["lazy"])
    res["pkgs"][t] = sorted(m for m, (a, pkg) in mods.items() if pkg)
    if t == tags[-1]:
        res["own_latest"] = {m: a["own"] for m, (a, pkg) in sorted(mods.items()) if not a["lazy"] and a["own"]}
    print(t, len(mods), len(res["lazy"][t]), len(res["mods"][t][""]), sum(len(v) for v in res["mods"][t].values()), file=sys.stderr)
res["stale"] = [[m, n, key, kind, ts] for (m, n, key, kind), ts in sorted(stale.items())]
json.dump(res, sys.stdout, separators=(",", ":"))
