"""usage: <python with one numpy> probe.py names.json > result.json
Runs `getattr(numpy, name)` for each name and records what happens: ok, the warning class, or the AttributeError message."""
import json, sys, warnings
import numpy as np
out = {"numpy": np.__version__, "python": sys.version.split()[0], "names": {}}
for n in json.load(open(sys.argv[1])):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            v = getattr(np, n)
            r = {"ok": True, "warn": sorted({x.category.__name__ for x in w})}
            if n in ("financial_probe",):
                pass
        except AttributeError as e:
            r = {"ok": False, "error": str(e), "warn": sorted({x.category.__name__ for x in w})}
    out["names"][n] = r
json.dump(out, sys.stdout, indent=0)
