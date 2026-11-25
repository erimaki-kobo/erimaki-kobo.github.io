#!/usr/bin/env python3
"""Make a local git repository of the Python files a PyPI wheel installs, one commit and tag per release (from
../triton-imports, generalized).

usage: python3 -I wheel_repo.py pypi.json <package dir, e.g. llama_index/core> <min version> <below version or -> out.git > wheels.json
llama-index-core's git tags do not always match the published wheels (v0.10.0's tag exports Settings, the 0.10.0
wheel does not), so the package is read from the wheels. For the first release of each minor version in the range,
and the newest, the <package dir>/**/*.py of the py3-none-any wheel (or a Linux x86_64 CPython wheel) are fetched with
HTTP range requests and committed under that path, tagged v<version>. The wheel's file name and sha256 are recorded.
"""
import io, json, os, re, subprocess, sys, tempfile, urllib.request, zipfile

PYPI, PKG, MIN, BELOW, OUT = json.load(open(sys.argv[1])), sys.argv[2].strip("/"), sys.argv[3], sys.argv[4], sys.argv[5]
key = lambda v: tuple(int(x) for x in v.split("."))


class Remote(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        self.size = int(urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60).headers["Content-Length"])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def readinto(self, buf):
        if not len(buf) or self.pos >= self.size:
            return 0
        end = min(self.size, self.pos + len(buf)) - 1
        b = urllib.request.urlopen(urllib.request.Request(self.url, headers={"Range": "bytes=%d-%d" % (self.pos, end)}), timeout=120).read()
        buf[:len(b)] = b
        self.pos += len(b)
        return len(b)


def pick(files):
    for f in files:
        if f["filename"].endswith("-py3-none-any.whl") and not f.get("yanked"):
            return f
    for py in ("cp312", "cp311", "cp310"):
        for f in files:
            n = f["filename"]
            if n.endswith(".whl") and "-%s-" % py in n and "x86_64" in n and "manylinux" in n and not f.get("yanked"):
                return f
    for f in files:   # old releases: the newest CPython wheel for Linux x86_64 (no cp310 wheels before torchvision 0.11)
        n = f["filename"]
        if n.endswith(".whl") and "linux" in n and "x86_64" in n and not f.get("yanked"):
            return f
    return None


vs = sorted((v for v in PYPI["releases"] if re.fullmatch(r"\d+\.\d+\.\d+", v) and key(v) >= key(MIN) and (BELOW == "-" or key(v) < key(BELOW)) and pick(PYPI["releases"][v])), key=key)
first = {}
for v in vs:
    first.setdefault(key(v)[:2], v)
sel = vs if os.environ.get("EVERY") else sorted(set(first.values()) | {vs[-1]}, key=key)   # EVERY=1: every release
work = tempfile.mkdtemp()
git = lambda *a: subprocess.run(["git", "-C", work, *a], check=True, capture_output=True)
git("init", "-q")
info = {}
for v in sel:
    f = pick(PYPI["releases"][v])
    z = zipfile.ZipFile(io.BufferedReader(Remote(f["url"]), 1 << 20))
    subprocess.run(["git", "-C", work, "rm", "-rq", "--ignore-unmatch", PKG.split("/")[0]], check=True)
    py = [n for n in z.namelist() if n.startswith(PKG + "/") and n.endswith(".py")]
    for n in py:
        p = os.path.join(work, n)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(z.read(n))
    git("add", "-A")
    git("-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "%s %s from %s" % (PKG, v, f["filename"]), "--allow-empty")
    git("tag", "v" + v)
    info[v] = {"wheel": f["filename"], "sha256": f["digests"]["sha256"], "py_files": len(py)}
    print(v, len(py), f["filename"], file=sys.stderr)
subprocess.run(["git", "clone", "-q", "--bare", work, OUT], check=True)
json.dump(info, sys.stdout, indent=0)
