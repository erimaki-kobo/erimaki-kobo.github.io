#!/usr/bin/env python3
"""Find, for every GGUF `general.architecture` string known to llama.cpp,
the commit that first added it to LLM_ARCH_NAMES and the first bNNNN release tag
containing that commit.

Phase 1: parse `git log -p --follow -- src/llama-arch.cpp` (arch_log.txt).
Phase 2: archs already present in the first llama-arch.cpp commit are traced
back through src/llama.cpp / llama.cpp with a memoized binary search over the
commit list (blobless clone: each probe fetches one blob).

Output: llama_archs.json
"""
import json, re, subprocess, sys, functools, bisect
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "llama.cpp"
PAT = re.compile(r'LLM_ARCH_([A-Z0-9_]+),\s*"([^"]+)"')

def git(*a, text=True):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=text, check=True).stdout

# ---------- phase 1: llama-arch.cpp history (oldest first) ----------
commits = []  # (hash, date, subject, added_names)
cur = None
for line in (ROOT / "arch_log.txt").read_text(errors="replace").splitlines():
    if line.startswith("COMMIT\t"):
        _, h, d, s = line.split("\t", 3)
        cur = {"hash": h, "date": d, "subject": s, "added": [], "removed": []}
        commits.append(cur)
    elif cur is not None and line.startswith("+") and not line.startswith("+++"):
        for m in PAT.finditer(line):
            cur["added"].append((m.group(1), m.group(2)))
    elif cur is not None and line.startswith("-") and not line.startswith("---"):
        for m in PAT.finditer(line):
            cur["removed"].append((m.group(1), m.group(2)))
commits.reverse()  # oldest first
first_commit = commits[0]
print("llama-arch.cpp commits:", len(commits), "first:", first_commit["hash"][:9], first_commit["date"], file=sys.stderr)

# current arch set (HEAD) — the authority on what exists today
head_src = git("show", "HEAD:src/llama-arch.cpp")
head_archs = {name: enum for enum, name in PAT.findall(head_src)}
print("archs at HEAD:", len(head_archs), file=sys.stderr)

intro = {}  # name -> dict(commit, date, subject, via)
for c in commits:
    for enum, name in c["added"]:
        if name not in intro:
            intro[name] = {"enum": enum, "commit": c["hash"], "date": c["date"], "subject": c["subject"]}

# ---------- phase 2: archs that predate src/llama-arch.cpp ----------
old_names = [n for n in head_archs if intro.get(n, {}).get("commit") == first_commit["hash"]]
print("archs predating llama-arch.cpp:", len(old_names), file=sys.stderr)

# commit list of the predecessor files, oldest first, with the path valid at each commit
hist = git("log", "--reverse", "--date=short", "--format=%H%x09%ad%x09%s", "--name-only", "--", "src/llama.cpp", "llama.cpp").splitlines()
old_commits = []  # (hash, date, subject, path)
i = 0
while i < len(hist):
    if "\t" in hist[i]:
        h, d, s = hist[i].split("\t", 2)
        j = i + 1
        path = None
        while j < len(hist) and "\t" not in hist[j]:
            if hist[j].strip() in ("src/llama.cpp", "llama.cpp") and path is None:
                path = hist[j].strip()
            j += 1
        if path:
            old_commits.append((h, d, s, path))
        i = j
    else:
        i += 1
print("predecessor commits:", len(old_commits), file=sys.stderr)

@functools.lru_cache(maxsize=None)
def archs_at(idx):
    h, d, s, path = old_commits[idx]
    try:
        src = git("show", f"{h}:{path}")
    except subprocess.CalledProcessError:
        return frozenset()
    return frozenset(name for _, name in PAT.findall(src))

# after the 2025-01-03 refactor the table no longer lives in src/llama.cpp: trim trailing empty states
LAST = len(old_commits) - 1
while LAST > 0 and not archs_at(LAST):
    LAST -= 1
print("last predecessor commit with LLM_ARCH_NAMES:", old_commits[LAST][:2], "archs:", len(archs_at(LAST)), file=sys.stderr)

def first_index_with(name):
    lo, hi = 0, LAST
    if name not in archs_at(hi):
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if name in archs_at(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo

for n, name in enumerate(old_names):
    idx = first_index_with(name)
    if idx is None:
        intro[name]["note"] = "not found in predecessor history; kept llama-arch.cpp first commit"
        continue
    h, d, s, path = old_commits[idx]
    intro[name].update({"commit": h, "date": d, "subject": s, "via": path})
    print(f"[{n+1}/{len(old_names)}] {name}: {h[:9]} {d} {s[:60]}", file=sys.stderr)
print("blobs fetched:", archs_at.cache_info().misses, file=sys.stderr)

# ---------- first release tag containing the commit ----------
def first_tag(commit):
    try:
        out = git("describe", "--contains", "--match", "b*", commit).strip()
    except subprocess.CalledProcessError:
        return None
    # forms: b1234, b1234~3, b1234^2~1
    m = re.match(r"(b\d+)", out)
    return m.group(1) if m else None

tag_date_cache = {}
def tag_date(tag):
    if tag not in tag_date_cache:
        tag_date_cache[tag] = git("log", "-1", "--format=%ad", "--date=short", tag).strip()
    return tag_date_cache[tag]

rows = []
for name, enum in sorted(head_archs.items(), key=lambda kv: kv[0]):
    info = intro.get(name)
    if not info:
        rows.append({"arch": name, "enum": enum, "error": "no intro found"})
        continue
    tag = first_tag(info["commit"])
    row = {"arch": name, "enum": enum, "commit": info["commit"], "commit_date": info["date"],
           "subject": info["subject"], "first_tag": tag, "tag_date": tag_date(tag) if tag else None}
    if "note" in info:
        row["note"] = info["note"]
    rows.append(row)

head = git("rev-parse", "HEAD").strip()
head_tag = first_tag(head) or git("describe", "--tags", "--abbrev=0", "--match", "b*", head).strip()  # latest tag at or before HEAD
out = {"source": "https://github.com/ggml-org/llama.cpp", "file": "src/llama-arch.cpp (LLM_ARCH_NAMES)",
       "head": head, "head_tag": head_tag, "head_date": git("log", "-1", "--format=%ad", "--date=short").strip(),
       "count": len(rows), "archs": rows}
(ROOT / "llama_archs.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
missing = [r["arch"] for r in rows if not r.get("first_tag")]
print("rows:", len(rows), "without tag:", missing, file=sys.stderr)
