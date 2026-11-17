#!/usr/bin/env python3
"""Which names `from transformers import X`, `from transformers.utils import X` and
`from transformers.file_utils import X` can resolve, at the first release of every minor version (and the newest).

Usage: python3 -I names_hist.py <bare blobless clone of huggingface/transformers> tf_pypi.json > names_hist.json
A release that is not on PyPI or is yanked there is skipped: the first release of a minor is the first one pip installs.
Nothing from transformers is imported or run. The files are read with ast:
  top level  v2.0-v3.x  the relative `from .x import A` statements of __init__.py (the module was not lazy)
             v4.0+      the string lists of `_import_structure` in __init__.py (what _LazyModule serves), without the
                        `utils.dummy_*` placeholders; where __init__.py calls define_import_structure (v4.52+), plus the
                        `__all__` of every file under models/
  utils      names bound at module level in utils/__init__.py (imports, assignments, defs, classes)
  file_utils names bound at module level in file_utils.py
  aliases    v5 resolves some names that are in no list: _LazyModule.__getattr__ (utils/import_utils.py) maps
             XTokenizerFast to XTokenizer, XImageProcessorFast to XImageProcessor, and tokenizer names through
             SLOW_TO_FAST_CONVERTERS (convert_slow_tokenizer.py). Which of the three rules a release has is read
             from the text of that method; the converter table is read with ast.
"""
import ast, json, re, subprocess, sys

REPO = sys.argv[1]
PYPI = json.load(open(sys.argv[2]))


def git(*a, inp=None):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, check=True, input=inp).stdout


def ver(t):
    return tuple(int(x) for x in t[1:].split("."))


finals = sorted((t for t in git("tag").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t) and ver(t) >= (2, 0, 0)
                 and t[1:] in PYPI["dates"] and t[1:] not in PYPI["yanked"]), key=ver)
first_of_minor = {}
for t in finals:
    first_of_minor.setdefault(ver(t)[:2], t)
tags = sorted(set(first_of_minor.values()) | {finals[-1]}, key=ver)


def root(t):
    return "src/transformers" if git("ls-tree", t, "--", "src/transformers").strip() else "transformers"


# ---- which blobs are needed ----
want = {}          # tag -> {path: sha}
for t in tags:
    r = root(t)
    ls = {}
    for l in git("ls-tree", "-r", t, "--", r + "/__init__.py", r + "/utils/__init__.py", r + "/file_utils.py", r + "/models",
                      r + "/utils/import_utils.py", r + "/convert_slow_tokenizer.py").splitlines():
        meta, path = l.split("\t")
        if path.endswith(".py"):
            ls[path[len(r) + 1:]] = meta.split()[2]
    want[t] = ls
init_sha = {t: want[t]["__init__.py"] for t in tags}


def fetch(shas):
    have = set(git("cat-file", "--batch-check=%(objectname) %(objecttype)", "--batch-all-objects").split())
    need = sorted(set(shas) - have)
    for i in range(0, len(need), 4000):
        subprocess.run(["git", "-C", REPO, "-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "origin", "--no-tags",
                        "--no-write-fetch-head", "--recurse-submodules=no", "--filter=blob:none", "--stdin"],
                       input="\n".join(need[i:i + 4000]) + "\n", text=True, check=True)


def cat(shas):
    """{sha: text} through one cat-file --batch."""
    shas = sorted(set(shas))
    p = subprocess.run(["git", "-C", REPO, "cat-file", "--batch"], input=("\n".join(shas) + "\n").encode(), capture_output=True, check=True)
    out, buf, i = {}, p.stdout, 0
    for s in shas:
        nl = buf.index(b"\n", i)
        head = buf[i:nl].split()
        assert head[0].decode() == s and head[1] == b"blob", head
        n = int(head[2])
        out[s] = buf[nl + 1:nl + 1 + n].decode("utf-8", "replace")
        i = nl + 1 + n + 1
    return out


fetch([s for t in tags for p, s in want[t].items() if not p.startswith("models/")])
small = cat([s for t in tags for p, s in want[t].items() if not p.startswith("models/")])
scan_models = {t for t in tags if "define_import_structure(" in small[init_sha[t]]}
model_shas = {s for t in scan_models for p, s in want[t].items() if p.startswith("models/") and not p.endswith("__init__.py")}
fetch(model_shas)
models = cat(model_shas)


def strs(node):
    """String constants of a list/tuple/set literal (or a single string)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def is_struct(n):
    return isinstance(n, ast.Name) and n.id == "_import_structure"


def lazy_names(tree):
    """{name: module key} from every way __init__.py fills _import_structure."""
    out = {}

    def add(key, names):
        if key is None or key.startswith("utils.dummy_"):
            return
        for n in names:
            out.setdefault(n, key)

    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            tg = n.targets[0]
            if is_struct(tg) and isinstance(n.value, ast.Dict):
                for k, v in zip(n.value.keys, n.value.values):
                    if isinstance(k, ast.Constant):
                        add(k.value, strs(v))
            elif isinstance(tg, ast.Subscript) and is_struct(tg.value):
                add(strs(tg.slice)[0] if strs(tg.slice) else None, strs(n.value))
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Subscript) and is_struct(n.target.value):
            add(strs(n.target.slice)[0] if strs(n.target.slice) else None, strs(n.value))
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("extend", "append")
              and isinstance(n.func.value, ast.Subscript) and is_struct(n.func.value.value) and n.args):
            k = strs(n.func.value.slice)
            add(k[0] if k else None, strs(n.args[0]))
    return out


def eager_names(tree):
    """{name: module} for the relative imports of a non-lazy __init__.py."""
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level >= 1:
            for a in n.names:
                if a.name != "*":
                    out.setdefault(a.asname or a.name, n.module or "")
    return out


def bound_names(tree):
    """Every name a module binds at module level (also inside if/try/else blocks, not inside functions or classes)."""
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
                for part in ("body", "orelse", "finalbody"):
                    walk(getattr(n, part, []))
                for h in getattr(n, "handlers", []):
                    walk(h.body)
    walk(tree.body)
    return out


def dunder_all(text):
    if "__all__" not in text:
        return []
    for n in ast.parse(text).body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets):
            return strs(n.value)
    return []


def alias_rules(t):
    """Which dynamic fallbacks _LazyModule.__getattr__ has at this tag, and the converter table."""
    src = small.get(want[t].get("utils/import_utils.py", ""), "")
    if "class _LazyModule" not in src:
        return None
    cls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ClassDef) and n.name == "_LazyModule"][0]
    ga = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__getattr__"]
    body = ast.unparse(ga[0]) if ga else ""
    rules = {"tok_fast": "name.endswith('TokenizerFast')" in body and "fallback_name in self._class_to_module" in body,
             "img_fast": "name.endswith('ImageProcessorFast')" in body,
             "conv": "SLOW_TO_FAST_CONVERTERS" in body}
    # anything else that looks at the spelling of the name would be a rule this script does not know
    known = {"TokenizerFast", "Tokenizer", "ImageProcessorFast", "ImageProcessor"}
    seen = set(re.findall(r"endswith\('(\w+)'\)", body))
    assert seen <= known, (t, seen - known)
    conv = {}
    if rules["conv"]:
        for n in ast.parse(small[want[t]["convert_slow_tokenizer.py"]]).body:
            tg = n.targets[0] if isinstance(n, ast.Assign) else n.target if isinstance(n, ast.AnnAssign) else None
            if isinstance(tg, ast.Name) and tg.id == "SLOW_TO_FAST_CONVERTERS":
                assert isinstance(n.value, ast.Dict), t
                conv = {k.value: v.id for k, v in zip(n.value.keys, n.value.values)}
        assert conv, t
    rules["converters"] = conv
    return rules if any(rules[k] for k in ("tok_fast", "img_fast", "conv")) else None


all_cache = {s: dunder_all(txt) for s, txt in models.items()}
res = {"tags": tags, "finals": finals, "scan_models": sorted(scan_models, key=ver), "top": {}, "utils": {}, "file_utils": {}, "alias": {}}
for t in tags:
    tree = ast.parse(small[init_sha[t]])
    if "_import_structure" in small[init_sha[t]]:
        top = lazy_names(tree)
        kind = "lazy"
    else:
        top = eager_names(tree)
        kind = "eager"
    if t in scan_models:
        for p, s in sorted(want[t].items()):
            if s in all_cache:
                for n in all_cache[s]:
                    top.setdefault(n, p[:-3].replace("/", "."))
    res["top"][t] = {"kind": kind, "names": dict(sorted(top.items()))}
    ar = alias_rules(t)
    if ar:
        res["alias"][t] = ar
    for key, path in (("utils", "utils/__init__.py"), ("file_utils", "file_utils.py")):
        if path in want[t]:
            res[key][t] = sorted(bound_names(ast.parse(small[want[t][path]])))
    print(t, kind, len(top), len(res["utils"].get(t, [])), len(res["file_utils"].get(t, [])), file=sys.stderr)
json.dump(res, sys.stdout, separators=(",", ":"))
