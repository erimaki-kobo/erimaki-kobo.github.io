#!/usr/bin/env python3
"""names_hist.json + hub_pypi.json + the downstream files -> data.json for the page and its tool.

Usage: python3 -I build_data.py names_hist.json hub_pypi.json <as-of> lib=ds_lib.json [lib=...] > data.json
Ranges are index pairs into "releases": [first release with the name, first later release without it (0 = still there)].
"users": for every huggingface_hub name that is gone from the newest release, which versions of each library import it
at module level (so importing that file fails), as runs of [first minor's release, last minor's release, example file].
"needs": per library, runs of versions with the huggingface_hub range in which all of its module-level imports resolve.
"""
import json, sys
H, P, ASOF = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
LIBS = dict(a.split("=", 1) for a in sys.argv[4:])
MIN_VERSION = {"gradio": (3, 0, 0)}       # older tags of that repository are not the PyPI package's history
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


mod_ix, top = {}, {}
for n in sorted({n for t in tags for n in H["top"][t]["names"]}):
    r = ranges([n in H["top"][t]["names"] for t in tags])
    m = H["top"][tags[(r[-1] or N) - 1]]["names"][n]
    top[n] = [mod_ix.setdefault(m, len(mod_ix))] + r
out = {"about": "Names importable from huggingface_hub, huggingface_hub.utils and huggingface_hub.errors at the first release of every minor "
                "version, and which releases of diffusers, sentence-transformers, gradio, datasets and peft import the removed ones. "
                "Read from the source of each release tag. CC BY 4.0, erimaki-kobo.github.io/en/huggingface-hub-import-name-version-lookup/",
       "asof": ASOF, "latest": releases[-1][0], "releases": releases, "modules": list(mod_ix), "top": top}
for key in ("utils", "errors"):
    names = sorted({n for t in tags for n in H[key].get(t, [])})
    out[key] = {n: ranges([n in H[key].get(t, ()) for t in tags]) for n in names}
    out[key + "_since"] = min(i for i, t in enumerate(tags) if t in H[key])


def last_range(kind, name):
    d = out[kind].get(name)
    if d is None:
        return None
    d = d[1:] if kind == "top" else d
    return d[-2], d[-1]


users, needs, unknown = {}, {}, {}
for lib, path in LIBS.items():
    D = json.load(open(path))
    vs = [v for v in D["versions"] if ver(v) >= MIN_VERSION.get(lib, (0,))]
    runs = []
    per_name = {}
    for vi, v in enumerate(vs):
        lo, hi, lo_n, hi_n = 0, 0, "", ""
        for k, e in D["imports"][v].items():
            if not e["hard"]:
                continue
            kind, name = k.split(":")
            r = last_range(kind, name)
            if r is None:
                unknown.setdefault(k, set()).add(lib)
                continue
            if r[0] > lo:
                lo, lo_n = r[0], name
            if r[1] and (hi == 0 or r[1] < hi):
                hi, hi_n = r[1], name
            if r[1]:
                per_name.setdefault(k, []).append((vi, e["file"]))
        key = [lo, lo_n, hi, hi_n]
        if runs and runs[-1][2:] == key:
            runs[-1][1] = v
        else:
            runs.append([v, v] + key)
    needs[lib] = {"runs": runs, "latest": vs[-1], "dates": {v: D["dates"][v] for v in vs}}
    for k, hits in per_name.items():
        rr = []
        for vi, f in hits:
            if rr and rr[-1][3] == vi - 1:
                rr[-1][1], rr[-1][3] = vs[vi], vi
            else:
                rr.append([vs[vi], vs[vi], f, vi])
        # the version after the run, where the import is gone (None if the newest release still has it)
        users.setdefault(k, {})[lib] = [[a, b, f, (vs[i + 1] if i + 1 < len(vs) else None)] for a, b, f, i in rr]
out["users"], out["needs"] = users, needs
out["not_names"] = {k: sorted(v) for k, v in sorted(unknown.items())}
json.dump(out, sys.stdout, separators=(",", ":"), sort_keys=True)
