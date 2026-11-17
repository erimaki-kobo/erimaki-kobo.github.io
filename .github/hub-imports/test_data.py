#!/usr/bin/env python3
"""Second reading, by other means than names_hist.py and downstream_hist.py. Nothing is imported or run.

Usage: python3 -I test_data.py <hub clone> names_hist.json data.json checks.json lib=<clone>:<package dir>:<ds_lib.json> ...
  (the release tags are taken from the file downstream_hist.py wrote)
 1. Lazy releases of huggingface_hub carry a generated static copy of the runtime table under `if TYPE_CHECKING:`
    (utils/check_static_imports.py keeps it in sync). The names read from the runtime table must equal that copy.
 2. For every (library, removed name) run in data.json: a plain-text search (regular expression, no ast) of the library's
    files must find an import of the name at the last version of the run and at the first, and, where the run ended,
    no import outside a try block or function at the next version (indented imports are allowed there).
 3. Anchors: facts known from release notes, deprecation messages and public error reports.
"""
import ast, json, re, subprocess, sys
HUB, H, D = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
LIBS = dict((a.split("=", 1)[0], a.split("=", 1)[1].split(":")) for a in sys.argv[5:])


def show(repo, spec):
    return subprocess.run(["git", "-C", repo, "show", spec], capture_output=True, text=True, check=True).stdout


lazy = same = 0
diff = []
for t in H["tags"]:
    if H["top"][t]["kind"] != "lazy":
        continue
    tree = ast.parse(show(HUB, t + ":src/huggingface_hub/__init__.py"))
    tc = [n for n in tree.body if isinstance(n, ast.If) and "TYPE_CHECKING" in ast.dump(n.test)]
    if not tc:
        continue
    mirror = {a.asname or a.name for n in ast.walk(ast.Module(body=tc[-1].body, type_ignores=[])) if isinstance(n, ast.ImportFrom) and n.level >= 1 for a in n.names}
    mine = set(H["top"][t]["names"])
    lazy += 1
    if mine == mirror:
        same += 1
    else:
        diff.append((t, sorted(mine - mirror)[:5], sorted(mirror - mine)[:5]))
print("1. runtime table vs generated static copy: %d lazy releases with a copy, identical in %d" % (lazy, same))
for d in diff:
    print("   ", d)


def files(repo, tag, pkg):
    ls = subprocess.run(["git", "-C", repo, "ls-tree", "-r", tag, "--", *pkg.split(",")], capture_output=True, text=True, check=True).stdout.splitlines()
    paths = [l.split("\t")[1] for l in ls if l.endswith(".py")]
    buf = subprocess.run(["git", "-C", repo, "cat-file", "--batch"], input="".join("%s:%s\n" % (tag, p) for p in paths).encode(), capture_output=True, check=True).stdout
    out, i = {}, 0
    for p in paths:
        nl = buf.index(b"\n", i)
        n = int(buf[i:nl].split()[2])
        out[p] = buf[nl + 1:nl + 1 + n].decode("utf-8", "replace")
        i = nl + 2 + n
    return out


MOD = {"top": r"huggingface_hub", "utils": r"huggingface_hub\.utils", "errors": r"huggingface_hub\.errors"}


def hits(fs, kind, name):
    """(imports at column 0, indented imports) found by regular expression."""
    rx = re.compile(r"^([ \t]*)from " + MOD[kind] + r" import (\([^)]*\)|[^\n]*(?:\\\n[^\n]*)*)", re.M)
    top = ind = 0
    for src in fs.values():
        if "huggingface_hub" not in src:
            continue
        for m in rx.finditer(src):
            if re.search(r"\b%s\b" % re.escape(name), m.group(2)):
                if m.group(1):
                    ind += 1
                else:
                    top += 1
    return top, ind


runs = bad2 = 0
TAGS = {}
cache = {}
for key, libs in sorted(D["users"].items()):
    kind, name = key.split(":")
    for lib, rr in libs.items():
        repo, pkg, ds = LIBS[lib]
        tagof = TAGS.setdefault(lib, json.load(open(ds))["tags"])
        for a, b, f, nxt in rr:
            runs += 1
            res = []
            for v in (a, b, nxt):
                if v is None:
                    res.append(None)
                    continue
                if (lib, v) not in cache:
                    cache[(lib, v)] = files(repo, tagof[v], pkg)
                res.append(hits(cache[(lib, v)], kind, name))
            ok = res[0][0] + res[0][1] > 0 and res[1][0] + res[1][1] > 0 and (res[2] is None or res[2][0] == 0)
            if not ok:
                bad2 += 1
                print("   ", lib, key, a, b, nxt, res)
print("2. plain-text search at the ends of each run: %d runs, %d disagree" % (runs, bad2))


def has(kind, v, name):
    d = D[kind].get(name)
    if d is None:
        return False
    d = d[1:] if kind == "top" else d
    i = [r[0] for r in D["releases"]].index(v)
    return any(a <= i and (b == 0 or i < b) for a, b in zip(d[::2], d[1::2]))


anchors = [("top", "0.25.0", "cached_download", True), ("top", "0.26.0", "cached_download", False),      # @_deprecate_method(version="0.26")
           ("top", "0.36.0", "HfFolder", True), ("top", "1.0.0", "HfFolder", False),
           ("top", "0.36.0", "Repository", True), ("top", "1.0.0", "Repository", False),                 # docstring: removal in v1.0
           ("top", "0.36.0", "InferenceApi", True), ("top", "1.0.0", "InferenceApi", False),             # deprecated for 1.0
           ("top", "0.23.0", "ModelFilter", True), ("top", "0.24.0", "ModelFilter", False),              # "removed in >=0.24"
           ("top", "0.14.0", "InferenceClient", False), ("top", "0.15.0", "InferenceClient", True),
           ("top", "2.4.0", "hf_hub_download", True), ("top", "2.4.0", "snapshot_download", True),
           ("errors", "0.25.0", "EntryNotFoundError", True), ("utils", "2.4.0", "HfHubHTTPError", True)]
wrong = [a for a in anchors if has(*a[:3]) != a[3]]
print("3. anchors: %d, wrong %s" % (len(anchors), wrong))
json.dump({"CHK_LAZY": lazy, "CHK_SAME": same, "CHK_RUNS": runs, "CHK_ANCHORS": len(anchors)}, open(sys.argv[4], "w"))
sys.exit(1 if diff or bad2 or wrong else 0)
