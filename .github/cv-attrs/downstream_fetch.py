"""usage: python3 -I downstream_fetch.py packages.txt meta_dir src_dir
For each PyPI package name: save its JSON (meta_dir/<name>.json), then download the newest release's sdist (or, without one,
a wheel) and unpack it into its own new folder src_dir/<name>/. Nothing from the archives is run."""
import io, json, os, re, sys, tarfile, urllib.request, zipfile
names = [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]
META, SRC = sys.argv[2], sys.argv[3]
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "erimaki-kobo downstream scan"}), timeout=120) as r:
        return r.read()
for n in names:
    try:
        j = json.loads(get("https://pypi.org/pypi/%s/json" % n))
    except Exception as e:
        print("SKIP", n, type(e).__name__, e)
        continue
    open(os.path.join(META, n + ".json"), "wb").write(json.dumps({"info": {k: j["info"].get(k) for k in ("name", "version", "requires_dist")},
                                                                   "urls": j["urls"]}).encode())
    files = [f for f in j["urls"] if not f.get("yanked")]
    pick = ([f for f in files if f["packagetype"] == "sdist"] or [f for f in files if f["filename"].endswith("none-any.whl")]
            or [f for f in files if "manylinux" in f["filename"] and "x86_64" in f["filename"]] or files)
    if not pick:
        print("SKIP", n, "no files")
        continue
    f = sorted(pick, key=lambda f: f["size"])[0]
    if f["size"] > 150e6:
        print("SKIP", n, "too big", f["size"])
        continue
    dest = os.path.join(SRC, n)
    if os.path.isdir(dest):
        print("have", n)
        continue
    data = get(f["url"])
    os.makedirs(dest)
    try:
        if f["filename"].endswith((".whl", ".zip")):
            z = zipfile.ZipFile(io.BytesIO(data))
            for m in z.namelist():
                if m.endswith(".py") and not m.startswith("/") and ".." not in m:
                    p = os.path.join(dest, m)
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    open(p, "wb").write(z.read(m))
        else:
            t = tarfile.open(fileobj=io.BytesIO(data))
            for m in t.getmembers():
                if m.isfile() and m.name.endswith(".py") and not m.name.startswith("/") and ".." not in m.name:
                    p = os.path.join(dest, m.name)
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    open(p, "wb").write(t.extractfile(m).read())
        print("ok  ", n, j["info"]["version"], f["filename"], f["size"])
    except Exception as e:
        print("FAIL", n, type(e).__name__, e)
