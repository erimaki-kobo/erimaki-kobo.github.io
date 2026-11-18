#!/usr/bin/env python3
"""Shared: pick the release tags and load every .py blob under src/diffusers at those tags.
tags(): first non-yanked PyPI release of every minor, plus the newest release.  load(): {tag: {path: sha}}, {sha: text}
"""
import json, os, re, subprocess, sys

def git(repo, *a, inp=None, binary=False):
    p = subprocess.run(["git", "-C", repo, *a], capture_output=True, check=True, input=inp)
    return p.stdout if binary else p.stdout.decode()

ver = lambda t: tuple(int(x) for x in t.split("==")[-1].lstrip("v").split("."))

def tags(repo, pypi, every=False):
    """every=True: read every release, not only the first of each minor (timm puts real changes in 1.0.x patches)"""
    # TAG_PREFIX: monorepos tag "langchain==1.2.3"; TAG_MIN / TAG_BELOW bound the versions read (e.g. 0.1.0 <= v < 1.0.0)
    pre = os.environ.get("TAG_PREFIX", "")
    lo, hi = os.environ.get("TAG_MIN"), os.environ.get("TAG_BELOW")
    vv = lambda t: t[len(pre):].lstrip("v")
    finals = sorted((t for t in git(repo, "tag").split() if t.startswith(pre) and re.fullmatch(r"v?\d+\.\d+\.\d+", t[len(pre):])
                     and vv(t) in pypi["dates"] and vv(t) not in pypi["yanked"]
                     and (not lo or ver(vv(t)) >= ver(lo)) and (not hi or ver(vv(t)) < ver(hi))), key=lambda t: ver(vv(t)))
    if every:
        return finals, finals
    first = {}
    for t in finals:
        first.setdefault(ver(t)[:2], t)
    return sorted(set(first.values()) | {finals[-1]}, key=ver), finals

def load(repo, tg, root="src/diffusers"):
    want = {}
    for t in tg:
        ls = {}
        for l in git(repo, "ls-tree", "-r", t, "--", root).splitlines():
            meta, path = l.split("\t")
            if path.endswith(".py"):
                ls[path[len(root) + 1:]] = meta.split()[2]
        assert "__init__.py" in ls, t
        want[t] = ls
    shas = sorted({s for t in tg for s in want[t].values()})
    have = set(git(repo, "cat-file", "--batch-check=%(objectname)", "--batch-all-objects").split())
    need = [s for s in shas if s not in have]
    for i in range(0, len(need), 4000):
        subprocess.run(["git", "-C", repo, "-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "origin", "--no-tags", "--no-write-fetch-head",
                        "--recurse-submodules=no", "--filter=blob:none", "--stdin"], input=("\n".join(need[i:i + 4000]) + "\n").encode(), check=True)
    buf = git(repo, "cat-file", "--batch", inp=("\n".join(shas) + "\n").encode(), binary=True)
    text, i = {}, 0
    for s in shas:
        nl = buf.index(b"\n", i)
        sha, typ, size = buf[i:nl].split()
        assert sha.decode() == s and typ == b"blob"
        text[s] = buf[nl + 1:nl + 1 + int(size)].decode("utf-8", "replace")
        i = nl + 1 + int(size) + 1
    return want, text
