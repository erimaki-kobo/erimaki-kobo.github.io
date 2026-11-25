#!/usr/bin/env python3
"""names_hist.json + dates.json -> <lib>.json for the import-name lookup of one library (accelerate, peft or trl).

Usage: python3 -I build_data.py <lib> names_hist.json dates.json <as-of> <out dir>
<lib>.json   releases [version, PyPI date, last patch release of that minor], the table of release ranges ("ranges"),
             the life of every module ("mods"), the names of every module ("names", "" = top level), the lazy-table
             entries that cannot resolve ("stale"), and for the newest release the modules that define each name ("where").
A range is a flat list of index pairs into "releases": [first release with it, first later release without it (0 = still
there), ...].
"""
import json, re, sys
from pathlib import Path
LIB, H, P, ASOF, OUT = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3])), sys.argv[4], Path(sys.argv[5])
tags, finals = H["tags"], H["finals"]
vs = lambda t: re.split("==|@", t)[-1].lstrip("v")          # "langchain==1.2.3" or "v0.1.0" -> "1.2.3"
ver = lambda t: tuple(int(x) for x in vs(t).split("."))
N = len(tags)
releases = []
for i, t in enumerate(tags):
    nxt = ver(tags[i + 1]) if i + 1 < N else (999,)
    releases.append([vs(t), P["dates"][vs(t)], vs([f for f in finals if ver(t) <= ver(f) < nxt][-1])])


def ranges(has):
    out, start = [], None
    for i, h in enumerate(has):
        if h and start is None:
            start = i
        elif not h and start is not None:
            out += [start, i]
            start = None
    if start is not None:
        out += [start, 0]
    return out


table, tix = [], {}


def rix(r):
    k = tuple(r)
    if k not in tix:
        tix[k] = len(table)
        table.append(r)
    return tix[k]


sets = [{m: set(v) for m, v in H["mods"][t].items()} for t in tags]
all_mods = sorted({m for s in sets for m in s})
mods = {m: rix(ranges([m in s for s in sets])) for m in all_mods if m}
names = {}
for m in all_mods:
    every = sorted({n for s in sets if m in s for n in s[m]})
    names[m] = {n: rix(ranges([m in s and n in s[m] for s in sets])) for n in every}
idx = {t: i for i, t in enumerate(tags)}
stale = []
for m, n, key, kind, ts in H["stale"]:
    ii = sorted(idx[t] for t in ts)
    assert ii == list(range(ii[0], ii[-1] + 1)), (m, n, ts)
    stale.append([m, n, key, kind, ii[0], ii[-1] + 1 if ii[-1] + 1 < N else 0])
own = {m: v for m, v in H["own_latest"].items() if not m.rsplit(".", 1)[-1].startswith("dummy_")}
wm = sorted(own)
where = {}
for i, m in enumerate(wm):
    for n in own[m]:
        if not (n.startswith("__") and n.endswith("__")):
            where.setdefault(n, []).append(i)
where = {n: (v if len(v) <= 8 else [-len(v)]) for n, v in sorted(where.items())}
# names a module serves through __getattr__ from another package (langchain -> langchain_community): their ranges and target
deferred, via = {}, {}
if H.get("deferred"):
    pairs_ = {}
    for i, t in enumerate(tags):
        for m, ns in H["deferred"].get(t, {}).items():
            for n, target in ns.items():
                pairs_.setdefault((m, n), [False] * N)[i] = True
                via.setdefault(m, {})[n] = target
    for (m, n), has in pairs_.items():
        deferred.setdefault(m, {})[n] = rix(ranges(has))
lazy_from = next((i for i, t in enumerate(tags) if "" in H["lazy"][t]), None)
out = {"lib": LIB, "asof": ASOF, "latest": releases[-1][0], "releases": releases, "ranges": table, "mods": mods,
       "names": names, "stale": stale, "lazy_from": lazy_from, "where": {"modules": wm, "names": where}}
if deferred:
    out["deferred"], out["via"] = deferred, via
# names that import but raise when used (openai 1.x: APIRemovedInV1 proxies for the 0.x API)
if H.get("proxies"):
    px = {}
    for i, t in enumerate(tags):
        for m, ns in H["proxies"].get(t, {}).items():
            for n in ns:
                px.setdefault((m, n), [False] * N)[i] = True
    out["proxies"] = {}
    for (m, n), has in px.items():
        out["proxies"].setdefault(m, {})[n] = rix(ranges(has))
# modules that pass along everything of another package (`from pydantic.v1 import *`): their names are not listed
if H.get("ext_star"):
    es = {}
    for i, t in enumerate(tags):
        for m, srcs in H["ext_star"].get(t, {}).items():
            es.setdefault(m, [[False] * N, set()])
            es[m][0][i] = True
            es[m][1] |= set(srcs)
    out["ext_star"] = {m: [rix(ranges(h)), sorted(s)] for m, (h, s) in es.items()}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / (LIB + ".json")).write_text(json.dumps(out, separators=(",", ":"), sort_keys=True), encoding="ascii")
print("%s: releases %d (%s..%s) | modules ever %d (gone %d) | top %d (gone %d) | pairs %d | ranges %d | stale %d | %d bytes" % (
    LIB, N, releases[0][0], releases[-1][0], len(mods), sum(1 for r in mods.values() if table[r][-1]), len(names[""]),
    sum(1 for r in names[""].values() if table[r][-1]), sum(len(v) for v in names.values()), len(table), len(stale),
    (OUT / (LIB + ".json")).stat().st_size), file=sys.stderr)
