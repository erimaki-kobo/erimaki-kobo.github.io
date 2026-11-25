import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from classify import judge, judge_stream
from scenarios import FORMATS
key = lambda v: tuple(int(x) for x in v[1:].split("."))
D = sys.argv[1]
VS = sorted([f[:-5] for f in os.listdir(D) if f.endswith(".json")], key=key)
R = {v: json.load(open(os.path.join(D, v + ".json"))) for v in VS}
out = {}
for fmt, spec in FORMATS.items():
    for case, c in spec["cases"].items():
        for mode in ("nonstream", "stream"):
            seq = []
            for v in VS:
                p = R[v]["parsers"].get(fmt, {})
                if "error" in p:
                    seq.append(("missing", p["error"][:60])); continue
                x = p["cases"][case][mode]
                if "exception" in x:
                    seq.append(("exception", x["exception"][:90] + " @" + x["where"])); continue
                tr = c["want"] is None
                if mode == "nonstream":
                    seq.append(judge(x["calls"], x["content"], c["want"] or [], c["content"], tr))
                else:
                    seq.append(judge_stream(x["deltas"], c["want"] or [], c["content"], tr))
            out[(fmt, case, mode)] = seq
json.dump({"versions": VS, "rows": [[f, c, m, [list(s) for s in seq]] for (f, c, m), seq in out.items()],
           "classes": {v: {f: R[v]["parsers"][f].get("class") for f in FORMATS} for v in VS}}, open(sys.argv[2], "w"), ensure_ascii=False)
for (f, c, m), seq in out.items():
    runs, prev = [], None
    for v, s in zip(VS, seq):
        if s != prev:
            runs.append([v, v, s]); prev = s
        else:
            runs[-1][1] = v
    if len(runs) == 1 and runs[0][2][0] == "ok":
        continue
    print(f"{f:13} {c:14} {m:9}", " | ".join("%s-%s %s %s" % (a, b, s[0], s[1][:70]) for a, b, s in runs))
