#!/usr/bin/env python3
"""Independent check of data.json: plain text search of common/arg.cpp at build tags.

Usage: python3 -I test_data.py <llama.cpp clone> data.json
build_data.py works from parsed add_opt(...) blocks at commits; this looks for the quoted name in the file at the
tag where data.json says the name appeared or disappeared, and at the tag before it.
Checks every removed name, every stub, every removed environment variable, and a sample of additions.
"""
import json, random, re, subprocess, sys

REPO, D = sys.argv[1], json.load(open(sys.argv[2]))
tags = sorted(int(t[1:]) for t in subprocess.run(["git", "-C", REPO, "tag"], capture_output=True, text=True).stdout.split() if re.fullmatch(r"b\d+", t))
cache = {}


def src(b):
    if b not in cache:
        cache[b] = subprocess.run(["git", "-C", REPO, "show", "b%d:common/arg.cpp" % b], capture_output=True, text=True, check=True).stdout
    return cache[b]


def has(b, name):
    return ('"%s"' % name) in src(b)


def before(b):
    return tags[tags.index(b) - 1]


ok = bad = 0
def check(cond, what):
    global ok, bad
    if cond:
        ok += 1
    else:
        bad += 1
        print("FAIL", what)

first = D["first"][0]
for n, f in D["flags"].items():
    if "rm" in f and "stub" not in f:                      # gone: quoted name present just before, absent from then on
        b = f["rm"][0]
        check(has(before(b), n) and not has(b, n) and not has(D["latest"][0], n), ("removed", n, b))
    if "stub" in f:
        b = f["stub"][0]
        check(has(b, n) and "the argument has been removed" in src(b) and "the argument has been removed" not in src(before(b)) or
              (has(b, n) and has(D["latest"][0], n)), ("stub", n, b))
random.seed(7)
added = [(n, f["any"][0][0]) for n, f in D["flags"].items() if f["any"] and f["any"][0][0] > first]
for n, b in random.sample(added, 60):
    check(has(b, n) and not has(before(b), n), ("added", n, b))
for n, e in D["envs"].items():
    if e["r"][-1][1] and not e.get("derived") and "stub" not in e:
        b = e["r"][-1][1]
        check(has(before(b), n) and not has(b, n), ("env removed", n, b))
# the three binaries and the example they parse with
def grep(spec, pat):
    r = subprocess.run(["git", "-C", REPO, "show", spec], capture_output=True, text=True)
    return bool(re.search(pat, r.stdout))
sw = D["cli_switch"]
check(grep("b%d:tools/cli/cli.cpp" % sw, r"common_params_parse\([^;]*LLAMA_EXAMPLE_CLI"), "llama-cli parses as CLI at the switch")
check(grep("b%d:tools/completion/completion.cpp" % sw, r"common_params_parse\([^;]*LLAMA_EXAMPLE_COMPLETION"), "llama-completion at the switch")
check(grep("b%d:tools/main/main.cpp" % before(sw), r"common_params_parse\([^;]*LLAMA_EXAMPLE_MAIN"), "llama-cli parses as MAIN before the switch")
check(grep("b%d:tools/server/server.cpp" % D["latest"][0], r"common_params_parse\([^;]*LLAMA_EXAMPLE_SERVER"), "llama-server parses as SERVER")
check("error: invalid argument: %s" in src(first) and "error: invalid argument: %s" in src(D["latest"][0]), "wording from the first arg.cpp")
print("%d/%d" % (ok, ok + bad), "tags read:", len(cache))
sys.exit(1 if bad else 0)
