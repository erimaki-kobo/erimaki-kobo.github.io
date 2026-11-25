"""usage: python3 -I verify.py np_attrs.json probes/ > verify.json
Compares what the tables (np_attrs.py, read from the source) predict with what getattr(numpy, name) did in an installed numpy
of the same release (probe.py)."""
import json, os, sys
A, PD = json.load(open(sys.argv[1])), sys.argv[2]
n_ok, bad, rel = 0, [], []
for v, r in A.items():
    f = os.path.join(PD, v + ".json")
    if not os.path.exists(f):
        continue
    p = json.load(open(f))["names"]
    rel.append(v)
    def chk(n, cond, why):
        global n_ok
        if cond: n_ok += 1
        else: bad.append((v, n, why, p.get(n)))
    for n in r["deprecated"]:
        chk(n, p[n]["ok"] and "DeprecationWarning" in p[n]["warn"], "deprecated")
    for n in r["expired_fn"]:
        chk(n, p[n]["ok"] and "DeprecationWarning" in p[n]["warn"], "expired_fn")
    for n, m in r["former"].items():
        chk(n, not p[n]["ok"] and p[n]["error"] == m, "former")
    for n, m in r["expired"].items():
        if n in r["former"]:
            continue
        chk(n, not p[n]["ok"] and p[n]["error"] == "`np.%s` was removed in the NumPy 2.0 release. %s" % (n, m), "expired")
    for n, m in r["special"].items():
        chk(n, not p[n]["ok"] and p[n]["error"] == m, "special")
    for n in r["future"]:
        chk(n, "FutureWarning" in p[n]["warn"], "future")
print("releases installed and probed:", rel, "| table entries confirmed:", n_ok, "| mismatches:", len(bad), file=sys.stderr)
for b in bad:
    print(*b, file=sys.stderr)
json.dump({"releases": rel, "confirmed": n_ok, "mismatches": bad}, sys.stdout, indent=0)
