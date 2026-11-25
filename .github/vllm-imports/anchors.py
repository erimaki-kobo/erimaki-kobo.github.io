#!/usr/bin/env python3
"""Check the page's key vLLM facts against the PyPI wheels, a source independent of the git tags and of names_hist.py.

usage: python3 -I anchors.py pypi.json out/vllm.json > anchors.json
For each fact (name, release where it must be present, release where it must be absent) the wheel of each release is
opened with HTTP range requests and the name is looked for as plain text: a submodule file vllm/<module path>/<name>.py or
vllm/<module path>/<name>/__init__.py, or the word in the module's own file (vllm/<module path>.py or its __init__.py).
The same facts are then read from out/vllm.json; both must agree.
"""
import io, json, re, sys, urllib.request, zipfile

PYPI, D = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
FACTS = [  # (module, name, a release that has it, the nearest release without it)
    ("sampling_params", "GuidedDecodingParams", "0.11.2", "0.12.0"), ("sampling_params", "StructuredOutputsParams", "0.11.0", "0.10.2"),
    ("utils", "get_open_port", "0.13.0", "0.14.0"), ("utils.network_utils", "get_open_port", "0.12.0", "0.11.0"),
    ("utils", "FlexibleArgumentParser", "0.11.0", "0.12.0"), ("entrypoints.openai", "protocol", "0.14.1", "0.15.0"),
    ("entrypoints.openai.chat_completion.protocol", "ChatCompletionRequest", "0.15.0", "0.14.1"),
    ("worker", "worker", "0.10.2", "0.11.0"), ("model_executor", "guided_decoding", "0.10.0", "0.11.0"),
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
    base = "vllm/" + mod.replace(".", "/")
    if base + "/" + name + ".py" in files or base + "/" + name + "/__init__.py" in files:
        return True
    own = base + ".py" if base + ".py" in files else base + "/__init__.py"
    if own not in files:
        return False
    src = z.read(own).decode("utf-8", "replace")
    src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    return re.search(r"^(?:class|def)\s+%s\b|^%s\s*=|^\s*from\s+\S+\s+import\s+[^\n]*\b%s\b|^\s+%s,?$|^\s+[\x27\x22]%s[\x27\x22]:" % ((re.escape(name),) * 5), src, re.M) is not None


R = [r[0] for r in D["releases"]]
key = lambda v: tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def data_has(mod, name, v):
    i = max(j for j, r in enumerate(R) if key(r) <= key(v))       # the release read for v's minor version
    if name in D["names"].get(mod, {}):
        rg = D["ranges"][D["names"][mod][name]]
    elif (mod + "." + name) in D["mods"]:
        rg = D["ranges"][D["mods"][mod + "." + name]]
    else:
        rg = []
    return any(a <= i and (b == 0 or i < b) for a, b in zip(rg[::2], rg[1::2]))


out = []
for mod, name, has, other in FACTS:
    for v, want in ((has, True), (other, False)):
        w, d = in_wheel(mod, name, v), data_has(mod, name, v)
        out.append({"module": mod, "name": name, "release": v, "expected": want, "wheel": w, "data": d})
        assert w == want and d == want, out[-1]
print("anchors: %d facts, %d release checks, wheel and data agree" % (len(FACTS), len(out)), file=sys.stderr)
json.dump(out, sys.stdout, indent=0)
