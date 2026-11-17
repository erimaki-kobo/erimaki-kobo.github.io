#!/usr/bin/env python3
"""names_hist.json + tf_pypi.json -> data.json (what the page and its tool read).

Usage: python3 -I build_data.py names_hist.json tf_pypi.json <as-of YYYY-MM-DD> > data.json
Ranges are pairs of indexes into "releases": [first release that has the name, first release after it that does not];
the second is 0 while the name is still there. "alias" holds the v5 names that are in no list but still import
because _LazyModule.__getattr__ maps them to another name (see names_hist.py).
"""
import json, sys
H, P, ASOF = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
tags, finals = H["tags"], H["finals"]
ver = lambda t: tuple(int(x) for x in t.lstrip("v").split("."))
N = len(tags)

releases = []
for i, t in enumerate(tags):
    nxt = ver(tags[i + 1]) if i + 1 < N else (999,)
    last = [f for f in finals if ver(t) <= ver(f) < nxt][-1]
    releases.append([t[1:], P["dates"][t[1:]], last[1:]])
if len(releases) > 1 and ver(releases[-1][0])[:2] == ver(releases[-2][0])[:2]:
    raise SystemExit("the newest release is a patch of the last minor; drop the duplicate before building")


def ranges(present):
    """present: list of (index, bool or None); None = the module does not exist at that release (ends a range)."""
    out, open_at = [], None
    for i, has in present:
        if has and open_at is None:
            open_at = i
        elif not has and open_at is not None:
            out += [open_at, i]
            open_at = None
    if open_at is not None:
        out += [open_at, 0]
    return out


mods, mod_ix = [], {}
top = {}
all_top = sorted({n for t in tags for n in H["top"][t]["names"]})
for n in all_top:
    r = ranges([(i, n in H["top"][t]["names"]) for i, t in enumerate(tags)])
    last_tag = tags[(r[-1] or N) - 1]
    m = H["top"][last_tag]["names"][n]
    top[n] = [mod_ix.setdefault(m, len(mod_ix))] + r
mods = list(mod_ix)


def alias_target(n, t):
    a, S = H["alias"].get(t), H["top"][t]["names"]
    if not a or n in S:
        return None
    if a["tok_fast"] and n.endswith("TokenizerFast") and n[:-4] in S:
        return n[:-4]
    if a["conv"] and (n.endswith("Tokenizer") or n.endswith("TokenizerFast")):
        C = a["converters"]
        look = n[:-4] if n.endswith("TokenizerFast") else n
        if look in C:
            cands = [C[look].replace("Converter", "") + "Tokenizer"] + [k for k in C if C[k] == C[look] and k != look]
            for c in cands:
                if c in S:
                    return c
    if a["img_fast"] and n.endswith("ImageProcessorFast") and n[:-4] in S:
        return n[:-4]
    return None


universe = set(all_top)
for a in H["alias"].values():
    universe |= set(a["converters"]) | {k + "Fast" for k in a["converters"]}
alias = {}
for n in sorted(universe):
    if not (n.endswith("Tokenizer") or n.endswith("TokenizerFast") or n.endswith("ImageProcessorFast")):
        continue
    runs, cur = [], None
    for i, t in enumerate(tags):
        tg = alias_target(n, t)
        if cur and cur[2] == tg and cur[1] == i:
            cur[1] = i + 1
        else:
            if cur:
                runs.append(cur)
            cur = [i, i + 1, tg] if tg else None
    if cur:
        runs.append(cur)
    if runs:
        alias[n] = [[s, 0 if e == N else e, tg] for s, e, tg in runs]

out = {"about": "Names importable from transformers, transformers.utils and transformers.file_utils at the first release of every "
                "minor version, read from the source of each release tag. CC BY 4.0, "
                "erimaki-kobo.github.io/en/transformers-import-name-version-lookup/",
       "asof": ASOF, "latest": releases[-1][0], "releases": releases, "modules": mods, "top": top, "alias": alias}
for key in ("utils", "file_utils"):
    names = sorted({n for t in tags for n in H[key].get(t, [])})
    out[key] = {n: ranges([(i, (n in H[key][t]) if t in H[key] else False) for i, t in enumerate(tags)]) for n in names}
    out[key + "_since"] = min(i for i, t in enumerate(tags) if t in H[key])
    gone = [i for i, t in enumerate(tags) if t not in H[key] and i > out[key + "_since"]]
    out[key + "_until"] = gone[0] if gone else 0
out["lazy_since"] = min(i for i, t in enumerate(tags) if H["top"][t]["kind"] == "lazy")
out["scan_since"] = tags.index(H["scan_models"][0])
json.dump(out, sys.stdout, separators=(",", ":"), sort_keys=True)
