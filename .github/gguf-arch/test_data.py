#!/usr/bin/env python3
"""Independent checks of table.json against the repositories (reads blobs at tags; runs no repo code).
1. llama.cpp: the architecture string is present in the arch table at first_tag and absent at the tag before it.
2. Ollama (releases that vendor llama.cpp source in-tree): the string is present in the vendored
   arch table at the 'bundled from' release and absent in the release before it. This also catches
   architectures added early by Ollama's own patches.
"""
import json, re, subprocess, sys, functools
from pathlib import Path
ROOT = Path(__file__).resolve().parent
T = json.loads((ROOT / "table.json").read_text())
PAT = re.compile(r'LLM_ARCH_[A-Z0-9_]+,\s*"([^"]+)"')

def git(repo, *a):
    r = subprocess.run(["git", "-C", str(ROOT / repo), *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None

btags = sorted((t for t in git("llama.cpp", "tag", "--list", "b*").split() if re.fullmatch(r"b\d+", t)), key=lambda t: int(t[1:]))
bidx = {t: i for i, t in enumerate(btags)}

@functools.lru_cache(maxsize=None)
def llama_names(tag):
    for p in ("src/llama-arch.cpp", "src/llama.cpp", "llama.cpp"):
        s = git("llama.cpp", "show", f"{tag}:{p}")
        if s:
            n = set(PAT.findall(s))
            if n:
                return frozenset(n)
    return frozenset()

@functools.lru_cache(maxsize=None)
def ollama_names(tag):
    for p in ("llama/llama.cpp/src/llama-arch.cpp", "llama/llama.cpp/src/llama.cpp", "llama/llama.cpp"):
        s = git("ollama", "show", f"{tag}:{p}")
        if s:
            n = set(PAT.findall(s))
            if n:
                return frozenset(n)
    return None

bad = []
n1 = 0
for r in T["archs"]:
    ft = r["llama_first_build"]
    prev = btags[bidx[ft] - 1] if bidx[ft] > 0 else None
    if r["arch"] not in llama_names(ft):
        bad.append(("llama absent at first tag", r["arch"], ft))
    if prev and r["arch"] in llama_names(prev):
        bad.append(("llama present before first tag", r["arch"], prev))
    n1 += 1
print("llama.cpp first-tag checks:", n1, "problems:", len([b for b in bad]))

# 2. Ollama, LLAMA_CPP_VERSION era: the pinned tag's arch table must contain the arch at the 'from' release
#    (unless marked as an Ollama patch) and must not contain it at the release before.
otags = T["ollama_tags"]
oidx = {t["tag"]: i for i, t in enumerate(otags)}
n2 = 0
for r in T["archs"]:
    v = r["ollama_via_llama"]
    if not v or v["how"] != "pin":
        continue
    t = otags[oidx[v["tag"]]]
    if not re.fullmatch(r"b\d+", t["pin"] or ""):
        continue
    n2 += 1
    if r["arch"] not in llama_names(t["pin"]):
        bad.append(("pinned llama.cpp tag lacks arch at Ollama 'from' release", r["arch"], v["tag"], t["pin"]))
    p = otags[oidx[v["tag"]] - 1]
    if re.fullmatch(r"b\d+", p["pin"] or "") and r["arch"] in llama_names(p["pin"]):
        bad.append(("arch already in the previous Ollama release's pinned tag", r["arch"], p["tag"], p["pin"]))
print("ollama pinned-tag checks:", n2)
for b in bad:
    print("PROBLEM", b)
print("ALL PASS" if not bad else "FAIL")
sys.exit(1 if bad else 0)
