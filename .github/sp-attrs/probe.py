"""usage: <python with one scipy> probe.py dir > dir.json
          <python with one scipy> probe.py get names.json > get.json
Objects: scipy and its public submodules, and the sparse matrix classes. `dir` lists the public names of each and its __all__ (or the import
error); `get` runs getattr for the union of names and records ok, the first warning, or the error."""
import importlib, json, sys, warnings
warnings.simplefilter("ignore")
MODS = ["scipy", "scipy.cluster", "scipy.cluster.hierarchy", "scipy.cluster.vq", "scipy.constants", "scipy.fft", "scipy.fftpack",
        "scipy.integrate", "scipy.interpolate", "scipy.io", "scipy.io.wavfile", "scipy.io.matlab", "scipy.linalg", "scipy.misc",
        "scipy.ndimage", "scipy.odr", "scipy.optimize", "scipy.signal", "scipy.signal.windows", "scipy.sparse", "scipy.sparse.linalg",
        "scipy.sparse.csgraph", "scipy.spatial", "scipy.spatial.distance", "scipy.spatial.transform", "scipy.special", "scipy.stats",
        "scipy.stats.mstats"]
CLASSES = ["scipy.sparse:csr_matrix", "scipy.sparse:coo_matrix", "scipy.sparse:lil_matrix"]


def load(spec):
    m, _, c = spec.partition(":")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        o = importlib.import_module(m)
        return getattr(o, c) if c else o


O, ERR = {}, {}
for s in MODS + CLASSES:
    try:
        O[s] = load(s)
    except Exception as e:
        ERR[s] = "%s: %s" % (type(e).__name__, e)
import scipy
if sys.argv[1] == "dir":
    json.dump({"scipy": scipy.__version__, "python": sys.version.split()[0], "numpy": __import__("numpy").__version__, "import_errors": ERR,
               "dir": {k: sorted(n for n in dir(v) if not n.startswith("_")) for k, v in O.items()},
               "all": {k: sorted(getattr(v, "__all__")) for k, v in O.items() if isinstance(getattr(v, "__all__", None), (list, tuple))}}, sys.stdout)
else:
    out = {}
    for k, names in json.load(open(sys.argv[2])).items():
        res = {}
        for n in names:
            if k not in O:
                res[n] = {"ok": False, "error": ERR.get(k, "missing"), "warn": []}
                continue
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                try:
                    getattr(O[k], n)
                    res[n] = {"ok": True, "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
                except Exception as e:
                    res[n] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
        out[k] = res
    json.dump({"scipy": scipy.__version__, "import_errors": ERR, "get": out}, sys.stdout)
