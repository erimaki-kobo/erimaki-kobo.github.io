#!/usr/bin/env python3
"""Check the page's key gradio facts against the PyPI wheels, a source independent of the git tags and of names_hist.py.

usage: python3 -I anchors.py pypi.json out/gradio.json > anchors.json
For each fact (name, release where it must be present, release where it must be absent) the wheel of each release is
opened with HTTP range requests and the name is looked for as plain text: a module file gradio/<name>.py or
gradio/<name>/__init__.py, or the word in gradio/__init__.py (gradio/components/__init__.py for gradio.components).
The same facts are then read from out/gradio.json; both must agree.
"""
import io, json, re, sys, urllib.request, zipfile

PYPI, D = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
FACTS = [  # (module, name, a release that has it, the nearest release without it: the first after a removal, or the last patch before an addition)
    ("", "inputs", "3.50.2", "4.0.0"), ("", "outputs", "3.50.2", "4.0.0"), ("", "Box", "3.50.2", "4.0.0"),
    ("", "Interpretation", "3.50.2", "4.0.0"), ("components", "IOComponent", "3.50.2", "4.0.0"),
    ("", "make_waveform", "4.44.1", "5.0.0"), ("", "HuggingFaceDatasetSaver", "4.44.1", "5.0.0"),
    ("", "ChatInterface", "3.37.0", "3.36.1"), ("", "http_server", "4.23.0", "4.22.0"),
    ("", "ChatMessage", "4.38.0", "4.37.2"), ("", "Sidebar", "5.14.0", "5.13.2"),
]


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


_z = {}
def wheel(v):
    if v not in _z:
        f = [f for f in PYPI["releases"][v] if f["filename"].endswith(".whl")][0]
        _z[v] = zipfile.ZipFile(io.BufferedReader(Remote(f["url"]), 1 << 20))
    return _z[v]


def in_wheel(mod, name, v):
    z = wheel(v)
    files = set(z.namelist())
    base = "gradio/" + (mod.replace(".", "/") + "/" if mod else "")
    if base + name + ".py" in files or base + name + "/__init__.py" in files:
        return True
    src = z.read(base + "__init__.py").decode("utf-8", "replace")
    src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    return re.search(r"\b%s\b" % re.escape(name), src) is not None


R = [r[0] for r in D["releases"]]
key = lambda v: tuple(map(int, v.split(".")))


def data_has(mod, name, v):
    i = max(j for j, r in enumerate(R) if key(r) <= key(v))       # the release read for v's minor version
    rg = D["ranges"][D["names"][mod][name]] if name in D["names"].get(mod, {}) else []
    return any(a <= i and (b == 0 or i < b) for a, b in zip(rg[::2], rg[1::2]))


out = []
for mod, name, has, other in FACTS:
    for v, want in ((has, True), (other, False)):
        w, d = in_wheel(mod, name, v), data_has(mod, name, v)
        out.append({"module": mod, "name": name, "release": v, "expected": want, "wheel": w, "data": d})
        assert w == want and d == want, out[-1]
print("anchors: %d facts, %d release checks, wheel and data agree" % (len(FACTS), len(out)), file=sys.stderr)
json.dump(out, sys.stdout, indent=0)
