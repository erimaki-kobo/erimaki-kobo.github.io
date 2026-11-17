#!/usr/bin/env python3
"""Independent checks of comfy.json against the three repositories (reads blobs; runs no repo code).
extract_comfy.py parses the lists with ast. This file does not: it looks for the quoted name in the text
of the list statement, at the recorded commit (must be present) and at its first parent (must be absent).
It also checks every registry release: present at the commit that set the version, absent at the previous one.
"""
import json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
D = json.loads((ROOT / "comfy.json").read_text())
DIRS = {"city96": "comfy-city96", "leejet": "comfy-leejet", "chriscoletech": "comfy-chriscoletech"}
REG_REF = {"city96": "origin/stable", "chriscoletech": "origin/HEAD"}
REG_PKG = {"city96": "comfyui-gguf", "chriscoletech": "comfyui-gguf-loader"}
VAR = {"image": "IMG_ARCH_LIST", "text": "TXT_ARCH_LIST"}

def git(d, *a):
    r = subprocess.run(["git", "-C", str(ROOT / d), *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None

def listed(d, commit, kind, name):
    """True/False, or None when the commit has no list at all."""
    q = '"%s"' % name
    s = git(d, "show", "%s:loader.py" % commit)
    if s:
        m = re.search(r"^%s\s*=\s*\{(.*?)\}" % VAR[kind], s, re.S | re.M)
        if m:
            body = "\n".join(line.split("#")[0] for line in m.group(1).splitlines())
            return q in body
    for path in ("loader.py", "nodes.py"):  # the inline set of 2024
        s = git(d, "show", "%s:%s" % (commit, path)) or ""
        m = re.search(r"arch_str not in \{([^}]*)\}", s)
        if m:
            return q in m.group(1) and ((name in ("t5", "t5encoder")) == (kind == "text"))
    return None

bad, n, nreg = [], 0, 0
for L in D["loaders"]:
    if L.get("stale"):
        print("skipped (stale):", L["name"])
        continue
    d = DIRS[L["id"]]
    head = git(d, "rev-parse", "origin/main" if L["id"] == "city96" else "origin/HEAD").strip()
    if head != L["head_commit"]:
        bad.append(("head commit differs", L["id"], head))
    versions = []  # [(version, commit)] in publication order, read with grep instead of the extractor's walk
    if L["id"] in REG_REF:
        prev = None
        for c in git(d, "rev-list", "--first-parent", "--reverse", REG_REF[L["id"]]).split():
            t = git(d, "show", "%s:pyproject.toml" % c) or ""
            nm = re.search(r'^name\s*=\s*"([^"]+)"', t, re.M)
            v = re.search(r'^version\s*=\s*"([^"]+)"', t, re.M)
            if not v or not nm or nm.group(1).lower() != REG_PKG[L["id"]] or (L["id"] == "city96" and v.group(1) == "2.0.0"):
                continue
            if v.group(1) != prev:
                prev = v.group(1)
                versions.append((prev, c))
    vidx = {v: i for i, (v, _) in enumerate(versions)}
    for r in L["names"]:
        n += 1
        c = r["commit"]
        if listed(d, c, r["list"], r["name"]) is not True:
            bad.append(("absent at recorded commit", L["id"], r["list"], r["name"], c[:8]))
        parent = (git(d, "rev-parse", "-q", "--verify", c + "^1") or "").strip()
        if parent and listed(d, parent, r["list"], r["name"]) is True:
            bad.append(("already present at the parent", L["id"], r["list"], r["name"], parent[:8]))
        if listed(d, head, r["list"], r["name"]) is not True:
            bad.append(("absent at head", L["id"], r["list"], r["name"]))
        if r.get("registry_version"):
            nreg += 1
            i = vidx.get(r["registry_version"])
            if i is None:
                bad.append(("unknown registry version", L["id"], r["name"], r["registry_version"]))
                continue
            if listed(d, versions[i][1], r["list"], r["name"]) is not True:
                bad.append(("absent at registry release", L["id"], r["name"], r["registry_version"]))
            if i > 0 and listed(d, versions[i - 1][1], r["list"], r["name"]) is True:
                bad.append(("already in the previous registry release", L["id"], r["name"], versions[i - 1][0]))
        elif versions and listed(d, versions[-1][1], r["list"], r["name"]) is True:
            bad.append(("in the latest registry release but no version recorded", L["id"], r["name"]))
    if versions and (L["registry_latest"] or {}).get("version") != versions[-1][0]:
        bad.append(("latest registry version differs", L["id"], versions[-1][0]))
print("ComfyUI-GGUF checks: %d names, %d registry releases, problems: %d" % (n, nreg, len(bad)))
for b in bad:
    print("PROBLEM", b)
print("ALL PASS" if not bad else "FAIL")
sys.exit(1 if bad else 0)
