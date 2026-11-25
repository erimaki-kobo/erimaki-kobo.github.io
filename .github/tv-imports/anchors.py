"""usage: python3 -I anchors.py pypi.json out/torchvision.json > anchors.json
Checks the facts the page names by plain-text search in the PyPI wheels (read by HTTP range requests), then compares
with the data. Written by hand from the release notes, not from the data."""
import io, json, re, sys, urllib.request, zipfile
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




P, D = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
R, T = D["releases"], D["ranges"]
key = lambda v: tuple(int(x) for x in v.split("."))


def wheel(v):
    fs = [f for f in P["releases"][v] if f["filename"].endswith(".whl") and "linux" in f["filename"] and "x86_64" in f["filename"]]
    return zipfile.ZipFile(io.BufferedReader(Remote(fs[-1]["url"]), 1 << 16))


def has(m, n, v):   # in the data
    i = [k for k, r in enumerate(R) if r[0] == v][0]
    ri = D["mods"].get(m) if n is None else D["names"].get(m, {}).get(n)
    if ri is None:
        return False
    r = T[ri]
    return any(a <= i and (not b or i < b) for a, b in zip(r[::2], r[1::2]))


# (module, name or None for the module, file in the wheel, text that must be there or None for "the file exists", release, expected)
FACTS = [
    ("transforms.functional_tensor", None, "torchvision/transforms/functional_tensor.py", None, "0.16.0", True),
    ("transforms.functional_tensor", None, "torchvision/transforms/functional_tensor.py", None, "0.17.0", False),
    ("models.utils", "load_state_dict_from_url", "torchvision/models/utils.py", "load_state_dict_from_url", "0.10.0", True),
    ("models.utils", "load_state_dict_from_url", "torchvision/models/utils.py", "load_state_dict_from_url", "0.11.1", False),
    ("io", "read_video", "torchvision/io/__init__.py", "from .video import read_video", "0.25.0", True),
    ("io", "read_video", "torchvision/io/__init__.py", "from .video import read_video", "0.26.0", False),
    ("io", "VideoReader", "torchvision/io/__init__.py", "from .video_reader import VideoReader", "0.25.0", True),
    ("io.video", None, "torchvision/io/video.py", "from pytorch.vision.fb.io.video import", "0.28.0", False),   # the file is there but its import fails
    ("datapoints", None, "torchvision/datapoints/__init__.py", None, "0.15.1", True),
    ("datapoints", None, "torchvision/datapoints/__init__.py", None, "0.16.0", False),
    ("tv_tensors", None, "torchvision/tv_tensors/__init__.py", None, "0.16.0", True),
    ("models", "ResNet50_Weights", "torchvision/models/resnet.py", "class ResNet50_Weights", "0.12.0", False),
    ("models", "ResNet50_Weights", "torchvision/models/resnet.py", "class ResNet50_Weights", "0.13.0", True),
    ("transforms.v2", None, "torchvision/transforms/v2/__init__.py", None, "0.14.0", False),
    ("transforms.v2", None, "torchvision/transforms/v2/__init__.py", None, "0.15.1", True),
    ("transforms.functional", "rgb_to_grayscale", "torchvision/transforms/functional.py", "def rgb_to_grayscale", "0.7.0", False),
    ("transforms.functional", "rgb_to_grayscale", "torchvision/transforms/functional.py", "def rgb_to_grayscale", "0.8.0", True),
    ("transforms", "Scale", "torchvision/transforms/transforms.py", "class Scale", "0.11.1", True),
    ("transforms", "Scale", "torchvision/transforms/transforms.py", "class Scale", "0.12.0", False),
]
out, cache = [], {}
for m, n, path, text, v, want in FACTS:
    z = cache.setdefault(v, wheel(v))
    names = set(z.namelist())
    if text is None:
        w = path in names
    elif m == "io.video":
        w = not (path in names and text in z.read(path).decode())
    else:
        w = path in names and text in z.read(path).decode()
    d = has(m, n, v)
    out.append({"module": m, "name": n, "release": v, "expected": want, "wheel": w, "data": d})
    print(m, n, v, want, w, d, file=sys.stderr)
    assert want == w == d, out[-1]
json.dump(out, sys.stdout, indent=0)
