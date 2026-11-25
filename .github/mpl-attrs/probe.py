"""usage: <python with one matplotlib> probe.py dir > dir.json
          <python with one matplotlib> probe.py get names.json > get.json
Objects: matplotlib, its public modules, and the classes people call methods on (Figure, Axes, FigureCanvasAgg, ...). Also records plt.style.available. `dir` lists the public names of each and its __all__ (or the import
error); `get` runs getattr for the union of names and records ok, the first warning, or the error."""
import importlib, json, pkgutil, sys, warnings
warnings.simplefilter("ignore")
import os
os.environ.setdefault("MPLBACKEND", "Agg")
MODS = ["matplotlib", "matplotlib.pyplot", "matplotlib.cm", "matplotlib.cbook", "matplotlib.colors", "matplotlib.colorbar",
        "matplotlib.dates", "matplotlib.ticker", "matplotlib.mlab", "matplotlib.patches", "matplotlib.lines", "matplotlib.text",
        "matplotlib.figure", "matplotlib.axes", "matplotlib.animation", "matplotlib.style", "matplotlib.font_manager",
        "matplotlib.collections", "matplotlib.legend", "matplotlib.transforms", "matplotlib.path", "matplotlib.image",
        "matplotlib.backends.backend_agg", "matplotlib.backend_bases", "matplotlib.gridspec", "matplotlib.rcsetup",
        "matplotlib.widgets", "matplotlib.markers", "mpl_toolkits.mplot3d", "mpl_toolkits.mplot3d.axes3d", "mpl_toolkits.axes_grid1"]
CLASSES = ["matplotlib.figure:Figure", "matplotlib.axes:Axes", "matplotlib.backends.backend_agg:FigureCanvasAgg",
           "matplotlib.colorbar:Colorbar", "matplotlib.legend:Legend", "matplotlib.text:Text", "matplotlib.lines:Line2D",
           "matplotlib.colors:Colormap", "mpl_toolkits.mplot3d.axes3d:Axes3D", "matplotlib.animation:FuncAnimation"]


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
import matplotlib
if sys.argv[1] == "dir":
    json.dump({"matplotlib": matplotlib.__version__, "styles": sorted(__import__("matplotlib.pyplot").pyplot.style.available), "python": sys.version.split()[0], "numpy": __import__("numpy").__version__, "import_errors": ERR,
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
    json.dump({"matplotlib": matplotlib.__version__, "import_errors": ERR, "get": out}, sys.stdout)
