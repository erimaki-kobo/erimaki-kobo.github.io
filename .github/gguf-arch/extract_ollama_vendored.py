#!/usr/bin/env python3
"""Architecture names in the llama.cpp source that Ollama vendored in-tree (after its own patches),
per release tag. Tags without vendored source get null. Also lists LLM_ARCH additions found in
Ollama's patch directories for the other eras. Output: ollama_vendored.json"""
import json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
PAT = re.compile(r'LLM_ARCH_[A-Z0-9_]+,\s*"([^"]+)"')
def git(*a):
    r = subprocess.run(["git", "-C", str(ROOT / "ollama"), *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None
tags = [t["tag"] for t in json.loads((ROOT / "ollama_tags.json").read_text())["tags"]]
out, patch_adds = {}, {}
for t in tags:
    names = None
    for p in ("llama/llama.cpp/src/llama-arch.cpp", "llama/llama.cpp/src/llama.cpp", "llama/llama.cpp"):
        s = git("show", f"{t}:{p}")
        if s:
            n = sorted(set(PAT.findall(s)))
            if n:
                names = n
                break
    out[t] = names
    if names is None:
        for d in ("llama/compat", "llm/patches", "llama/patches"):
            s = git("grep", "-h", "-E", r'^\+.*LLM_ARCH_[A-Z0-9_]+,\s*"', t, "--", d)
            if s:
                patch_adds.setdefault(t, sorted(set(PAT.findall(s))))
json.dump({"vendored": out, "patch_adds_other_eras": patch_adds}, open(ROOT / "ollama_vendored.json", "w"), indent=1)
have = [t for t in tags if out[t]]
print("tags with vendored source:", len(have), have[0], "..", have[-1], file=sys.stderr)
print("patch-added archs in other eras:", {k: v for k, v in list(patch_adds.items())[:3]}, "... total tags", len(patch_adds), sorted({a for v in patch_adds.values() for a in v}), file=sys.stderr)
