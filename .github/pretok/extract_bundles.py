#!/usr/bin/env python3
"""Which Ollama and llama-cpp-python release first ships a llama.cpp that accepts each pre-tokenizer name.
  Ollama: releases with in-tree (vendored, patched) llama.cpp source are read directly; the others are
          judged by the pinned llama.cpp commit (ollama_tags.json from extract_ollama.py).
  llama-cpp-python: the vendor/llama.cpp submodule commit of each vX.Y.Z tag.
A name counts as shipped by a release when the commit that added it (current span) is an ancestor of the
pinned commit. Output: bundles.json
Usage: extract_bundles.py pretok_raw.json ollama_tags.json OUT"""
import json, re, subprocess, sys
RAW, OTAGS, OUT = sys.argv[1:4]
d = json.load(open(RAW))
NAME_RE = re.compile(r'tokenizer_pre == "([^"]+)"')


def git(repo, *a):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


anc_cache = {}


def is_ancestor(a, b):
    k = (a, b)
    if k not in anc_cache:
        anc_cache[k] = subprocess.run(["git", "-C", "llama.cpp", "merge-base", "--is-ancestor", a, b]).returncode == 0
    return anc_cache[k]


def resolve(ref):
    out = git("llama.cpp", "rev-parse", "-q", "--verify", ref + "^{commit}")
    return out.strip() if out else None


names = {n: e["spans"][-1]["added"] for n, e in d["names"].items() if not e["spans"][-1]["removed"]}

# ---- Ollama
ot = json.load(open(OTAGS))["tags"]
ollama = []
for t in ot:
    vend = None
    for p in ("llama/llama.cpp/src/llama-vocab.cpp", "llama/llama.cpp/src/llama-model.cpp", "llama/llama.cpp/src/llama.cpp"):
        s = git("ollama", "show", f"{t['tag']}:{p}")
        if s and "tokenizer_pre ==" in s:
            vend = sorted(set(NAME_RE.findall(s)))
            break
    pin = resolve(t["pin"]) if t["pin"] else None
    ollama.append({"tag": t["tag"], "date": t["date"], "pin": t["pin"], "build": t["llama_build"], "vendored": vend, "pin_commit": pin})


def ollama_first(name, added):
    first = None
    for r in ollama:  # oldest first; take the start of the run that reaches the newest release
        if r["vendored"] is not None:
            ok = name in r["vendored"]
        elif r["pin_commit"]:
            ok = is_ancestor(added, r["pin_commit"])
        else:
            ok = False
        if ok and first is None:
            first = r
        elif not ok:
            first = None
    return first


# ---- llama-cpp-python
lcp_tags = [t for t in git("llama-cpp-python", "tag", "--list", "v*").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
lcp_tags.sort(key=lambda t: tuple(int(x) for x in t[1:].split(".")))
lcp = []
for t in lcp_tags:
    s = git("llama-cpp-python", "ls-tree", t, "vendor/llama.cpp")
    if not s or " commit " not in s:
        continue
    c = s.split()[2]
    if not resolve(c):
        continue
    date = git("llama-cpp-python", "log", "-1", "--format=%cd", "--date=short-local", t).strip()
    desc = git("llama.cpp", "describe", "--tags", "--match", "b*", c)
    lcp.append({"tag": t, "date": date, "pin_commit": c, "build": re.match(r"(b\d+)", desc).group(1) if desc else None})


def lcp_first(added):
    first = None
    for r in lcp:
        ok = is_ancestor(added, r["pin_commit"])
        if ok and first is None:
            first = r
        elif not ok:
            first = None
    return first


rows = {}
for n, added in sorted(names.items()):
    o = ollama_first(n, added)
    p = lcp_first(added)
    rows[n] = {"ollama": o and {"tag": o["tag"], "date": o["date"], "how": "vendored source" if o["vendored"] is not None else "pinned llama.cpp " + (o["build"] or o["pin"][:9])},
               "llama_cpp_python": p and {"tag": p["tag"], "date": p["date"], "build": p["build"]}}
out = {"ollama_latest": {k: ollama[-1][k] for k in ("tag", "date", "build")},
       "llama_cpp_python_latest": {k: lcp[-1][k] for k in ("tag", "date", "build")} if lcp else None,
       "ollama_releases": [{k: r[k] for k in ("tag", "date", "build")} | {"vendored": r["vendored"] is not None} for r in ollama],
       "llama_cpp_python_releases": [{k: r[k] for k in ("tag", "date", "build")} for r in lcp],
       "names": rows}
json.dump(out, open(OUT, "w"), indent=1)
print("ollama releases", len(ollama), "vendored", sum(r["vendored"] is not None for r in ollama), "lcp releases", len(lcp), file=sys.stderr)
print("latest ollama", out["ollama_latest"], "latest lcp", out["llama_cpp_python_latest"], file=sys.stderr)
for n in ("qwen2", "smaug-bpe", "tekken", "qwen35", "gemma4", "glm5", "domyn-edge", "command-r", "grok-2", "inkling2"):
    if n in rows:
        print(n, rows[n], file=sys.stderr)
print("no ollama yet:", [n for n, r in rows.items() if not r["ollama"]], file=sys.stderr)
print("no lcp yet:", [n for n, r in rows.items() if not r["llama_cpp_python"]], file=sys.stderr)
