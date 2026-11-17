#!/usr/bin/env python3
"""First llama.cpp build whose converter registers each given HF class (bisect over build tags).

Usage: python3 -I converter_first.py <llama.cpp clone> <work dir> <lo build> <hi build> Class [Class ...]
  lo: a build known not to have the classes (the build of the previous data.json), hi: a build that has them.
The clone can be `git clone --depth 1 --filter=blob:none`; each probed tag is fetched with --depth 1.
Prints JSON {class: [build number, UTC date of the tag's commit]}.
"""
import json, re, subprocess, sys, tarfile, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_map import gguf_map

repo, work, lo, hi = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3].lstrip("b")), int(sys.argv[4].lstrip("b"))
want = sys.argv[5:]


def git(*a, **k):
    return subprocess.run(["git", "-C", repo] + list(a), capture_output=True, check=True, **k).stdout


refs = git("ls-remote", "--tags", "origin").decode().split("\n")
builds = sorted(int(m.group(1)) for m in (re.search(r"refs/tags/b(\d+)$", r) for r in refs) if m and lo <= int(m.group(1)) <= hi)
assert builds[0] == lo and builds[-1] == hi, (builds[:2], builds[-2:])
cache = {}


def classes_at(b):
    if b not in cache:
        d = work / ("conv_b%d" % b)
        if not (d / "conversion").exists():
            git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", "tag", "b%d" % b)
            d.mkdir(parents=True, exist_ok=True)
            tarfile.open(fileobj=io.BytesIO(git("archive", "b%d" % b, "conversion", "convert_hf_to_gguf.py", "gguf-py/gguf/constants.py"))).extractall(d, filter="data")
        cache[b] = set(gguf_map(d))
    return cache[b]


out = {}
for c in want:
    assert c not in classes_at(lo) and c in classes_at(hi), c
    a, z = 0, len(builds) - 1                       # builds[a] lacks c, builds[z] has it
    while z - a > 1:
        m = (a + z) // 2
        if c in classes_at(builds[m]):
            z = m
        else:
            a = m
    b = builds[z]
    date = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%cd", "--date=format-local:%Y-%m-%d", "b%d" % b],
                          capture_output=True, text=True, check=True, env={"TZ": "UTC", "PATH": "/usr/bin:/bin"}).stdout.strip()
    out[c] = [str(b), date, "previous build b%d" % builds[a]]
print(json.dumps(out, indent=1))
