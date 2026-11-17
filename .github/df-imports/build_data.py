#!/usr/bin/env python3
"""names_hist.json + dates.json -> data.json, names-core.json, names-pipelines.json, names-modular.json, where.json

Usage: python3 -I build_data.py names_hist.json dates.json <as-of> <out dir>
data.json      releases, the table of release ranges ("ranges"), the life of every module ("mods"), the top-level names
               ("top"), the lazy-table entries that cannot resolve ("stale"), and which file holds which module's names.
names-*.json   {module: {name: index into "ranges"}} for the modules below the top level, in three files so that a lookup
               loads only the part it needs.
where.json     for the newest release: the modules that define a name (def, class or assignment), to say where a name
               that left one module can be imported from now.
A range is a flat list of index pairs into "releases": [first release with it, first later release without it (0 = still
there), ...].
"""
import json, sys
from pathlib import Path
H, P, ASOF, OUT = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3], Path(sys.argv[4])
tags, finals = H["tags"], H["finals"]
ver = lambda t: tuple(int(x) for x in t.lstrip("v").split("."))
N = len(tags)
releases = []
for i, t in enumerate(tags):
    nxt = ver(tags[i + 1]) if i + 1 < N else (999,)
    releases.append([t[1:], P["dates"][t[1:]], [f for f in finals if ver(t) <= ver(f) < nxt][-1][1:]])
if ver(releases[-1][0])[:2] == ver(releases[-2][0])[:2]:
    raise SystemExit("the newest release is a patch of the last minor; nothing to rebuild")


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


def chunk(m):
    head = m.split(".")[0]
    return "pipelines" if head == "pipelines" else "modular" if head == "modular_pipelines" else "core"


files = {"core": {}, "pipelines": {}, "modular": {}}
for m in all_mods:
    if m and names[m]:
        files[chunk(m)][m] = names[m]
idx = {t: i for i, t in enumerate(tags)}
stale = []
for m, n, key, kind, ts in H["stale"]:
    ii = sorted(idx[t] for t in ts)
    assert ii == list(range(ii[0], ii[-1] + 1)), (m, n, ts)
    stale.append([m, n, key, kind, ii[0], ii[-1] + 1 if ii[-1] + 1 < N else 0])
pk = sorted({m for t in tags for m in H["pkgs"][t] if m})
lazy_first = {}
for i, t in enumerate(tags):
    for m in H["lazy"][t]:
        lazy_first.setdefault(m, i)
out = {"about": "Names importable from diffusers and from each of its modules at the first release of every minor version, read from the "
                "source of each release tag along the path with the optional backends installed. CC BY 4.0, "
                "erimaki-kobo.github.io/en/diffusers-import-name-version-lookup/",
       "asof": ASOF, "latest": releases[-1][0], "releases": releases, "ranges": table, "mods": mods, "packages": pk,
       "lazy_from": lazy_first[""], "top": names[""], "stale": stale,
       "files": {"core": "names-core.json", "pipelines": "names-pipelines.json", "modular": "names-modular.json", "where": "where.json"}}
# where.json: definitions in the newest release. Names defined in many modules (logger, EXAMPLE_DOC_STRING, copied helpers) keep a count only.
own = {m: v for m, v in H["own_latest"].items() if not m.rsplit(".", 1)[-1].startswith("dummy_")}   # placeholders for a missing backend
wm = sorted(own)
where = {}
for i, m in enumerate(wm):
    for n in own[m]:
        if not (n.startswith("__") and n.endswith("__")):
            where.setdefault(n, []).append(i)
MAXW = 8
where = {n: (v if len(v) <= MAXW else [-len(v)]) for n, v in sorted(where.items())}
OUT.mkdir(parents=True, exist_ok=True)
dump = lambda o, f: (OUT / f).write_text(json.dumps(o, separators=(",", ":"), sort_keys=True), encoding="ascii")
dump(out, "data.json")
for k, v in files.items():
    dump(v, out["files"][k])
dump({"release": releases[-1][0], "modules": wm, "names": where}, "where.json")
for f in sorted(OUT.glob("*.json")):
    print(f.name, f.stat().st_size, file=sys.stderr)
print("releases %d | modules ever %d | top names %d (now %d) | pairs %d | ranges %d | stale %d" % (
    N, len(mods), len(names[""]), sum(1 for r in names[""].values() if table[r][-1] == 0),
    sum(len(v) for v in names.values()), len(table), len(stale)), file=sys.stderr)
