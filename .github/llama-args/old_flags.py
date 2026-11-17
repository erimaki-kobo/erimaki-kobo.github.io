#!/usr/bin/env python3
"""Options llama.cpp had before common/arg.cpp existed (b3716, 2024-09-09), coarsely.

Usage: python3 -I old_flags.py <llama.cpp clone> <args_hist.json> > old_flags.json
Before b3716 the options were parsed by hand (`if (arg == "--name")`) in common/common.cpp and, for the server
until mid 2024, in examples/server/server.cpp. This reads those files at a build tag every ~250 builds from the first
GGUF build (b1046) and reports every name seen there that the first common/arg.cpp no longer has, with the last
snapshot that still had it and the first that did not: "removed between bA and bB".
"""
import json, os, re, subprocess, sys

REPO, HIST = sys.argv[1], json.load(open(sys.argv[2]))
ENV = dict(os.environ, TZ="UTC")
FILES = ["common/common.cpp", "examples/common.cpp", "examples/server/server.cpp", "examples/main/main.cpp"]


def git(*a, check=True):
    r = subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, env=ENV)
    if check and r.returncode:
        raise SystemExit(r.stderr)
    return r.stdout if r.returncode == 0 else None


tags = sorted(int(t[1:]) for t in git("tag").split() if re.fullmatch(r"b\d+", t))
first_arg = HIST["commits"][0]["build"][0]
want = [1046] + list(range(1250, first_arg, 250))
snaps = []
for w in want:
    b = min(t for t in tags if t >= w)
    names = set()
    for f in FILES:
        src = git("show", "b%d:%s" % (b, f), check=False)
        if src:
            names |= set(re.findall(r'arg == "(-{1,2}[A-Za-z][\w-]*)"', src))
    date = git("log", "-1", "--date=short-local", "--format=%cd", "b%d" % b).strip()
    snaps.append((b, date, names))
    print("b%d" % b, date, len(names), file=sys.stderr)
new = set()
for o in HIST["commits"][0]["options"]:
    new |= set(o["names"]) | set(o["neg"])
ever_new = set()
for c in HIST["commits"]:
    for o in c["options"]:
        ever_new |= set(o["names"]) | set(o["neg"])
out = {}
for i, (b, d, names) in enumerate(snaps):
    for n in names:
        if n in new or n in ever_new:
            continue
        nxt = snaps[i + 1] if i + 1 < len(snaps) else (first_arg, HIST["commits"][0]["build"][1], new)
        if n not in nxt[2]:
            out[n] = {"last_seen": [b, d], "gone_by": [nxt[0], nxt[1]]}     # later snapshots overwrite earlier ones
        else:
            out.pop(n, None)
json.dump({"snapshots": [[b, d, len(n)] for b, d, n in snaps], "first_arg_cpp": HIST["commits"][0]["build"], "flags": dict(sorted(out.items()))},
          sys.stdout, indent=0)
