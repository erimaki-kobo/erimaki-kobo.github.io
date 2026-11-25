#!/usr/bin/env python3
"""Build en/scikit-image-removed-name-lookup/ (index.html and skimage_names.json).

Usage: python3 -I build_page.py probes/ notes.json pypi.json out_dir PUBLISHED MODIFIED
probes/: dir_<v>.json (public names, __all__, submodule files), get_<v>.json (getattr, or import for a submodule, of the union in each
release), msg_<v>.json (deprecation text in the last release before each removal), sig_<v>.json (parameters and deprecation wrappers of
every public function), kw_<v>.json (real calls with old and new spellings, and result digests).
notes.json: replacements for the few removals scikit-image gave no text for. ASCII only; the facts the prose names are asserted.
style.css is shared with .github/llama-args.
"""
import html, json, os, re, sys
from pathlib import Path

PD, PRE, P = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
out_dir, PUB, MOD = Path(sys.argv[4]), sys.argv[5], sys.argv[6]
HERE = Path(__file__).resolve().parent
e = html.escape
key = lambda v: tuple(int(x) for x in v.split("."))
VS = sorted((f[4:-5] for f in os.listdir(PD) if f.startswith("get_") and f.endswith(".json")), key=key)
ld_ = lambda pre, v: json.load(open(os.path.join(PD, "%s_%s.json" % (pre, v))))
G = {v: ld_("get", v)["get"] for v in VS}
DIRS = {v: ld_("dir", v) for v in VS}
SIG = {v: ld_("sig", v)["sig"] for v in VS}
KW = {v: ld_("kw", v) for v in VS}
MSG = {f[4:-5]: json.load(open(os.path.join(PD, f))) for f in os.listdir(PD) if f.startswith("msg_") and f.endswith(".json")}
DATE = {v: min(f["upload_time"] for f in P["releases"][v])[:10] for v in VS}
YANKED = [v for v in VS if all(f.get("yanked") for f in P["releases"][v])]
LATEST = VS[-1]
NOISE = {"setup", "conftest", "scripts", "brief_pythran"}   # build files, and a compiled helper nobody imports
STD = re.compile(r"has no attribute '|No module named '|^AttributeError: No skimage[\w.]* attribute ")


def clean(msg):
    msg = " ".join(msg.replace("``", "`").split())
    return re.sub(r"^(DEPRECATED|deprecation warning): ", "", msg)


# ---- removed names
ROWS = {}
for k in G[LATEST]:
    for n in sorted(G[LATEST][k]):
        seq = [("warn" if G[v][k][n]["warn"] else "ok") if G[v][k][n]["ok"] else "gone" for v in VS]
        if seq[-1] != "gone" or all(s == "gone" for s in seq):
            continue
        i = max(j for j in range(len(VS)) if seq[j] != "gone") + 1
        last, rem = VS[i - 1], VS[i]
        is_mod = bool(G[last][k][n].get("module")) or n in DIRS[last]["submodules"].get(k, [])
        in_all = n in (DIRS[last]["all"].get(k) or [])
        msg = src = None
        acc = next((G[v][k][n]["warn"] for v in reversed(VS[:i]) if G[v][k][n]["warn"]), None)
        err = G[rem][k][n].get("error") or ""
        if STD.search(err) or not err:   # a submodule: the error its own import raises in the release that removed it
            err = DIRS[rem]["import_errors"].get("%s.%s" % (k, n), err)
        if acc:
            msg, src = acc[0][1], "scikit-image's warning on import"
        elif n in MSG.get(last, {}).get(k, {}):
            msg, src = MSG[last][k][n], "scikit-image's deprecation text in %s" % last
            if msg.endswith(" [found by text search]"):
                msg = msg[:-len(" [found by text search]")]
        elif err and not STD.search(err):
            msg, src = err.split(": ", 1)[1], "scikit-image's error text in %s" % rem
        if n in NOISE or not (in_all or is_mod or msg):
            continue
        gaps = [VS[j] for j in range(1, i) if seq[j] == "gone" and any(s != "gone" for s in seq[:j])]
        ROWS["%s.%s" % (k, n)] = {"obj": k, "name": n, "seq": seq, "removed": rem, "last": last, "fix": clean(msg) if msg else None, "src": src, "module": is_mod, "gaps": gaps, "eq": None}
for r in ROWS.values():   # no text: the same name is public in another module in the release that removed it
    if r["fix"] or r["module"]:
        continue
    alive = [k2 for k2 in G[LATEST] if k2 != r["obj"] and r["name"] in (DIRS[r["removed"]]["all"].get(k2) or []) and G[r["removed"]][k2][r["name"]]["ok"] and G[LATEST][k2][r["name"]]["ok"]]
    if alive:
        r["fix"], r["src"] = "Import %s from %s (there from %s to %s)." % (r["name"], alive[0], next(v for v in VS if G[v][alive[0]][r["name"]]["ok"]), LATEST), "this page's data"
for kk, x in PRE["notes"].items():
    k, n = kk.split("|")
    r = ROWS["%s.%s" % (k, n)]
    assert not r["fix"], (kk, r["fix"])
    r["fix"], r["src"] = x, "our note"
for r in ROWS.values():   # still no text: the text for the module the name was in
    par = ROWS.get(r["obj"])
    if not r["fix"] and par and par["fix"] and par["removed"] == r["removed"]:
        r["fix"], r["src"] = par["fix"], par["src"] + ", for the whole module"
R = lambda k, n: ROWS["%s.%s" % (k, n)]

# ---- same-result checks (digest of the old spelling's result against the new spelling's)
def eq_status(label):
    """('same', where) if a release ran both with equal digests, or the last old result equals the first new one across releases."""
    both = [v for v in VS if not str(KW[v]["eq"][label]["old"]).startswith("ERR") and not str(KW[v]["eq"][label]["new"]).startswith("ERR")]
    if both:
        same = [v for v in both if KW[v]["eq"][label]["old"] == KW[v]["eq"][label]["new"]]
        return ("same", "%s to %s" % (same[0], same[-1]) if len(same) > 1 else same[0]) if len(same) == len(both) else ("differs", ", ".join(v for v in both if v not in same))
    olds = [v for v in VS if not str(KW[v]["eq"][label]["old"]).startswith("ERR")]
    news = [v for v in VS if not str(KW[v]["eq"][label]["new"]).startswith("ERR")]
    if olds and news:
        return ("same", "%s against %s" % (olds[-1], news[0])) if KW[olds[-1]]["eq"][label]["old"] == KW[news[0]]["eq"][label]["new"] else ("differs", "%s against %s" % (olds[-1], news[0]))
    return ("norun", "")


EQSKIP = {"feature.structure_tensor_eigvals | feature.structure_tensor_eigenvalues"}   # a tuple of arrays against one stacked array: not comparable by digest
EQ = {lab: eq_status(lab) for lab in KW[LATEST]["eq"] if lab not in EQSKIP}
EQNAME = {"draw.circle(5, 5, 2) | draw.disk((5, 5), 2)": "skimage.draw.circle", "morphology.selem.disk(2) | morphology.disk(2)": "skimage.morphology.selem",
          "external.tifffile.imread | tifffile.imread": "skimage.external.tifffile"}
EQARG = {"gaussian multichannel=True | channel_axis=-1": "multichannel", "gaussian multichannel=False | channel_axis=None": "multichannel", "rescale multichannel=True | channel_axis=-1": "multichannel",
         "structural_similarity multichannel=True | channel_axis=-1": "multichannel", "binary_erosion selem= | footprint=": "selem", "dilation selem= | footprint=": "selem",
         "rank.mean selem= | footprint=": "selem", "label neighbors=8 | connectivity=2": "neighbors", "label neighbors=4 | connectivity=1": "neighbors",
         "richardson_lucy iterations=2 | num_iter=2": "iterations", "gaussian output= | out=": "output"}
for lab, st in EQ.items():
    if lab in EQARG:
        continue
    rk = EQNAME.get(lab) or "skimage." + lab.split(" | ")[0]
    assert rk in ROWS, (lab, rk)
    ROWS[rk]["eq"] = [st[0], st[1], lab.split(" | ")[1]]

# ---- removed arguments
def accepts(v, m, n, p):
    d = SIG[v].get(m, {}).get(n)
    if d is None:
        return None
    for h in d["h"]:   # a deprecation wrapper names it: accepted, with a warning
        if p in (h.get("kwarg_mapping") or {}) or (h["type"] == "deprecate_multichannel_kwarg" and p == "multichannel"):
            return "map"
        if h.get("arg_name") == p or h.get("deprecated_name") == p:
            return "map"
    if p in d["p"]:
        return "sig"
    return "kwargs" if d["kw"] else ""


ARGS = []
for m in sorted({m for v in VS for m in SIG[v]}):
    for n in sorted({n for v in VS for n in SIG[v].get(m, {})}):
        ps, new, helpmsg = [], {}, {}
        for v in VS:
            d = SIG[v].get(m, {}).get(n) or {"p": [], "h": []}
            for p in d["p"]:
                if p not in ps:
                    ps.append(p)
            for h in d["h"]:
                mp = dict(h.get("kwarg_mapping") or {})
                if h["type"] == "deprecate_multichannel_kwarg":
                    mp.setdefault("multichannel", "channel_axis")
                if h.get("deprecated_name") and h.get("new_name"):
                    mp[h["deprecated_name"]] = h["new_name"]
                if h.get("arg_name"):
                    mp.setdefault(h["arg_name"], None)
                    if h.get("help_msg"):
                        helpmsg[h["arg_name"]] = h["help_msg"]
                for p, q in mp.items():
                    if p not in ps:
                        ps.append(p)
                    if q:
                        new[p] = q
        for p in ps:
            seq = [accepts(v, m, n, p) for v in VS]
            live = [j for j in range(len(VS)) if seq[j] is not None]
            if not live or seq[live[-1]] != "" or not any(seq[j] for j in live):
                continue
            lastok = max(j for j in live if seq[j])
            rem = next(VS[j] for j in live if j > lastok)
            wr = [VS[j] for j in live if seq[j] == "map"]
            sg = [VS[j] for j in live if seq[j] == "sig"]
            ARGS.append({"mod": m, "fn": n, "p": p, "new": new.get(p), "removed": rem, "sig": [sg[0], sg[-1]] if sg else None, "map": [wr[0], wr[-1]] if wr else None, "text": clean(helpmsg[p]) if helpmsg.get(p) else None, "called": False})
AR = {(a["mod"], a["fn"], a["p"]): a for a in ARGS}
# the rule (not in the signature, no wrapper, no **kwargs -> TypeError) against real calls
n_rule = 0
for lab in KW[LATEST]["old"]:
    mm = re.match(r"^([\w.]+)\.(\w+)\((\w+)=\)$", lab)
    if not mm:
        continue
    m, n, p = "skimage." + mm.group(1), mm.group(2), mm.group(3)
    for v in VS:
        a, c = accepts(v, m, n, p), KW[v]["calls"][lab]
        if a is None or a == "kwargs":
            continue
        raised = (not c["ok"]) and ("unexpected keyword argument '%s'" % p) in c["error"]
        assert raised == (a == ""), (lab, v, a, c)
        n_rule += 1
        if (m, n, p) in AR:
            AR[(m, n, p)]["called"] = True
            if c["ok"] and c.get("warn") and p in c["warn"]:
                AR[(m, n, p)]["text"] = clean(c["warn"])
for a in ARGS:
    if not a["new"] and a["text"]:
        mm = re.search(r"[Uu]se (?:the parameter )?[`']?(\w+)[`']? (?:argument )?instead", a["text"])
        if mm and mm.group(1) != a["p"]:
            a["new"] = mm.group(1)
for a in ARGS:   # the same function exported from a second module
    for b in ARGS:
        if b is not a and b["fn"] == a["fn"] and b["p"] == a["p"] and b["removed"] == a["removed"]:
            a["new"], a["text"] = a["new"] or b["new"], a["text"] or b["text"]
GROUPS = {}
for a in ARGS:
    GROUPS.setdefault((a["p"], a["new"] or "", a["removed"]), []).append(a)
argeq = {}
for lab, p in EQARG.items():
    argeq.setdefault(p, []).append((lab, EQ[lab]))

# ---- deprecated in the latest release (still works, warns)
DEPF, DEPP = [], []
for m in sorted(SIG[LATEST]):
    for n, d in sorted(SIG[LATEST][m].items()):
        for h in d["h"]:
            if h["type"] == "deprecate_func":
                DEPF.append((m, n, h.get("deprecated_version"), h.get("removed_version"), h.get("hint")))
            elif h["type"] == "deprecate_parameter":
                DEPP.append((m, n, h.get("deprecated_name"), h.get("new_name"), h.get("start_version"), h.get("stop_version")))

# ---- facts the prose names
for k, n, v in [("skimage.measure", "compare_ssim", "0.18.0"), ("skimage.measure", "compare_psnr", "0.18.0"), ("skimage.measure", "compare_mse", "0.18.0"), ("skimage.measure", "compare_nrmse", "0.18.0"),
                ("skimage.feature", "greycomatrix", "0.20.0"), ("skimage.feature", "greycoprops", "0.20.0"), ("skimage.color", "rgb2grey", "0.19.0"), ("skimage.color", "grey2rgb", "0.19.0"),
                ("skimage.draw", "circle", "0.19.0"), ("skimage.morphology", "selem", "0.20.0"), ("skimage.morphology", "watershed", "0.19.0"), ("skimage.feature", "register_translation", "0.19.0"),
                ("skimage.util", "pad", "0.19.0"), ("skimage.measure", "marching_cubes_lewiner", "0.19.0"), ("skimage", "viewer", "0.20.0"), ("skimage.future", "graph", "0.20.0"),
                ("skimage.future.graph", "rag_mean_color", "0.20.0"), ("skimage.external", "tifffile", "0.17.1"), ("skimage", "external", "0.17.1"), ("skimage.filters", "inverse", "0.22.0"),
                ("skimage.feature", "plot_matches", "0.25.0"), ("skimage.morphology", "skeletonize_3d", "0.25.0"), ("skimage.transform", "match_histograms", "0.18.0"),
                ("skimage.viewer", "ImageViewer", "0.20.0"), ("skimage.morphology", "grey", "0.20.0")]:
    assert R(k, n)["removed"] == v, (k, n, R(k, n)["removed"])
for k, n, want in [("skimage.measure", "compare_ssim", "skimage.metrics.structural_similarity"), ("skimage.measure", "compare_psnr", "skimage.metrics.peak_signal_noise_ratio"),
                   ("skimage.feature", "greycomatrix", "skimage.feature.graycomatrix"), ("skimage.feature", "greycoprops", "skimage.feature.graycoprops"), ("skimage.color", "rgb2grey", "rgb2gray"),
                   ("skimage.draw", "circle", "draw.disk"), ("skimage.morphology", "selem", "skimage.morphology.footprints"), ("skimage.morphology", "watershed", "skimage.segmentation.watershed"),
                   ("skimage.feature", "register_translation", "skimage.registration.phase_cross_correlation"), ("skimage.util", "pad", "numpy.pad"), ("skimage.measure", "marching_cubes_lewiner", "marching_cubes"),
                   ("skimage", "viewer", "visualization.html"), ("skimage.future", "graph", "skimage.graph"), ("skimage.future.graph", "rag_mean_color", "skimage.graph"),
                   ("skimage.filters", "inverse", "skimage.filters.filter_inverse"), ("skimage.feature", "plot_matches", "skimage.feature.plot_matched_features"),
                   ("skimage.morphology", "skeletonize_3d", "skimage.morphology.skeletonize"), ("skimage.transform", "match_histograms", "skimage.exposure.match_histograms")]:
    assert want in (R(k, n)["fix"] or ""), (k, n, R(k, n)["fix"])
for lab in ["measure.compare_ssim | metrics.structural_similarity", "measure.compare_psnr | metrics.peak_signal_noise_ratio", "color.rgb2grey | color.rgb2gray", "feature.greycomatrix | feature.graycomatrix",
            "feature.greycoprops | feature.graycoprops", "draw.circle(5, 5, 2) | draw.disk((5, 5), 2)", "morphology.watershed | segmentation.watershed", "util.pad | numpy.pad",
            "gaussian multichannel=True | channel_axis=-1", "gaussian multichannel=False | channel_axis=None", "binary_erosion selem= | footprint=", "label neighbors=8 | connectivity=2",
            "label neighbors=4 | connectivity=1", "richardson_lucy iterations=2 | num_iter=2", "morphology.selem.disk(2) | morphology.disk(2)", "future.graph.rag_mean_color | graph.rag_mean_color",
            "external.tifffile.imread | tifffile.imread"]:
    assert EQ[lab][0] == "same", (lab, EQ[lab], {v: KW[v]["eq"][lab] for v in VS})
for m, n, p, new, v in [("skimage.filters", "gaussian", "multichannel", "channel_axis", "0.20.0"), ("skimage.morphology", "binary_erosion", "selem", "footprint", "0.20.0"),
                        ("skimage.measure", "label", "neighbors", "connectivity", "0.18.0"), ("skimage.measure", "label", "input", "label_image", "0.20.0"),
                        ("skimage.restoration", "richardson_lucy", "iterations", "num_iter", "0.20.0"), ("skimage.segmentation", "active_contour", "max_iterations", "max_num_iter", "0.20.0"),
                        ("skimage.filters", "gaussian", "output", "out", "0.25.0"), ("skimage.feature", "peak_local_max", "indices", None, "0.20.0"),
                        ("skimage.morphology", "remove_small_objects", "in_place", "out", "0.20.0")]:
    a = AR[(m, n, p)]
    assert a["removed"] == v and a["new"] == new, (m, n, p, a)
assert AR[("skimage.filters", "gaussian", "multichannel")]["map"] == ["0.19.0", "0.19.3"] and AR[("skimage.morphology", "binary_erosion", "selem")]["map"] == ["0.19.0", "0.19.3"]
for v in VS:
    assert KW[v]["deps"]["tifffile"] == (key(v) >= key("0.17.1")), (v, KW[v]["deps"])
for n in ("structural_similarity", "peak_signal_noise_ratio", "mean_squared_error", "normalized_root_mse"):
    assert all(G[v]["skimage.metrics"][n]["ok"] for v in VS), n
assert G[LATEST]["skimage.exposure"]["match_histograms"]["ok"] and G[LATEST]["skimage.morphology"]["footprints"]["ok"] and not G["0.18.3"]["skimage.morphology"]["footprints"]["ok"]
assert G["0.19.0"]["skimage.feature"]["graycomatrix"]["ok"] and not G["0.18.3"]["skimage.feature"]["graycomatrix"]["ok"]
assert G["0.17.1"]["skimage.draw"]["disk"]["ok"] and not G["0.16.2"]["skimage.draw"]["disk"]["ok"]
assert all(KW[v]["calls"]["filters.gaussian(channel_axis=)"]["ok"] == (key(v) >= key("0.19.0")) for v in VS)
assert all(KW[v]["calls"]["morphology.binary_erosion(footprint=)"]["ok"] == (key(v) >= key("0.19.0")) for v in VS)
SSIM = "measure.compare_ssim | metrics.structural_similarity"
for v in VS:   # structural_similarity on float images without data_range: runs up to 0.19.3, ValueError from 0.20.0
    x = str(KW[v]["eq"][SSIM]["new"])
    assert (x.startswith("ERR ValueError") and "data_range" in x) == (key(v) >= key("0.20.0")) and (x.startswith("ERR") == (key(v) >= key("0.20.0"))), (v, x)
    assert KW[v]["deps"]["matplotlib"], v
assert G["0.19.0"]["skimage.morphology"]["footprints"]["ok"]
MCF = {a["fn"] for a in ARGS if a["p"] == "multichannel" and a["removed"] == "0.20.0"}
assert {"gaussian", "rescale", "slic", "hog", "denoise_tv_chambolle", "pyramid_gaussian"} <= MCF and "structural_similarity" not in MCF, sorted(MCF)
for v in VS:   # structural_similarity takes **kwargs: from 0.20.0 multichannel=True is swallowed and a color image fails on win_size
    c = KW[v]["calls"]["metrics.structural_similarity(multichannel=)"]
    assert (not c["ok"] and c["error"].startswith("ValueError: win_size exceeds image extent")) == (key(v) >= key("0.20.0")), (v, c)
    assert c["ok"] == (key(v) < key("0.20.0")) and KW[v]["calls"]["metrics.structural_similarity(channel_axis=)"]["ok"] == (key(v) >= key("0.19.0")), (v, c)
    assert SIG[v]["skimage.metrics"]["structural_similarity"]["kw"], v
OLDER = sorted((v for v in P["releases"] if re.match(r"^\d+(\.\d+)+$", v) and key(v) < key(VS[0]) and P["releases"][v]), key=key)
assert OLDER and not any(re.search(r"cp3(8|9|1\d)", f["filename"]) for v in OLDER for f in P["releases"][v]), OLDER
assert YANKED == ["0.23.0"], YANKED
DR = next((v for v in VS if str(KW[v]["eq"]["measure.compare_ssim | metrics.structural_similarity"]["new"]).startswith("ERR ValueError") and "data_range" in KW[v]["eq"]["measure.compare_ssim | metrics.structural_similarity"]["new"]), None)
print("data_range needed from", DR, "|", KW[LATEST]["eq"]["measure.compare_ssim | metrics.structural_similarity"]["new"], file=sys.stderr)
n_mc = sum(1 for a in ARGS if a["p"] == "multichannel" and a["removed"] == "0.20.0")
n_se = sum(1 for a in ARGS if a["p"] == "selem" and a["removed"] == "0.20.0")
assert n_mc >= 20 and n_se >= 40, (n_mc, n_se)
rest = list(ROWS.values())
n_fix = sum(1 for r in rest if r["fix"] and r["src"] not in ("this page's data", "our note"))
n_same = sum(1 for r in rest if r["eq"] and r["eq"][0] == "same")
n_names = sum(len(x) for x in G[VS[0]].values())
n_fn = sum(len(x) for x in SIG[LATEST].values())
CODE = {"ok": "o", "warn": "w", "gone": "g"}
DATA = {"releases": [[v, DATE[v], DIRS[v]["python"], DIRS[v]["numpy"]] for v in VS], "yanked": YANKED,
        "rows": {kk: dict(r, seq="".join(CODE[s] for s in r["seq"])) for kk, r in ROWS.items()},
        "args": [[a["mod"], a["fn"], a["p"], a["new"], a["removed"], a["sig"], a["map"], a["text"], a["called"]] for a in ARGS],
        "argeq": {p: [[lab, st[0], st[1]] for lab, st in x] for p, x in argeq.items()},
        "names": {k: sorted(set().union(*(DIRS[v]["dir"].get(k, []) for v in VS)) | set().union(*(DIRS[v]["submodules"].get(k, []) for v in VS))) for k in G[LATEST]},
        "latest_names": {k: sorted(n for n in G[LATEST][k] if G[LATEST][k][n]["ok"]) for k in G[LATEST]}}
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json
URL = "https://erimaki-kobo.github.io/en/scikit-image-removed-name-lookup/"
TITLE = "cannot import name 'compare_ssim' from 'skimage.measure': fix"
H1 = "ImportError: cannot import name 'compare_ssim' from 'skimage.measure' (or 'greycomatrix', TypeError: unexpected keyword argument 'multichannel', 'selem'): which scikit-image release removed it and what to use"
DESC = ("scikit-image 0.18 removed compare_ssim (use skimage.metrics.structural_similarity); 0.20 removed multichannel= (channel_axis=) and selem= (footprint=). %d releases run." % len(VS))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))


def eq_note(r):
    if not r["eq"]:
        return ""
    if r["eq"][0] == "same":
        return " <em>(same result as %s, run in %s)</em>" % (e(r["eq"][2]), e(r["eq"][1]))
    if r["eq"][0] == "differs":
        return " <em>(result differs from %s, run in %s)</em>" % (e(r["eq"][2]), e(r["eq"][1]))
    return ""


tab = []
for r in sorted(rest, key=lambda x: (key(x["removed"]), x["obj"], x["name"].lower())):
    tab.append("<tr><td><code>%s.%s</code>%s</td><td>%s</td><td>%s%s%s</td></tr>" % (e(r["obj"]), e(r["name"]), " (module)" if r["module"] else "", r["removed"], e(r["fix"] or ""),
                                                                           " <em>(our note)</em>" if r["src"] == "our note" else "", eq_note(r)))
tab_html = "\n".join(tab)
short = lambda m: m[len("skimage."):] if m.startswith("skimage.") else m
atab = []
for (p, new, rem), rows in sorted(GROUPS.items(), key=lambda x: (key(x[0][2]), -len(x[1]), x[0][0])):
    maps = sorted({tuple(a["map"]) for a in rows if a["map"]})
    warn = "; ".join("%s to %s" % m_ if m_[0] != m_[1] else m_[0] for m_ in maps)
    fns = ", ".join("%s.%s" % (short(a["mod"]), a["fn"]) for a in rows)
    txt = next((a["text"] for a in rows if a["text"]), "")
    atab.append("<tr><td><code>%s=</code></td><td>%s%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(p), ("<code>%s=</code>" % e(new)) if new else "", (" " if new else "") + ("<span class=\"note\">%s</span>" % e(txt) if txt and not new else ""), rem, e(warn), e(fns)))
atab_html = "\n".join(atab)
dtab = ["<tr><td><code>%s.%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(m), e(n), e(str(dv or "")), e(str(rv or "")), e(clean(h or ""))) for m, n, dv, rv, h in DEPF]
dtab += ["<tr><td><code>%s.%s(%s=)</code></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(m), e(n), e(p), e(str(sv or "")), e(str(ev or "")), ("Use %s= instead." % e(q)) if q else "") for m, n, p, q, sv, ev in DEPP]
dtab_html = "\n".join(dtab)
mc_eq = "; ".join("%s (%s)" % (lab.replace(" | ", " and "), st[1]) for lab, st in argeq["multichannel"] if st[0] == "same")
FAQ = [
    ("How do I fix \"cannot import name 'compare_ssim' from 'skimage.measure'\"?",
     "scikit-image 0.18.0 (%s) removed compare_ssim, compare_psnr, compare_mse and compare_nrmse from skimage.measure; 0.16.2 to 0.17.2 warn when they are called. "
     "Use from skimage.metrics import structural_similarity, peak_signal_noise_ratio, mean_squared_error, normalized_root_mse. On the same two images "
     "compare_ssim and structural_similarity returned the same number (run in %s). skimage.metrics is in every release from %s on.%s"
     % (DATE["0.18.0"], EQ["measure.compare_ssim | metrics.structural_similarity"][1], VS[0],
        (" From %s, structural_similarity on float images raises a ValueError unless you pass data_range= (data_range=1.0 for images scaled 0 to 1); up to 0.19.3 the same call ran without it." % DR) if DR else "")),
    ("How do I fix \"TypeError: ... got an unexpected keyword argument 'multichannel'\"?",
     "scikit-image 0.20.0 (%s) removed the multichannel argument from %d functions (gaussian, rescale, pyramid_gaussian, slic, hog, denoise_tv_chambolle and others); 0.19.0 to 0.19.3 accept it with a warning. "
     "Use channel_axis: multichannel=True becomes channel_axis=-1, and multichannel=False becomes channel_axis=None. Same output for each pair run: %s. "
     "channel_axis itself only exists from 0.19.0, so code that must run on both sides needs a version check. "
     "structural_similarity is a special case: it takes **kwargs, so from 0.20.0 multichannel=True is not rejected but ignored, and a color image then fails with "
     "\"ValueError: win_size exceeds image extent\" (run with a 32x32x3 image in 0.20.0 to %s). Pass channel_axis=-1 there too." % (DATE["0.20.0"], n_mc, mc_eq, LATEST)),
    ("How do I fix \"unexpected keyword argument 'selem'\" or \"No module named 'skimage.morphology.selem'\"?",
     "scikit-image 0.20.0 removed the selem argument from %d functions (skimage.morphology, skimage.filters.rank and a few others), and the skimage.morphology.selem module; 0.19.0 to 0.19.3 accept both with a warning. "
     "Write footprint=... instead of selem=..., and import disk, ball and the other shapes from skimage.morphology (or skimage.morphology.footprints, there from 0.19.0). footprint= does not exist before 0.19.0." % n_se),
    ("How do I fix \"module 'skimage.feature' has no attribute 'greycomatrix'\"?",
     "scikit-image 0.20.0 removed greycomatrix and greycoprops; 0.19.0 to 0.19.3 have both spellings and warn on the old one. Use graycomatrix and graycoprops (American spelling), "
     "which take the same arguments and gave the same matrix in 0.19.x. They exist from 0.19.0, so on 0.18 and older the grey spelling is the only one."),
    ("How do I fix \"No module named 'skimage.viewer'\" or \"No module named 'skimage.future.graph'\"?",
     "scikit-image 0.20.0 removed both. skimage.future.graph moved to skimage.graph: from skimage import graph, then graph.rag_mean_color, graph.cut_normalized and the rest "
     "(same region graph for the same image in 0.19.3 and 0.20.0). skimage.viewer has no replacement inside scikit-image; its own message points to the visualization page of the user guide."),
    ("How do I fix \"cannot import name 'circle' from 'skimage.draw'\"?",
     "scikit-image 0.19.0 (%s) removed draw.circle; 0.17.1 to 0.18.3 warn. Use draw.disk, which takes the center as one tuple: circle(r, c, radius) becomes disk((r, c), radius). "
     "Both gave the same pixels in %s. disk does not exist in 0.16.2." % (DATE["0.19.0"], EQ["draw.circle(5, 5, 2) | draw.disk((5, 5), 2)"][1])),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["scikit-image", "ImportError", "TypeError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "scikit-image removed name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError, AttributeError or TypeError from scikit-image and get the release that removed the name or argument, and what to use instead (%s to %s)." % (VS[0], LATEST),
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "scikit-image names and arguments by release", "url": URL + "skimage_names.json", "dateModified": MOD,
     "description": "The public names of %d scikit-image modules and the parameters of their functions in %d installed scikit-image releases (%s to %s), with the deprecation text before each removal." % (len(G[LATEST]), len(VS), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "skimage_names.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\ntd code,p code,li code,h1,h2,h3{overflow-wrap:anywhere}main p,main li,td{overflow-wrap:break-word}\n.s-ok{color:var(--ok,#1a7f37)}.s-warn{color:#9a6700}.s-gone{color:#cf222e}\n"
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'compare_ssim' from 'skimage.measure'", "compare_ssim"),
      ("TypeError: gaussian() got an unexpected keyword argument 'multichannel'", "multichannel="),
      ("AttributeError: module 'skimage.feature' has no attribute 'greycomatrix'", "greycomatrix"),
      ("TypeError: binary_erosion() got an unexpected keyword argument 'selem'", "selem="),
      ("ModuleNotFoundError: No module named 'skimage.viewer'", "skimage.viewer"),
      ("ImportError: cannot import name 'circle' from 'skimage.draw'", "draw.circle")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
by_py = {}
for v in VS:
    by_py.setdefault(DIRS[v]["python"].rsplit(".", 1)[0], []).append(v)
rel_list = "; ".join("%s (Python %s)" % (", ".join(vs), py) for py, vs in by_py.items())
by_np = {}
for v in VS:
    by_np.setdefault(DIRS[v]["numpy"], []).append(v)
np_list = "; ".join("NumPy %s for %s" % (npv, vs[0] if len(vs) == 1 else "%s to %s" % (vs[0], vs[-1])) for npv, vs in by_np.items())
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var LBL = {ok: "has it", warn: "has it, warns", gone: "not there"}, LAST = D.releases[D.releases.length - 1][0], FIRST = D.releases[0][0];
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  var M = "(skimage(?:\\.\\w+)*)";
  var PARAMS = {}, FUNCS = {};
  D.args.forEach(function (a) { PARAMS[a[2]] = 1; FUNCS[a[1]] = 1; });
  function find(t) {
    var out = [], m;
    var re = new RegExp("cannot import name '(\\w+)' from '" + M + "'|module '" + M + "' has no attribute '(\\w+)'|" +
      "from " + M + " import ([\\w ,()]+)|No module named '" + M + "'|(?:\\b(\\w+)\\.)?(\\w+)\\(\\) got an unexpected keyword argument '(\\w+)'|\\b" + M + "\\b", "g");
    while ((m = re.exec(t))) {
      if (m[1]) out.push(["n", m[2], m[1]]);
      else if (m[3]) out.push(["n", m[3], m[4]]);
      else if (m[5]) m[6].replace(/[()]/g, " ").split(",").forEach(function (p) { var n = p.trim().split(/\s+as\s+/)[0]; if (n) out.push(["n", m[5], n]); });
      else if (m[7]) { var s = m[7].split("."); if (s.length > 1) out.push(["n", s.slice(0, -1).join("."), s[s.length - 1]]); }
      else if (m[10]) out.push(["a", m[9], m[10]]);
      else if (m[11]) { var d = m[11].split("."); if (d.length > 2) out.push(["n", d.slice(0, -1).join("."), d[d.length - 1], 1]); }
    }
    if (!out.some(function (x) { return x[0] === "a"; })) {   // pasted code: old keyword names
      var seen = {}, km, kre = /\b(\w+)\s*=(?!=)/g;
      while ((km = kre.exec(t))) if (PARAMS[km[1]] && !seen[km[1]]) {
        seen[km[1]] = 1;
        var fm, fre = /\b(\w+)\s*\(/g, hit = false;
        while ((fm = fre.exec(t))) if (FUNCS[fm[1]] && D.args.some(function (a) { return a[1] === fm[1] && a[2] === km[1]; })) { out.push(["a", fm[1], km[1]]); hit = true; }
        if (!hit && (km[1] === "multichannel" || km[1] === "selem")) out.push(["a", "", km[1]]);
      }
    }
    return out;
  }
  function span(x) { return x ? (x[0] === x[1] ? x[0] : x[0] + " to " + x[1]) : ""; }
  function argHtml(fn, p) {
    var rs = D.args.filter(function (a) { return a[2] === p && (!fn || a[1] === fn); }), fam = D.args.filter(function (a) { return a[2] === p; });
    if (!rs.length && fam.length) rs = fam;
    if (!rs.length) return "<h3><code>" + esc((fn ? fn + "(" : "(") + p + "=)") + "</code></h3><p>No function in the scikit-image modules this page covers lost an argument named " + esc(p) + " between " + esc(FIRST) + " and " + esc(LAST) + ".</p>";
    var by = {}, h = "";
    rs.forEach(function (a) { var k = a[4] + "|" + (a[3] || ""); (by[k] = by[k] || []).push(a); });
    Object.keys(by).forEach(function (k) {
      var g = by[k], a = g[0], one = g.length === 1;
      h += "<h3><code>" + esc(one ? a[1] + "(" + p + "=)" : p + "=") + "</code></h3><p><strong>TypeError from scikit-image " + esc(a[4]) + "</strong>";
      if (a[3]) h += ". <strong>Instead:</strong> <code>" + esc(a[3]) + "=</code>";
      h += ".";
      if (a[6]) h += " " + esc(span(a[6])) + " still accept <code>" + esc(p) + "=</code> with a warning.";
      if (a[5]) h += " In the signature in " + esc(span(a[5])) + ".";
      var t = g.filter(function (x) { return x[7]; })[0];
      if (t) h += ' scikit-image\'s warning: "' + esc(t[7]) + '"';
      h += "</p>";
      if (p === "multichannel") h += "<p><code>multichannel=True</code> becomes <code>channel_axis=-1</code>; <code>multichannel=False</code> becomes <code>channel_axis=None</code>.</p>";
      (D.argeq[p] || []).forEach(function (x) { if (x[1] === "same") h += '<p class="note">Same result: ' + esc(x[0].replace(" | ", " and ")) + " (run in " + esc(x[2]) + ").</p>"; });
      h += "<p>" + (one ? "Function: " : g.length + " functions: ") + g.map(function (x) { return "<code>" + esc(x[0] + "." + x[1]) + "</code>"; }).join(", ") + '.</p><p>To keep the old spelling: <code>pip install "scikit-image&lt;' + esc(a[4]) + '"</code></p>';
    });
    return h;
  }
  function show() {
    var h = "", seen = {}, all = Object.keys(D.rows).map(function (k) { return D.rows[k]; });
    find(q.value).forEach(function (t) {
      if (t[0] === "a") { var ak = "a|" + t[1] + "|" + t[2]; if (seen[ak]) return; seen[ak] = 1; h += argHtml(t[1], t[2]); return; }
      var rs = all.filter(function (x) { return x.name === t[2] && x.obj === t[1]; });
      if (!rs.length) {
        if (t[3] || seen["?" + t[1] + "." + t[2]]) return; seen["?" + t[1] + "." + t[2]] = 1;
        var here = (D.latest_names[t[1]] || []).indexOf(t[2]) >= 0;
        var where = Object.keys(D.latest_names).filter(function (k) { return D.latest_names[k].indexOf(t[2]) >= 0; });
        var gone = all.filter(function (x) { return x.name === t[2]; });
        h += "<h3><code>" + esc(t[1] + "." + t[2]) + "</code></h3><p>" +
          (here ? "Not removed: " + esc(t[1] + "." + t[2]) + " is there in " + esc(LAST) + ". If the import fails, the installed scikit-image may be older than the release that added it." :
           where.length ? "Not removed in any release read: " + esc(t[2]) + " is in " + where.map(esc).join(", ") + " in " + esc(LAST) + ", and was not in " + esc(t[1]) + " in any release from " + esc(FIRST) + " on." :
           gone.length ? "" :
           "No scikit-image release from " + esc(FIRST) + " to " + esc(LAST) + " has this name in the modules this page covers (a name removed before " + esc(FIRST) + " is outside the range).") + "</p>";
        if (!here && !where.length && gone.length) rs = gone; else return;
      }
      rs.forEach(function (x) {
        var k = x.obj + "." + x.name; if (seen[k]) return; seen[k] = 1;
        var segs = [], prev = null;
        x.seq.split("").forEach(function (c, i) { var st = {o: "ok", w: "warn", g: "gone"}[c], v = D.releases[i][0]; if (st !== prev) { segs.push([v, st]); prev = st; } else segs[segs.length - 1][2] = v; });
        h += "<h3><code>" + esc(k) + "</code>" + (x.module ? " (module)" : "") + "</h3><p><strong>Removed in scikit-image " + esc(x.removed) + "</strong> (last in " + esc(x.last) + ").";
        if (x.fix) h += " <strong>Instead:</strong> " + esc(x.fix) + ' <span class="note">(' + esc(x.src) + ")</span>";
        if (x.eq && x.eq[0] === "same") h += " Same result as <code>" + esc(x.eq[2]) + "</code> on the same input (run in " + esc(x.eq[1]) + ").";
        if (x.eq && x.eq[0] === "differs") h += " The result was not identical to <code>" + esc(x.eq[2]) + "</code> on the same input (run in " + esc(x.eq[1]) + ").";
        h += '</p><p>To keep it: <code>pip install "scikit-image&lt;' + esc(x.removed) + '"</code></p>';
        h += '<div class="tw"><table><thead><tr><th>scikit-image</th><th>' + esc(k) + "</th></tr></thead><tbody>";
        segs.forEach(function (s) { h += "<tr><td>" + esc(s[0]) + (s[2] ? " to " + esc(s[2]) : "") + '</td><td class="s-' + s[1] + '">' + LBL[s[1]] + "</td></tr>"; });
        h += "</tbody></table></div>";
      });
    });
    if (/win_size exceeds image extent/.test(q.value)) h += "<h3><code>structural_similarity(multichannel=True)</code></h3><p><strong>From scikit-image 0.20.0, <code>multichannel=True</code> is ignored by <code>structural_similarity</code></strong> (the function takes <code>**kwargs</code>, so it is not rejected), and a color image then fails with this ValueError because the channel axis is shorter than the window. <strong>Instead:</strong> pass <code>channel_axis=-1</code> (there from 0.19.0). If you never passed multichannel, the image really is smaller than the 7x7 window: pass a smaller odd <code>win_size</code>.</p>";
    if (!h) h = "<p>Paste the error line, for example cannot import name 'compare_ssim' from 'skimage.measure'.</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.SKI_READY = true;
})();
"""
assert "</script" not in JS
yank_note = (" %s was yanked on PyPI and is included." % ", ".join(YANKED)) if YANKED else ""
page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(TITLE, quote=False)}</title>
<meta name="description" content="{e(DESC)}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESC)}">
<meta property="og:url" content="{URL}">
<style>
{css}</style>
<script type="application/ld+json">{LD}</script>
</head>
<body>
<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>{e(H1, quote=False)}</h1>
<p class="lede"><strong>scikit-image 0.18.0 ({DATE["0.18.0"]}) removed <code>compare_ssim</code>, <code>compare_psnr</code>, <code>compare_mse</code> and <code>compare_nrmse</code> from <code>skimage.measure</code>: import <code>structural_similarity</code>, <code>peak_signal_noise_ratio</code>, <code>mean_squared_error</code> and <code>normalized_root_mse</code> from <code>skimage.metrics</code>. 0.19.0 removed <code>rgb2grey</code> (use <code>rgb2gray</code>), <code>draw.circle</code> (<code>draw.disk</code>) and <code>morphology.watershed</code> (<code>segmentation.watershed</code>). 0.20.0 ({DATE["0.20.0"]}) removed <code>greycomatrix</code> (<code>graycomatrix</code>), <code>skimage.morphology.selem</code>, <code>skimage.viewer</code>, <code>skimage.future.graph</code> (now <code>skimage.graph</code>), and the arguments <code>multichannel=</code> (use <code>channel_axis=</code>) and <code>selem=</code> (use <code>footprint=</code>).</strong> If the error comes from a library you did not write, upgrade that library or pin scikit-image below the release that removed the name. Paste the error below for the release-by-release answer.</p>
<p class="meta">Published {PUB} &middot; {len(VS)} scikit-image releases installed and run, {VS[0]} to {LATEST} &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line, or the old code</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'compare_ssim' from 'skimage.measure'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="skimage_names.json">skimage_names.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which release removed the name, and what replaces it?</h2>
<p><strong>{len(rest)} functions and modules that one scikit-image release has and a later one does not.</strong> "Instead" is scikit-image's own text ({n_fix} of {len(rest)}): its deprecation message in the last release that had the name, or the error it raises afterwards. "Same result" means the old and the new spelling were both run on the same small test image and returned identical output ({n_same} names).</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Removed in</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>

<h2 id="args">Which release removed the argument (<code>unexpected keyword argument</code>)?</h2>
<p><strong>{len(ARGS)} function arguments that stopped being accepted, in {len(GROUPS)} groups.</strong> "TypeError from" is the first release where the function no longer has the argument in its signature and no longer wraps it; "Accepted with a warning" lists the releases whose deprecation wrapper still took the old name (blank: no wrapper was found; the function may still have warned in its own code). The new name is the one scikit-image's wrapper mapped the old name to, or the one its warning names. The 0.19 warnings say the old names "will be removed in version 1.0"; the removal was measured in 0.20.0.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Old argument</th><th>Use instead</th><th>TypeError from</th><th>Accepted with a warning</th><th>Functions</th></tr></thead>
<tbody>
{atab_html}
</tbody></table></div>

<h2 id="next">What does scikit-image {LATEST} warn about now?</h2>
<p><strong>{len(DEPF)} functions and {len(DEPP)} arguments still work in {LATEST} but carry scikit-image's deprecation wrapper</strong>, read from the installed package. The removal release is scikit-image's own plan and may change.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Deprecated since</th><th>Planned removal</th><th>scikit-image's hint</th></tr></thead>
<tbody>
{dtab_html}
</tbody></table></div>

<h2 id="how">How was this measured?</h2>
<p><strong>Each of {len(VS)} scikit-image releases ({VS[0]} to {LATEST}, patch releases included) was installed from PyPI in its own environment; the public names of {len(G[LATEST])} modules (<code>skimage</code> and its subpackages) were listed with <code>dir()</code>, and <code>getattr</code> or an import was run for the union of all {n_names} names in every release.</strong> Releases: {rel_list}.{yank_note} Each ran with a NumPy of its time ({np_list}) and with matplotlib installed. The {len(OLDER)} older releases on PyPI ({OLDER[0]} to {OLDER[-1]}) have no wheel for Python 3.8 or later and were not installed, so a name removed before {VS[0]} is outside this page.</p>
<p>For the arguments, the parameters of every public function and class ({n_fn} in {LATEST}) were read with <code>inspect.signature</code> in each release, together with the deprecation wrappers scikit-image attaches to a function (<code>deprecate_kwarg</code>, <code>deprecate_multichannel_kwarg</code>, <code>remove_arg</code>, <code>deprecate_parameter</code>). An argument is listed when a release accepts it and a later one has neither the parameter, nor a wrapper for it, nor <code>**kwargs</code>. That rule was checked against real calls: {len([x for x in KW[LATEST]["old"] if re.match(r"^[\w.]+\.\w+\(\w+=\)$", x)])} old-argument calls were run in every release, and whether each raised <code>TypeError: ... unexpected keyword argument</code> agreed with the rule in all {n_rule} call-and-release pairs. Arguments passed by position, and arguments a function forwards through <code>**kwargs</code>, are not covered.</p>
<p>The names table keeps names in a module's <code>__all__</code>, submodule files, and anything scikit-image itself deprecated; helpers a module merely imported (<code>np</code>, <code>warn</code>) and the <code>setup.py</code> build files are left out.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The scikit-image packages on <a href="https://pypi.org/project/scikit-image/#history">PyPI</a>, installed and run, and their source as installed; the release dates are PyPI's.</li>
<li>scikit-image's <a href="https://scikit-image.org/docs/stable/release_notes/index.html">release notes</a> (to cross-read the removals).</li>
</ul>
<p>The same data as JSON: <a href="skimage_names.json">skimage_names.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/opencv-removed-name-lookup/">"module 'cv2' has no attribute ..."</a> &middot; <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a> &middot; <a href="/en/scipy-removed-name-lookup/">"cannot import name 'triu' from 'scipy.linalg'"</a> &middot; <a href="/en/matplotlib-removed-name-lookup/">"module 'matplotlib.cm' has no attribute 'get_cmap'"</a>.</p>
</main>
<script type="application/json" id="data">{data_json}</script>
<script>
{JS}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
(out_dir / "skimage_names.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | names %d (own text %d, same result %d) | args %d in %d groups | rule checks %d | deprecated now %d+%d | releases %d" % (
    len(page), len(rest), n_fix, n_same, len(ARGS), len(GROUPS), n_rule, len(DEPF), len(DEPP), len(VS)), file=sys.stderr)
