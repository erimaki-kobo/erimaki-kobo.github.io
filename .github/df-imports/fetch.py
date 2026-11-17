#!/usr/bin/env python3
"""Shared: pick the release tags and load every .py blob under src/diffusers at those tags.
tags(): first non-yanked PyPI release of every minor, plus the newest release.  load(): {tag: {path: sha}}, {sha: text}
"""
import json, re, subprocess, sys

def git(repo, *a, inp=None, binary=False):
    p = subprocess.run(["git", "-C", repo, *a], capture_output=True, check=True, input=inp)
    return p.stdout if binary else p.stdout.decode()

ver = lambda t: tuple(int(x) for x in t.lstrip("v").split("."))

def tags(repo, pypi):
    finals = sorted((t for t in git(repo, "tag").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)
                     and t[1:] in pypi["dates"] and t[1:] not in pypi["yanked"]), key=ver)
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
