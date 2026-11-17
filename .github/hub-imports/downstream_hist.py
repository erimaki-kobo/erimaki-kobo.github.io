#!/usr/bin/env python3
"""Which huggingface_hub names a library imports, at the first release of each of its minor versions.

Usage: python3 -I downstream_hist.py <bare blobless clone> <dates json from pypi_dates.py> <package dir[,dir2]> > out.json
Reads every .py file under the package dir at each release tag with ast and records
`from huggingface_hub import A`, `from huggingface_hub.utils import A`, `from huggingface_hub.errors import A`.
An import is "hard" when it sits at module level outside any try block, function or class and outside
`if TYPE_CHECKING:` : importing that file fails if the name is missing. Everything else is "soft".
Tags may be vX.Y.Z, X.Y.Z or <name>@X.Y.Z. Nothing is imported or run.
"""
import ast, json, re, subprocess, sys

REPO, PYPI, DIRS = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3].split(",")
MODS = {"huggingface_hub": "top", "huggingface_hub.utils": "utils", "huggingface_hub.errors": "errors"}


def git(*a, inp=None, binary=False):
    p = subprocess.run(["git", "-C", REPO, *a], capture_output=True, check=True, input=inp)
    return p.stdout if binary else p.stdout.decode()


vt = {}
for t in git("tag").split():
    m = re.fullmatch(r"(?:v|[a-z_-]+@)?(\d+\.\d+\.\d+)", t)
    if m and m.group(1) in PYPI["dates"] and m.group(1) not in PYPI["yanked"]:
        if t.startswith("@") or ("@" in t and not t.startswith(sys.argv[4] + "@" if len(sys.argv) > 4 else "\0")):
            continue
        vt.setdefault(m.group(1), t)
key = lambda v: tuple(int(x) for x in v.split("."))
first = {}
for v in sorted(vt, key=key):
    first.setdefault(key(v)[:2], v)
versions = sorted(set(first.values()) | {max(vt, key=key)}, key=key)

want = {}
for v in versions:
    ls = {}
    for d in DIRS:
        for l in git("ls-tree", "-r", vt[v], "--", d).splitlines():
            meta, path = l.split("\t")
            if path.endswith(".py"):
                ls[path] = meta.split()[2]
    if ls:
        want[v] = ls
versions = [v for v in versions if v in want]
shas = sorted({s for v in versions for s in want[v].values()})
have = set(git("cat-file", "--batch-check=%(objectname)", "--batch-all-objects").split())
need = [s for s in shas if s not in have]
for i in range(0, len(need), 4000):
    subprocess.run(["git", "-C", REPO, "-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "origin", "--no-tags", "--no-write-fetch-head",
                    "--recurse-submodules=no", "--filter=blob:none", "--stdin"], input=("\n".join(need[i:i + 4000]) + "\n").encode(), check=True)
buf = git("cat-file", "--batch", inp=("\n".join(shas) + "\n").encode(), binary=True)
text, i = {}, 0
for s in shas:
    nl = buf.index(b"\n", i)
    n = int(buf[i:nl].split()[2])
    text[s] = buf[nl + 1:nl + 1 + n]
    i = nl + 2 + n


def imports(src):
    """[(kind, name, hard)]"""
    if b"huggingface_hub" not in src:
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []

    def walk(body, hard):
        for n in body:
            if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module in MODS:
                out.extend((MODS[n.module], a.name, hard) for a in n.names if a.name != "*")
            elif isinstance(n, ast.If):
                tc = "TYPE_CHECKING" in ast.dump(n.test)
                walk(n.body, hard and not tc)
                walk(n.orelse, hard)
            elif isinstance(n, ast.Try):
                walk(n.body, False)
                for h in n.handlers:
                    walk(h.body, False)
                walk(n.orelse, False)
                walk(n.finalbody, hard)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.With, ast.For, ast.While)):
                walk(n.body, False)
    walk(tree.body, True)
    return out


cache = {s: imports(t) for s, t in text.items()}
res = {"versions": versions, "dates": {v: PYPI["dates"][v] for v in versions}, "tags": {v: vt[v] for v in versions}, "imports": {}}
for v in versions:
    d = {}
    for path, s in sorted(want[v].items()):
        for kind, name, hard in cache[s]:
            e = d.setdefault(kind + ":" + name, {"hard": [], "soft": []})
            e["hard" if hard else "soft"].append(path)
    res["imports"][v] = {k: {"hard": len(e["hard"]), "soft": len(e["soft"]), "file": (e["hard"] or e["soft"])[0]} for k, e in sorted(d.items())}
    print(v, len(want[v]), "files,", len(d), "names", file=sys.stderr)
json.dump(res, sys.stdout, separators=(",", ":"))
