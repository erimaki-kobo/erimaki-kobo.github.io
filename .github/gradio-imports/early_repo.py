#!/usr/bin/env python3
"""Make a local git repository of the gradio package files of releases older than the first gradio@X.Y.Z tag (3.41.0),
from the PyPI wheels, so names_hist.py can read them like the real tags.

usage: python3 -I early_repo.py pypi.json 3.41.0 early.git > early_wheels.json
For the first release of every minor from 3.0 below the given version, every gradio/**/*.py in the wheel is fetched with
HTTP range requests (the wheel itself is not downloaded), committed, and tagged gradio@<version>. The wheel's sha256 from
PyPI is recorded; the zip's own CRC check runs on every file read.
"""
import io, json, os, re, subprocess, sys, tempfile, urllib.request, zipfile

PYPI, BELOW, OUT = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
key = lambda v: tuple(int(x) for x in v.split("."))


class Remote(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        r = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60)
        self.size = int(r.headers["Content-Length"])

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def readinto(self, buf):
        n = len(buf)
        if n == 0 or self.pos >= self.size:
            return 0
        end = min(self.size, self.pos + n) - 1
        req = urllib.request.Request(self.url, headers={"Range": "bytes=%d-%d" % (self.pos, end)})
        b = urllib.request.urlopen(req, timeout=120).read()
        buf[:len(b)] = b
        self.pos += len(b)
        return len(b)


def git(*a, **kw):
    return subprocess.run(["git", "-C", work, *a], check=True, capture_output=True, **kw).stdout.decode()


vs = sorted((v for v in PYPI["releases"] if re.fullmatch(r"\d+\.\d+\.\d+", v) and (3, 0, 0) <= key(v) < key(BELOW)
             and any(f["filename"].endswith(".whl") and not f.get("yanked") for f in PYPI["releases"][v])), key=key)
first = {}
for v in vs:
    first.setdefault(key(v)[:2], v)
work = tempfile.mkdtemp()
git("init", "-q")
info = {}
for v in sorted(first.values(), key=key):
    f = [f for f in PYPI["releases"][v] if f["filename"].endswith(".whl")][0]
    z = zipfile.ZipFile(io.BufferedReader(Remote(f["url"]), 1 << 20))
    subprocess.run(["git", "-C", work, "rm", "-rq", "--ignore-unmatch", "gradio"], check=True)
    py = [n for n in z.namelist() if n.startswith("gradio/") and n.endswith(".py")]
    for n in py:
        p = os.path.join(work, n)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(z.read(n))
    git("add", "-A")
    git("-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "gradio " + v + " from " + f["filename"], "--allow-empty")
    git("tag", "gradio@" + v)
    info[v] = {"wheel": f["filename"], "sha256": f["digests"]["sha256"], "py_files": len(py)}
    print(v, len(py), file=sys.stderr)
subprocess.run(["git", "clone", "-q", "--bare", work, OUT], check=True)
json.dump(info, sys.stdout, indent=0)
