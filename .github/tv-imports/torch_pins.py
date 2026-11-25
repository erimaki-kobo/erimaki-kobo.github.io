"""usage: python3 -I torch_pins.py pypi.json > torch_pins.json
For every torchvision release on PyPI (not yanked, x.y.z): the torch requirement in the METADATA of its Linux x86_64 wheel."""
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




P = json.load(open(sys.argv[1]))
key = lambda v: tuple(int(x) for x in v.split("."))
out = {}
for v in sorted((v for v in P["releases"] if re.fullmatch(r"\d+\.\d+\.\d+", v)), key=key):
    fs = [f for f in P["releases"][v] if f["filename"].endswith(".whl") and "linux" in f["filename"] and "x86_64" in f["filename"] and not f.get("yanked")]
    if not fs:
        continue
    f = fs[-1]
    z = zipfile.ZipFile(io.BufferedReader(Remote(f["url"]), 1 << 16))
    meta = z.read([n for n in z.namelist() if n.endswith(".dist-info/METADATA")][0]).decode()
    req = [l.split(":", 1)[1].strip() for l in meta.splitlines() if re.match(r"Requires-Dist:\s*torch\b", l)]
    out[v] = {"torch": req, "wheel": f["filename"], "date": f["upload_time"][:10]}
    print(v, req, file=sys.stderr)
json.dump(out, sys.stdout, indent=0)
