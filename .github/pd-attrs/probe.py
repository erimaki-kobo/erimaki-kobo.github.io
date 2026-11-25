"""usage: <python with one pandas> probe.py dir > dir.json          the public names of each object
          <python with one pandas> probe.py get names.json > get.json  getattr(object, name) for the union of names: ok, warning, or error
Objects: the pandas module, DataFrame, Series, Index, DatetimeIndex, Timestamp, the groupby objects, the .str accessor."""
import json, sys, warnings
warnings.simplefilter("ignore")
import pandas as pd


def objects():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    o = {"pandas": pd, "DataFrame": pd.DataFrame, "Series": pd.Series, "Index": pd.Index, "DatetimeIndex": pd.DatetimeIndex,
         "Timestamp": pd.Timestamp, "DataFrameGroupBy": type(df.groupby("a")), "SeriesGroupBy": type(df.groupby("a")["b"]),
         "StringMethods": type(df["b"].str)}
    return o


O = objects()
if sys.argv[1] == "dir":
    json.dump({"pandas": pd.__version__, "python": sys.version.split()[0], "numpy": __import__("numpy").__version__,
               "dir": {k: sorted(n for n in dir(v) if not n.startswith("_")) for k, v in O.items()}}, sys.stdout)
else:
    want = json.load(open(sys.argv[2]))
    out = {}
    for k, names in want.items():
        res = {}
        for n in names:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                try:
                    getattr(O[k], n)
                    res[n] = {"ok": True, "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
                except Exception as e:
                    res[n] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
        out[k] = res
    json.dump({"pandas": pd.__version__, "get": out}, sys.stdout)
