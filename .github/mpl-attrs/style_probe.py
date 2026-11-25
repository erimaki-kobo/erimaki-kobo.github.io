"""usage: <python with one matplotlib> style_probe.py names.json > styles.json
For each style name, plt.style.use(name) in a fresh rc state: ok, warn (with the warning text) or the error."""
import json, sys, warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
out = {}
for n in json.load(open(sys.argv[1])):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            with plt.style.context(n):
                pass
            ws = [str(x.message) for x in w if issubclass(x.category, matplotlib.MatplotlibDeprecationWarning)]
            out[n] = {"ok": True, "warn": ws[:1]}
        except Exception as e:
            out[n] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
json.dump({"matplotlib": matplotlib.__version__, "styles": out}, sys.stdout)
