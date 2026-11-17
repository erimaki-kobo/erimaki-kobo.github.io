#!/usr/bin/env python3
"""Which names `from huggingface_hub import X`, `from huggingface_hub.utils import X` and
`from huggingface_hub.errors import X` can resolve, at the first release of every minor version (and the newest).

Usage: python3 -I names_hist.py <bare blobless clone of huggingface/huggingface_hub> hub_pypi.json > names_hist.json
Nothing from huggingface_hub is imported or run; the files are read with ast.
  top     eager releases: the relative `from .x import A` statements of __init__.py
          lazy releases:  the string lists of `_SUBMOD_ATTRS` (what the module-level __getattr__ serves)
  utils   names bound at module level in utils/__init__.py, plus `_SUBMOD_ATTRS` / `_SUBMODULES` and the special
          name "httpx" where that file has its own __getattr__
  errors  names bound at module level in errors.py
A release that is not on PyPI or is yanked there is skipped. The script stops if a __getattr__ it reads contains a
comparison or test on the name that it does not know, because that would be a rule the reading misses.
"""
import ast, json, re, subprocess, sys

REPO, PYPI = sys.argv[1], json.load(open(sys.argv[2]))


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, check=True).stdout


def ver(t):
    return tuple(int(x) for x in t[1:].split("."))


finals = sorted((t for t in git("tag").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)
                 and t[1:] in PYPI["dates"] and t[1:] not in PYPI["yanked"]), key=ver)
first = {}
for t in finals:
    first.setdefault(ver(t)[:2], t)
tags = sorted(set(first.values()) | {finals[-1]}, key=ver)
FILES = {"top": "__init__.py", "utils": "utils/__init__.py", "errors": "errors.py"}
want = {}
for t in tags:
    r = "src/huggingface_hub"
    ls = {}
    for l in git("ls-tree", "-r", t, "--", *[r + "/" + f for f in FILES.values()]).splitlines():
        meta, path = l.split("\t")
        ls[path[len(r) + 1:]] = meta.split()[2]
    assert "__init__.py" in ls, t
    want[t] = ls
shas = sorted({s for t in tags for s in want[t].values()})
have = set(git("cat-file", "--batch-check=%(objectname)", "--batch-all-objects").split())
need = [s for s in shas if s not in have]
if need:
    subprocess.run(["git", "-C", REPO, "-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "origin", "--no-tags", "--no-write-fetch-head",
                    "--recurse-submodules=no", "--filter=blob:none", "--stdin"], input="\n".join(need) + "\n", text=True, check=True)
text = {s: git("cat-file", "blob", s) for s in shas}


def strs(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def submod_attrs(tree):
    """{name: module} from the dict literal assigned to _SUBMOD_ATTRS, or None when the file has none."""
    cands = []
    for n in tree.body:
        tg = n.targets[0] if isinstance(n, ast.Assign) and len(n.targets) == 1 else n.target if isinstance(n, ast.AnnAssign) else None
        if isinstance(tg, ast.Name) and tg.id == "_SUBMOD_ATTRS":
            cands.append(n.value)
        # 0.8.x and 0.9.x pass the dict straight to _attach(...)
        v = getattr(n, "value", None)
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "_attach":
            cands += [k.value for k in v.keywords if k.arg == "submod_attrs" and isinstance(k.value, ast.Dict)]
    for value in cands:
        if True:
            assert isinstance(value, ast.Dict)
            out = {}
            for k, v in zip(value.keys, value.values):
                assert isinstance(k, ast.Constant) and isinstance(v, (ast.List, ast.Tuple)), ast.dump(k)
                assert len(strs(v)) == len(v.elts)
                for a in strs(v):
                    out.setdefault(a, k.value)
            return out
    return None


def eager(tree):
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level >= 1:
            for a in n.names:
                if a.name != "*":
                    out.setdefault(a.asname or a.name, n.module or "")
    return out


def bound(tree):
    out = set()

    def targets(t):
        if isinstance(t, ast.Name):
            out.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                targets(e)

    def walk(body):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    if a.name != "*":
                        out.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    targets(t)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                targets(n.target)
            elif isinstance(n, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "TYPE_CHECKING":
                    continue        # only for type checkers; not bound at run time
                for part in ("body", "orelse", "finalbody"):
                    walk(getattr(n, part, []))
                for h in getattr(n, "handlers", []):
                    walk(h.body)
    walk(tree.body)
    return out


def getattr_rules(tree, where):
    """String constants a module-level (or nested) __getattr__ compares the name with. Known ones only."""
    special = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name in ("__getattr__", "__getattribute__"):
            for c in ast.walk(fn):
                if isinstance(c, ast.Compare) and isinstance(c.left, ast.Name) and c.left.id == "name":
                    for comp in c.comparators:
                        special |= set(strs(comp))
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) \
                        and c.func.value.id == "name" and c.func.attr in ("startswith", "endswith", "replace", "removesuffix", "removeprefix"):
                    raise SystemExit("%s: __getattr__ looks at the spelling of the name (%s); model it first" % (where, c.func.attr))
    return special


res = {"tags": tags, "finals": finals, "top": {}, "utils": {}, "errors": {}}
for t in tags:
    src = text[want[t]["__init__.py"]]
    tree = ast.parse(src)
    lazy = submod_attrs(tree)
    sp = getattr_rules(tree, t + " __init__.py")
    assert not sp, (t, sp)
    assert (lazy if lazy is not None else eager(tree)), t + ": no names read from __init__.py"
    res["top"][t] = {"kind": "lazy" if lazy is not None else "eager", "names": dict(sorted((lazy if lazy is not None else eager(tree)).items()))}
    if "utils/__init__.py" in want[t]:
        tree = ast.parse(text[want[t]["utils/__init__.py"]])
        names = bound(tree)
        sm = submod_attrs(tree)
        if sm is not None:
            names |= set(sm)
            for n in tree.body:
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "_SUBMODULES":
                    names |= set(strs(n.value)) | ({e for e in strs(n.value.args[0])} if isinstance(n.value, ast.Call) and n.value.args else set())
        sp = getattr_rules(tree, t + " utils/__init__.py")
        assert sp <= {"httpx", "tqdm", "_tqdm"}, (t, sp)
        names |= sp & {"httpx", "tqdm"}
        res["utils"][t] = sorted(names)
    if "errors.py" in want[t]:
        res["errors"][t] = sorted(bound(ast.parse(text[want[t]["errors.py"]])))
    print(t, res["top"][t]["kind"], len(res["top"][t]["names"]), len(res["utils"].get(t, [])), len(res["errors"].get(t, [])), file=sys.stderr)
json.dump(res, sys.stdout, separators=(",", ":"))
