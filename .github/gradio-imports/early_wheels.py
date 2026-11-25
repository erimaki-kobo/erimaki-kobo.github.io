#!/usr/bin/env python3
"""Top-level names of gradio releases older than the first gradio@X.Y.Z git tag (3.41.0), read from the PyPI wheels.

usage: python3 -I early_wheels.py pypi.json 3.41.0 > early.json
Only the zip directory and gradio/__init__.py of each wheel are fetched (HTTP range requests), for the first release of
every minor from 3.0 up to the given version. A top-level name is what `from gradio import X` can resolve: names bound in
gradio/__init__.py (import, def, class, assignment) and the submodules and subpackages in the wheel (gradio/<x>.py,
gradio/<x>/__init__.py). Code under `if TYPE_CHECKING:` is skipped; try/except bodies count (both branches bind).
"""
import ast, io, json, re, sys, urllib.request, zipfile

PYPI, BELOW = json.load(open(sys.argv[1])), sys.argv[2]
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

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.size, self.pos + n) - 1
        r = urllib.request.urlopen(urllib.request.Request(self.url, headers={"Range": "bytes=%d-%d" % (self.pos, end)}), timeout=120)
        b = r.read()
        self.pos += len(b)
        return b

    def readinto(self, buf):
        b = self.read(len(buf)); buf[:len(b)] = b; return len(b)


def bound(src):
    names = set()

    def walk(body):
        for n in body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    if a.name != "*":
                        names.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(n.name)
            elif isinstance(n, (ast.Assign, ast.AnnAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name):
                            names.add(x.id)
            elif isinstance(n, ast.If):
                if "TYPE_CHECKING" not in ast.dump(n.test):
                    walk(n.body)
                walk(n.orelse)
            elif isinstance(n, ast.Try):
                walk(n.body)
                for h in n.handlers:
                    walk(h.body)
                walk(n.orelse); walk(n.finalbody)
    walk(ast.parse(src).body)
    return names


vs = sorted((v for v in PYPI["releases"] if re.fullmatch(r"\d+\.\d+\.\d+", v) and (3, 0, 0) <= key(v) < key(BELOW)
             and any(f["filename"].endswith(".whl") and not f.get("yanked") for f in PYPI["releases"][v])), key=key)
first = {}
for v in vs:
    first.setdefault(key(v)[:2], v)
out = {}
for v in sorted(first.values(), key=key):
    f = [f for f in PYPI["releases"][v] if f["filename"].endswith(".whl")][0]
    z = zipfile.ZipFile(io.BufferedReader(Remote(f["url"]), 1 << 16))
    files = z.namelist()
    subs = set()
    for p in files:
        m = re.fullmatch(r"gradio/([A-Za-z_][A-Za-z0-9_]*)(\.py|/__init__\.py)", p)
        if m:
            subs.add(m.group(1))
    names = bound(z.read("gradio/__init__.py").decode("utf-8", "replace")) | subs
    out[v] = {"date": f["upload_time"][:10], "sha256": f["digests"]["sha256"], "names": sorted(names)}
    print(v, len(names), file=sys.stderr)
json.dump(out, sys.stdout, indent=0)
