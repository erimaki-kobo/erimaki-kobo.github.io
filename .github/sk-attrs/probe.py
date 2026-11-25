"""usage: <python with one scikit-learn> probe.py dir > dir.json
          <python with one scikit-learn> probe.py get names.json > get.json
Objects: sklearn and its public submodules. `dir` lists the public names of each and its __all__ (or the import
error); `get` runs getattr for the union of names and records ok, the first warning, or the error."""
import importlib, json, pkgutil, sys, warnings
warnings.simplefilter("ignore")
MODS = ["sklearn", "sklearn.base", "sklearn.calibration", "sklearn.cluster", "sklearn.compose", "sklearn.covariance", "sklearn.cross_decomposition",
        "sklearn.datasets", "sklearn.decomposition", "sklearn.discriminant_analysis", "sklearn.dummy", "sklearn.ensemble", "sklearn.exceptions",
        "sklearn.externals", "sklearn.feature_extraction", "sklearn.feature_extraction.text", "sklearn.feature_selection", "sklearn.gaussian_process",
        "sklearn.impute", "sklearn.inspection", "sklearn.isotonic", "sklearn.kernel_approximation", "sklearn.kernel_ridge", "sklearn.linear_model",
        "sklearn.manifold", "sklearn.metrics", "sklearn.metrics.pairwise", "sklearn.mixture", "sklearn.model_selection", "sklearn.multiclass",
        "sklearn.multioutput", "sklearn.naive_bayes", "sklearn.neighbors", "sklearn.neural_network", "sklearn.pipeline", "sklearn.preprocessing",
        "sklearn.random_projection", "sklearn.semi_supervised", "sklearn.svm", "sklearn.tree", "sklearn.utils", "sklearn.utils.validation",
        "sklearn.utils.multiclass", "sklearn.utils.extmath", "sklearn.utils.metaestimators", "sklearn.utils.estimator_checks"]
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
import sklearn
if sys.argv[1] == "dir":
    json.dump({"sklearn": sklearn.__version__, "python": sys.version.split()[0], "numpy": __import__("numpy").__version__, "import_errors": ERR,
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
    json.dump({"sklearn": sklearn.__version__, "import_errors": ERR, "get": out}, sys.stdout)
