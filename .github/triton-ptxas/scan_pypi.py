"""Read, without executing anything, which sm_* names each ptxas binary contains.
usage: python3 scan_pypi.py <workdir>   -> <workdir>/pypi.json
Sources: PyPI wheels of triton (bundled bin/ptxas, bin/ptxas-blackwell), nvidia-cuda-nvcc-cu12 and nvidia-cuda-nvcc (NVIDIA's own ptxas),
and the requires_dist metadata of every torch release. Each wheel is checked against the sha256 PyPI publishes, then deleted."""
import json, subprocess, os, zipfile, re, hashlib, sys
W = sys.argv[1]; os.makedirs(W, exist_ok=True)
def get(url, fn=None):
    if fn:
        subprocess.run(["curl", "-sSfL", "-o", fn, url], check=True); return fn
    return json.loads(subprocess.run(["curl", "-sSfL", url], check=True, capture_output=True, text=True).stdout)
def sms(b):
    s = {m.group(0).decode() for m in re.finditer(rb"(?<![A-Za-z0-9_])sm_(\d{2,3})([af]?)(?![A-Za-z0-9_])", b)}
    return sorted((x for x in s if int(re.search(r"\d+", x).group()) >= 80), key=lambda x: (int(re.search(r"\d+", x).group()), x))
def tools(fn, pat):
    z = zipfile.ZipFile(fn); out = {}
    for n in z.namelist():
        if re.search(pat, n):
            b = z.read(n); v = re.search(rb"release (\d+\.\d+), V(\d+\.\d+\.\d+)", b)
            out[n.rsplit("/", 1)[1]] = {"banner": v.group(2).decode() if v else None, "sha256": hashlib.sha256(b).hexdigest(), "sm": sms(b)}
    return out
def arch_of(fn): return "aarch64" if "aarch64" in fn else "x86_64" if "x86_64" in fn else None
def vkey(v): return [int(x) for x in re.findall(r"\d+", v)]
out = {"triton": {}, "nvcc": {}, "torch": {}}
d = get("https://pypi.org/pypi/triton/json")
for v in sorted(d["releases"], key=vkey):
    if vkey(v) < [2, 0, 0]: continue
    fs = d["releases"][v]; seen = set()
    for f in sorted(fs, key=lambda f: ("cp312" not in f["filename"], f["filename"])):
        a = arch_of(f["filename"])
        if not a or a in seen or not f["filename"].endswith(".whl"): continue
        seen.add(a); fn = get(f["url"], os.path.join(W, f["filename"]))
        assert hashlib.sha256(open(fn, "rb").read()).hexdigest() == f["digests"]["sha256"]
        out["triton"].setdefault(v, {"date": min(x["upload_time"] for x in fs)[:10], "arch": {}})["arch"][a] = {"wheel": f["filename"], "wheel_sha256": f["digests"]["sha256"], "tools": tools(fn, r"/bin/ptxas[^/]*$")}
        os.remove(fn); print("triton", v, a, flush=True)
for p in ("nvidia-cuda-nvcc-cu12", "nvidia-cuda-nvcc"):
    d = get(f"https://pypi.org/pypi/{p}/json")
    for v, fs in d["releases"].items():
        for f in fs:
            a = arch_of(f["filename"])
            if not a or not re.fullmatch(r"\d+\.\d+\.\d+", v): continue
            fn = get(f["url"], os.path.join(W, f["filename"]))
            assert hashlib.sha256(open(fn, "rb").read()).hexdigest() == f["digests"]["sha256"]
            t = tools(fn, r"/bin/ptxas$"); os.remove(fn)
            if t: out["nvcc"].setdefault(v, {"pkg": p, "date": f["upload_time"][:10], "arch": {}})["arch"][a] = dict(t["ptxas"], wheel=f["filename"])
            print(p, v, a, flush=True)
d = get("https://pypi.org/pypi/torch/json")
for v in sorted((v for v in d["releases"] if re.fullmatch(r"\d+\.\d+\.\d+", v) and d["releases"][v] and vkey(v) >= [2, 0, 0]), key=vkey):
    j = get(f"https://pypi.org/pypi/torch/{v}/json")
    rd = [r for r in (j["info"].get("requires_dist") or []) if r.lower().startswith("triton")]
    out["torch"][v] = {"date": min(f["upload_time"] for f in j["urls"])[:10], "triton": rd[0] if rd else None}
json.dump(out, open(os.path.join(W, "pypi.json"), "w"), indent=1, sort_keys=True)
