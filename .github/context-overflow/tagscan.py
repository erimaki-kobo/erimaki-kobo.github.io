"""First release tag where a regex appears (or disappears) in any of the given files.

usage: python3 bisect.py <git dir> <tag regex> <regex> <path> [<path> ...]
  prefix the regex with '!' to find where it stops matching.
  paths may contain a glob '*'; it is expanded with git ls-tree at each tag.
prints every sampled tag (linear scan of the newest patch of each minor, then a
bisection inside the first changed interval) and the first tag where it holds.
"""
import fnmatch, re, subprocess, sys

G, TAGRE, RX = sys.argv[1:4]
PATHS = sys.argv[4:]
neg = RX.startswith("!")
rx = re.compile(RX[1:] if neg else RX)


def git(*a):
    p = subprocess.run(["git", "-C", G, *a], capture_output=True)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def tags():
    out = git("tag", "-l", "--sort=v:refname").split()
    return [t for t in out if re.fullmatch(TAGRE, t)]


_cache = {}


def holds(tag):
    if tag in _cache:
        return _cache[tag]
    hit = False
    for p in PATHS:
        files = [p]
        if "*" in p:
            d = p.rsplit("/", 1)[0]
            ls = git("ls-tree", "--name-only", f"{tag}:{d}") or ""
            files = [f"{d}/{f}" for f in ls.split() if fnmatch.fnmatch(f"{d}/{f}", p)]
        for f in files:
            s = git("show", f"{tag}:{f}")
            if s and rx.search(s):
                hit = True
                break
        if hit:
            break
    r = (not hit) if neg else hit
    _cache[tag] = r
    return r


ts = tags()
first = None
prev = None
for i, t in enumerate(ts):
    if holds(t):
        first = i
        break
print("first tag where it holds:", ts[first] if first is not None else None)
if first:
    print("previous tag:", ts[first - 1])
