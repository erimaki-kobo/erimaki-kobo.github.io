"""usage: <python with one scikit-image> probe.py dir > dir.json
          <python with one scikit-image> probe.py get names.json > get.json
Objects: skimage and its public subpackages. `dir` lists the public names of each, its __all__ and its submodule files (or the
import error); `get` runs getattr for the union of names (or imports a submodule) and records ok, the first warning, or the error."""
import importlib, json, pkgutil, sys, warnings
warnings.simplefilter("ignore")
MODS = ["skimage"] + ["skimage." + m for m in ("color", "data", "draw", "exposure", "external", "feature", "filters", "filters.rank", "future", "future.graph",
                                              "graph", "io", "measure", "metrics", "morphology", "novice", "registration", "restoration", "segmentation",
                                              "transform", "util", "viewer")]
CLASSES = []


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
import skimage
if sys.argv[1] == "dir":
    json.dump({"skimage": skimage.__version__, "python": sys.version.split()[0], "numpy": __import__("numpy").__version__, "scipy": __import__("scipy").__version__, "import_errors": ERR,
               "dir": {k: sorted(n for n in dir(v) if not n.startswith("_")) for k, v in O.items()},
               "all": {k: sorted(getattr(v, "__all__")) for k, v in O.items() if isinstance(getattr(v, "__all__", None), (list, tuple))},
               "submodules": {k: sorted(m.name for m in pkgutil.iter_modules(v.__path__) if not m.name.startswith("_") and m.name != "tests")
                              for k, v in O.items() if hasattr(v, "__path__")}}, sys.stdout)
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
                    try:   # a submodule that is not imported by its package: `import sklearn.ensemble.forest`
                        if not hasattr(O[k], "__path__"):
                            raise
                        importlib.import_module("%s.%s" % (k, n))
                        res[n] = {"ok": True, "module": True, "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
                    except Exception as e2:
                        res[n] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
        out[k] = res
    json.dump({"skimage": skimage.__version__, "import_errors": ERR, "get": out}, sys.stdout)
