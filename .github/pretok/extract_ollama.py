#!/usr/bin/env python3
"""For every Ollama release tag (vX.Y.Z, no -rc): which llama.cpp commit/tag it pins,
which llama.cpp bNNNN build that is equivalent to, and which architectures the
Go engine (model/models/<arch>) implements natively.

Pin forms over time (newest first):
  LLAMA_CPP_VERSION file                (from 2026-05, tag like b12177 or a commit)
  Makefile.sync  FETCH_HEAD=<commit>    (2025-01 .. 2026-05)
  llama/vendoring LLAMACPP_BASE_COMMIT= (2024-10 .. 2025-01)
  llm/llama.cpp submodule gitlink       (.. 2024-10)
Output: ollama_tags.json
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OL = ROOT / "ollama"
LC = ROOT / "llama.cpp"

def git(repo, *a, ok=False):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
    if r.returncode and not ok:
        raise RuntimeError(r.stderr)
    return r.stdout if r.returncode == 0 else None

def show(tag, path):
    return git(OL, "show", f"{tag}:{path}", ok=True)

def pin_for(tag):
    s = show(tag, "LLAMA_CPP_VERSION")
    if s is not None:
        return s.strip(), "LLAMA_CPP_VERSION"
    s = show(tag, "Makefile.sync")
    if s is not None:
        m = re.search(r"^FETCH_HEAD=(\S+)", s, re.M)
        if m:
            return m.group(1), "Makefile.sync"
    s = show(tag, "llama/vendoring")
    if s is not None:
        m = re.search(r"LLAMACPP_BASE_COMMIT=(\S+)", s)
        if m:
            return m.group(1), "llama/vendoring"
    s = git(OL, "ls-tree", tag, "llm/llama.cpp", ok=True)
    if s and "\tcommit\t" in s.replace(" commit ", "\tcommit\t"):
        parts = s.split()
        if len(parts) >= 3 and parts[1] == "commit":
            return parts[2], "submodule llm/llama.cpp"
    return None, None

def build_of(ref):
    """Map a llama.cpp ref to (equivalent build tag, exact?)."""
    if re.fullmatch(r"b\d+", ref):
        return ref, True, git(LC, "log", "-1", "--format=%cd", "--date=short-local", ref, ok=True).strip() if git(LC, "rev-parse", "-q", "--verify", ref + "^{commit}", ok=True) else None
    full = git(LC, "rev-parse", "-q", "--verify", ref + "^{commit}", ok=True)
    if not full:
        return None, False, None
    full = full.strip()
    d = git(LC, "describe", "--tags", "--match", "b*", full, ok=True)
    if not d:
        return None, False, None
    d = d.strip()
    m = re.match(r"(b\d+)(?:-(\d+)-g[0-9a-f]+)?$", d)
    if not m:
        return None, False, None
    exact = m.group(2) is None
    date = git(LC, "log", "-1", "--format=%cd", "--date=short-local", full).strip()
    return m.group(1), exact, date

def go_archs(tag):
    s = git(OL, "ls-tree", "--name-only", tag, "model/models/", ok=True)
    if not s:
        return []
    out = []
    for line in s.splitlines():
        name = line.rsplit("/", 1)[-1]
        if name and "." not in name:
            out.append(name)
    return sorted(out)

tags = [t for t in git(OL, "tag", "--list", "v*").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
def key(t):
    return tuple(int(x) for x in t[1:].split("."))
tags.sort(key=key)

rows = []
for i, t in enumerate(tags):
    date = git(OL, "log", "-1", "--format=%cd", "--date=short-local", t).strip()
    pin, how = pin_for(t)
    build = exact = bdate = None
    if pin:
        build, exact, bdate = build_of(pin)
    rows.append({"tag": t, "date": date, "pin": pin, "pin_source": how,
                 "llama_build": build, "llama_build_exact": exact, "llama_build_date": bdate,
                 "go_engine_archs": go_archs(t)})
    if i % 25 == 0:
        print(f"[{i+1}/{len(tags)}] {t} {date} pin={pin} -> {build} exact={exact} go={len(rows[-1]['go_engine_archs'])}", file=sys.stderr)

out = {"source": "https://github.com/ollama/ollama", "count": len(rows), "tags": rows}
(ROOT / "ollama_tags.json").write_text(json.dumps(out, indent=1))
nopin = [r["tag"] for r in rows if not r["llama_build"]]
print("tags:", len(rows), "without resolvable llama.cpp build:", len(nopin), nopin[:10], "...", nopin[-5:], file=sys.stderr)
