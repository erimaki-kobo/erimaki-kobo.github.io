#!/usr/bin/env python3
"""Second reading of data.json's "users" (which library versions import a removed transformers name). No ast, nothing run.

Usage: python3 -I test_users.py data.json checks.json lib=<clone>:<package dir>:<ds_lib.json> ...
For every run, a regular-expression search of the library's files must find an import of the name at the first and the last
version of the run, and no import at column 0 in the version after it. Adds CHK_RUNS to checks.json.
"""
import json, re, subprocess, sys
D, CHK = json.load(open(sys.argv[1])), sys.argv[2]
LIBS = dict((a.split("=", 1)[0], a.split("=", 1)[1].split(":")) for a in sys.argv[3:])
MOD = {"top": r"transformers", "utils": r"transformers\.utils", "file_utils": r"transformers\.file_utils"}


def files(repo, tag, pkg):
    ls = subprocess.run(["git", "-C", repo, "ls-tree", "-r", tag, "--", *pkg.split(",")], capture_output=True, text=True, check=True).stdout.splitlines()
    paths = [l.split("\t")[1] for l in ls if l.endswith(".py")]
    buf = subprocess.run(["git", "-C", repo, "cat-file", "--batch"], input="".join("%s:%s\n" % (tag, p) for p in paths).encode(), capture_output=True, check=True).stdout
    out, i = [], 0
    for p in paths:
        nl = buf.index(b"\n", i)
        n = int(buf[i:nl].split()[2])
        out.append(buf[nl + 1:nl + 1 + n].decode("utf-8", "replace"))
        i = nl + 2 + n
    return out


def hits(fs, kind, name):
    rx = re.compile(r"^([ \t]*)from " + MOD[kind] + r" import (\([^)]*\)|[^\n]*(?:\\\n[^\n]*)*)", re.M)
    top = ind = 0
    for src in fs:
        if "transformers" in src:
            for m in rx.finditer(src):
                if re.search(r"\b%s\b" % re.escape(name), m.group(2)):
                    if m.group(1):
                        ind += 1
                    else:
                        top += 1
    return top, ind


runs = bad = 0
cache, tags = {}, {}
for key, libs in sorted(D["users"].items()):
    kind, name = key.split(":")
    for lib, rr in libs.items():
        repo, pkg, ds = LIBS[lib]
        tg = tags.setdefault(lib, json.load(open(ds))["tags"])
        for a, b, f, nxt in rr:
            runs += 1
            res = []
            for v in (a, b, nxt):
                if v is None:
                    res.append(None)
                    continue
                if (lib, v) not in cache:
                    cache[(lib, v)] = files(repo, tg[v], pkg)
                res.append(hits(cache[(lib, v)], kind, name))
            if not (sum(res[0]) > 0 and sum(res[1]) > 0 and (res[2] is None or res[2][0] == 0)):
                bad += 1
                print("   ", lib, key, a, b, nxt, res)
print("users: %d runs, %d disagree with the plain-text search" % (runs, bad))
c = json.load(open(CHK))
c["CHK_RUNS"] = runs
json.dump(c, open(CHK, "w"))
sys.exit(1 if bad else 0)
