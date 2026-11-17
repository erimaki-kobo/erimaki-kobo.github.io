#!/usr/bin/env python3
"""Read which libcudart a vLLM wheel loads, without downloading the wheel.
usage: python3 -I wheel_peek.py WHEEL_URL [WHEEL_URL ...]
Opens the wheel (a zip) over HTTP range requests, reads the smallest shared objects until one names
libcudart.so.N in its ELF DT_NEEDED entries, and prints one JSON line per wheel:
{"url", "size", "soname", "from" (member read), "bytes_fetched", "requires_dist_torch", "requires_python"}.
Nothing in the wheel is executed."""
import io, json, re, struct, sys, urllib.request, zipfile


class HttpFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos, self.fetched = url, 0, 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req) as r:
            self.size = int(r.headers["Content-Length"])
            self.final = r.geturl()
        self.cache = {}
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def read(self, n=-1):
        if n < 0: n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0: return b""
        out = b""
        CH = 1 << 16
        first, last = self.pos // CH, (self.pos + n - 1) // CH
        missing = [c for c in range(first, last + 1) if c not in self.cache]
        if missing:
            a, b = missing[0] * CH, min((missing[-1] + 1) * CH, self.size) - 1
            req = urllib.request.Request(self.final, headers={"Range": "bytes=%d-%d" % (a, b)})
            with urllib.request.urlopen(req) as r:
                data = r.read()
            self.fetched += len(data)
            for i, c in enumerate(range(missing[0], missing[-1] + 1)):
                self.cache[c] = data[i * CH:(i + 1) * CH]
        buf = b"".join(self.cache[c] for c in range(first, last + 1))
        s = self.pos - first * CH
        out = buf[s:s + n]
        self.pos += len(out)
        return out
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)


def dt_needed(elf):
    """DT_NEEDED names of a 64-bit little-endian ELF (parsed from the section headers)."""
    if elf[:4] != b"\x7fELF" or elf[4] != 2 or elf[5] != 1:
        return None
    shoff, = struct.unpack_from("<Q", elf, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", elf, 0x3A)
    secs = [struct.unpack_from("<IIQQQQIIQQ", elf, shoff + i * shentsize) for i in range(shnum)]
    out = []
    for name, typ, flags, addr, off, size, link, info, align, entsize in secs:
        if typ != 6:  # SHT_DYNAMIC
            continue
        stroff = secs[link][4]
        for i in range(0, size, 16):
            tag, val = struct.unpack_from("<qQ", elf, off + i)
            if tag == 0: break
            if tag == 1:  # DT_NEEDED
                end = elf.index(b"\0", stroff + val)
                out.append(elf[stroff + val:end].decode())
    return out


for url in sys.argv[1:]:
    f = HttpFile(url)
    z = zipfile.ZipFile(io.BufferedReader(f, buffer_size=1 << 16))
    res = {"url": url, "size": f.size, "soname": None, "from": None}
    meta = [n for n in z.namelist() if n.endswith(".dist-info/METADATA")]
    if meta:
        m = z.read(meta[0]).decode("utf-8", "replace")
        res["requires_dist_torch"] = [l.split(":", 1)[1].strip() for l in m.splitlines() if re.match(r"Requires-Dist: torch\b", l)]
        res["requires_python"] = next((l.split(":", 1)[1].strip() for l in m.splitlines() if l.startswith("Requires-Python:")), None)
    sos = sorted((i for i in z.infolist() if i.filename.endswith(".so")), key=lambda i: i.compress_size)
    res["so_files"] = [(i.filename, i.file_size) for i in sos]
    for i in sos:
        if i.compress_size > 64 << 20:
            break
        need = dt_needed(z.read(i)) or []
        cud = [n for n in need if n.startswith("libcudart.so")]
        if cud:
            res["soname"], res["from"], res["needed"] = cud[0], i.filename, need
            break
    res["bytes_fetched"] = f.fetched
    print(json.dumps(res))
