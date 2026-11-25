#!/usr/bin/env python3
"""Build en/sklearn-removed-name-lookup/ (index.html and sklearn_names.json).

Usage: python3 -I build_page.py probes/ pre22.json pypi.json out_dir PUBLISHED MODIFIED
probes/: dir_<v>.json (public names, __all__ and submodules), get_<v>.json (getattr, or import for a submodule, of the union in
each release), msg_<v>.json (deprecation text in the last release before each removal). pre22.json: removals before 0.22 (pre22.py).
ASCII only; the facts the prose names are asserted. style.css is shared with .github/llama-args.
"""
import __future__, html, json, os, re, sys, typing
from pathlib import Path

PD, PRE, P = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
DATES_EXTRA = ["0.19.2", "0.20.0", "0.21.3"]
out_dir, PUB, MOD = Path(sys.argv[4]), sys.argv[5], sys.argv[6]
HERE = Path(__file__).resolve().parent
e = html.escape
key = lambda v: tuple(int(x) for x in v.split("."))
VS = sorted((f[4:-5] for f in os.listdir(PD) if f.startswith("get_") and f.endswith(".json")), key=key)
G = {v: json.load(open(os.path.join(PD, "get_%s.json" % v)))["get"] for v in VS}
DIRS = {v: json.load(open(os.path.join(PD, "dir_%s.json" % v))) for v in VS}
MSG = {f[4:-5]: json.load(open(os.path.join(PD, f))) for f in os.listdir(PD) if f.startswith("msg_") and f.endswith(".json")}
DATE = {v: min(f["upload_time"] for f in P["releases"][v])[:10] for v in (VS + DATES_EXTRA)}
LATEST = VS[-1]
LAB = lambda k: k.replace(":", ".")
NOISE = set(__future__.all_feature_names) | set(typing.__all__) | set(sys.stdlib_module_names) | {"np", "numpy", "setup", "tests"}


def clean(msg, n):
    msg = msg.replace("%s", n)
    if "{}" in msg:
        msg = msg.replace("{}", n, 1)
    return " ".join(s for s in re.split(r"(?<=\.)\s+", msg) if "{}" not in s and "{...}" not in s).strip()


ROWS = {}
for k in G[VS[-1]]:
    for n in sorted(G[VS[-1]][k]):
        seq = [(v, ("warn" if G[v][k][n]["warn"] else "ok") if G[v][k][n]["ok"] else "gone") for v in VS]
        rem = None
        for i in range(1, len(seq)):
            if seq[i][1] == "gone" and seq[i - 1][1] != "gone":
                rem = (seq[i][0], seq[i - 1][0])
        if rem is None or seq[-1][1] != "gone":
            continue
        last = rem[1]
        allv = DIRS[last]["all"].get(k)
        is_mod = n in DIRS[last]["submodules"].get(k, [])
        if n in NOISE or not (is_mod or k == "sklearn.externals" or (allv is not None and n in allv)):
            continue   # a module the file imported, a helper outside __all__, typing or __future__ names, setup.py
        msg = src = None
        acc = G[last][k][n]["warn"]
        if acc:
            msg, src = acc[0][1], "warning on access in %s" % last
        elif n in MSG.get(last, {}).get(k, {}):
            msg = MSG[last][k][n]
            src = "deprecation text in %s" % last
            if msg.endswith(" [found by text search]"):
                msg, src = msg[:-len(" [found by text search]")], "deprecation text in %s that names it" % last
        if msg:
            msg = clean(msg, n)
        ROWS["%s.%s" % (k, n)] = {"obj": k, "name": n, "seq": [list(s) for s in seq], "removed": rem[0], "last": rem[1], "fix": msg, "src": src, "module": is_mod}
for r in ROWS.values():   # no text: the same name still public in another module of the latest release
    if r["fix"] or r["module"]:
        continue
    alive = [k2 for k2 in G[LATEST] if k2 != r["obj"] and ":" not in k2 and r["name"] in DIRS[LATEST]["all"].get(k2, DIRS[LATEST]["dir"].get(k2, []))
             and G[LATEST][k2].get(r["name"], {}).get("ok")]
    if alive:
        r["fix"] = "From %s import %s (still there in %s)." % (alive[0], r["name"], LATEST)
        r["src"] = "this page's data"
for kk, x in PRE.items():
    ROWS[kk] = {"obj": x["obj"], "name": x["name"], "seq": [[v, "gone"] for v in VS], "removed": x["removed"], "last": x["last"],
                "fix": x["message"], "src": "source of %s (%s)" % (x["last"], x["file"]), "pre": True, "module": bool(x.get("module"))}
R = lambda k, n: ROWS["%s.%s" % (k, n)]
rest = list(ROWS.values())
mods = [r for r in rest if r["module"]]
names_ = [r for r in rest if not r["module"]]
# facts the prose names
for k, n, v in [("sklearn.datasets", "load_boston", "1.2.0"), ("sklearn.metrics", "plot_confusion_matrix", "1.2.0"), ("sklearn.metrics", "plot_roc_curve", "1.2.0"),
                ("sklearn.inspection", "plot_partial_dependence", "1.2.0"), ("sklearn.externals", "joblib", "0.23.0"), ("sklearn.externals", "six", "0.23.0"),
                ("sklearn.ensemble", "forest", "0.24.0"), ("sklearn.tree", "tree", "0.24.0"), ("sklearn.linear_model", "logistic", "0.24.0"),
                ("sklearn.metrics", "scorer", "0.24.0"), ("sklearn.svm", "classes", "0.24.0"), ("sklearn.neighbors", "base", "0.24.0"),
                ("sklearn.datasets", "samples_generator", "0.24.0"), ("sklearn.utils", "testing", "0.24.0"), ("sklearn.utils", "safe_indexing", "0.24.0"),
                ("sklearn.metrics", "SCORERS", "1.3.0"), ("sklearn.utils.metaestimators", "if_delegate_has_method", "1.3.0"),
                ("sklearn.neighbors", "DistanceMetric", "1.3.0"), ("sklearn.metrics", "jaccard_similarity_score", "0.23.0"),
                ("sklearn.metrics", "calinski_harabaz_score", "0.23.0"), ("sklearn", "cross_validation", "0.20.0"), ("sklearn.preprocessing", "Imputer", "0.22")]:
    assert R(k, n)["removed"] == v, (k, n, R(k, n)["removed"])
for k, n, want in [("sklearn.datasets", "load_boston", "ethical"), ("sklearn.metrics", "plot_confusion_matrix", "ConfusionMatrixDisplay"),
                   ("sklearn.externals", "joblib", "joblib"), ("sklearn.ensemble", "forest", "sklearn.ensemble"), ("sklearn.metrics", "SCORERS", "get_scorer_names"),
                   ("sklearn.utils.metaestimators", "if_delegate_has_method", "available_if"), ("sklearn.preprocessing", "Imputer", "SimpleImputer"),
                   ("sklearn", "cross_validation", "model_selection"), ("sklearn.neighbors", "DistanceMetric", "sklearn.metrics")]:
    assert want in (R(k, n)["fix"] or ""), (k, n, R(k, n)["fix"])
m24 = [r for r in mods if r["removed"] == "0.24.0"]
assert len(m24) > 100, len(m24)
n_fix = sum(1 for r in rest if r["fix"] and r["src"] != "this page's data")
n_data = sum(1 for r in rest if r["src"] == "this page's data")
n_runs = sum(len(x) for x in G[VS[0]].values()) * len(VS)
assert all(not DIRS[v]["import_errors"] for v in VS)
CODE = {"ok": "o", "warn": "w", "gone": "g"}
ROWS_OUT = {kk: dict(r, seq="".join(CODE[s[1]] for s in r["seq"])) for kk, r in ROWS.items()}
DATA = {"releases": [[v, DATE[v], DIRS[v]["python"], DIRS[v]["numpy"]] for v in VS], "rows": ROWS_OUT,
        "names": {k: sorted(set().union(*(DIRS[v]["dir"].get(k, []) for v in VS))) for k in G[VS[-1]]}}
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json
URL = "https://erimaki-kobo.github.io/en/sklearn-removed-name-lookup/"
TITLE = "cannot import name 'load_boston' from 'sklearn.datasets' and more: fix"
H1 = "ImportError: cannot import name 'load_boston' (or 'plot_confusion_matrix', 'joblib', any name) from 'sklearn...': which scikit-learn removed it and what to use"
DESC = ("scikit-learn 1.2 removed load_boston and plot_confusion_matrix, 0.24 sklearn.ensemble.forest (old pickles), 0.23 externals.joblib. %d removals, %d releases run."
        % (len(rest), len(VS)))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))

tab = []
for r in sorted(names_ + [m for m in mods if m["removed"] != "0.24.0"], key=lambda x: (key(x["removed"]), x["obj"], x["name"].lower())):
    tab.append("<tr><td><code>%s.%s</code>%s</td><td>%s</td><td>%s</td></tr>" % (e(r["obj"]), e(r["name"]), " (module)" if r["module"] else "", r["removed"], e(r["fix"] or "")))
tab_html = "\n".join(tab)
m24_html = ", ".join("<code>%s.%s</code>" % (e(r["obj"].replace("sklearn.", "")), e(r["name"])) for r in sorted(m24, key=lambda x: (x["obj"], x["name"])))
FAQ = [
    ("How do I fix \"cannot import name 'load_boston' from 'sklearn.datasets'\"?",
     "scikit-learn 1.2.0 (%s) removed load_boston; 1.0 and 1.1 warned that the dataset has an ethical problem. The warning suggests "
     "fetch_california_housing() or the Ames housing data (fetch_openml(name=\"house_prices\", as_frame=True)), and shows how to read the "
     "original file from lib.stat.cmu.edu if you must reproduce old work. Or pin scikit-learn<1.2." % DATE["1.2.0"]),
    ("How do I fix \"cannot import name 'plot_confusion_matrix' from 'sklearn.metrics'\"?",
     "scikit-learn 1.2.0 removed plot_confusion_matrix, plot_roc_curve, plot_precision_recall_curve and plot_det_curve (and "
     "inspection.plot_partial_dependence). Use the display classes: ConfusionMatrixDisplay.from_estimator(clf, X, y) or "
     ".from_predictions(y_true, y_pred), RocCurveDisplay.from_estimator, PrecisionRecallDisplay, DetCurveDisplay, PartialDependenceDisplay."),
    ("How do I fix \"No module named 'sklearn.ensemble.forest'\" when loading a pickle?",
     "The pickle was written by scikit-learn 0.23 or earlier, which had public modules such as sklearn.ensemble.forest, sklearn.tree.tree and "
     "sklearn.linear_model.logistic; 0.24.0 (%s) removed %d of them (0.22 and 0.23 warned). Load the file in an environment with the same "
     "scikit-learn version that wrote it (pip install \"scikit-learn<0.24\"), and save the model again from there in a format you can rebuild, "
     "or retrain it. In code, import from the package: from sklearn.ensemble import RandomForestClassifier." % (DATE["0.24.0"], len(m24))),
    ("How do I fix \"cannot import name 'joblib' from 'sklearn.externals'\"?",
     "scikit-learn 0.23.0 (%s) removed the vendored copy. pip install joblib, then import joblib (joblib.dump, joblib.load). Old pickles that "
     "refer to sklearn.externals.joblib need scikit-learn<0.23 to load." % DATE["0.23.0"]),
    ("How do I fix \"No module named 'sklearn.cross_validation'\"?",
     "scikit-learn 0.20.0 (%s) removed sklearn.cross_validation, grid_search and learning_curve; their contents are in sklearn.model_selection "
     "(train_test_split, KFold, GridSearchCV, learning_curve)." % DATE["0.20.0"]),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["scikit-learn", "ImportError", "ModuleNotFoundError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "scikit-learn removed name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or ModuleNotFoundError from sklearn and get, for each scikit-learn release from %s to %s, whether the name or module exists, and what to use instead." % (VS[0], LATEST),
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "scikit-learn names by release", "url": URL + "sklearn_names.json", "dateModified": MOD,
     "description": "The public names and submodules of sklearn and %d of its modules in %d installed scikit-learn releases (%s to %s), and the deprecation text before each removal." % (len(G[VS[-1]]) - 1, len(VS), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "sklearn_names.json"}]},
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
EX = [("ImportError: cannot import name 'load_boston' from 'sklearn.datasets' (/usr/local/lib/python3.11/site-packages/sklearn/datasets/__init__.py)", "load_boston"),
      ("ImportError: cannot import name 'plot_confusion_matrix' from 'sklearn.metrics'", "plot_confusion_matrix"),
      ("ModuleNotFoundError: No module named 'sklearn.ensemble.forest'", "ensemble.forest"),
      ("from sklearn.externals import joblib", "externals.joblib"), ("from sklearn.cross_validation import train_test_split", "cross_validation")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
rel_list = ", ".join("%s (Python %s, NumPy %s)" % (v, DIRS[v]["python"].rsplit(".", 1)[0], DIRS[v]["numpy"]) for v in VS)
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var LBL = {ok: "has it", warn: "has it, warns on access", gone: "not there"};
  var CLS = {};
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function find(t) {
    var out = [], m;
    var re = /cannot import name '(\w+)' from '(sklearn(?:\.\w+)*)'|module '(sklearn(?:\.\w+)*)' has no attribute '(\w+)'|'(\w+)' object has no attribute '(\w+)'|from (sklearn(?:\.\w+)*) import ([\w ,()]+)|\b(sklearn(?:\.\w+)+)/g;
    while ((m = re.exec(t))) {
      if (m[1]) out.push([m[2], m[1]]);
      else if (m[3]) out.push([m[3], m[4]]);
      else if (m[5]) out.push([CLS[m[5]] || null, m[6]]);
      else if (m[7]) m[8].replace(/[()]/g, " ").split(",").forEach(function (p) { var n = p.trim().split(/\s+as\s+/)[0]; if (n) out.push([m[7], n]); });
      else if (m[9]) { var s = m[9].split("."); out.push([s.slice(0, -1).join("."), s[s.length - 1]]); }
    }
    return out;
  }
  function show() {
    var h = "", seen = {};
    find(q.value).forEach(function (t) {
      var rs = Object.keys(D.rows).map(function (k) { return D.rows[k]; }).filter(function (x) { return x.name === t[1] && (!t[0] || x.obj === t[0]); });
      if (t[0] && !D.names[t[0]] && t[0].indexOf(".") > 0) {   // `from sklearn.cross_validation import x`: the module itself is gone
        var par = t[0].slice(0, t[0].lastIndexOf(".")), leaf = t[0].slice(t[0].lastIndexOf(".") + 1);
        var mr = Object.keys(D.rows).map(function (k) { return D.rows[k]; }).filter(function (x) { return x.module && x.obj === par && x.name === leaf; });
        if (mr.length) rs = mr.concat(rs);
      }
      if (!rs.length) {
        if (seen["?" + t[1]]) return; seen["?" + t[1]] = 1;
        var where = Object.keys(D.names).filter(function (k) { return D.names[k].indexOf(t[1]) >= 0; });
        if (!t[0] && !where.length) return;
        h += "<h3><code>" + esc((t[0] ? t[0].replace(":", ".") + "." : "") + t[1]) + "</code></h3><p>" + (where.length ? "Not removed in any release read: " + esc(t[1]) + " is in " + where.map(function (k) { return esc(k.replace(":", ".")); }).join(", ") + " in " + esc(D.releases[D.releases.length - 1][0]) + "." : "No scikit-learn release from " + esc(D.releases[0][0]) + " to " + esc(D.releases[D.releases.length - 1][0]) + " has this name in the modules this page covers.") + "</p>";
        return;
      }
      rs.forEach(function (x) {
        var k = x.obj + "." + x.name; if (seen[k]) return; seen[k] = 1;
        var lab = x.obj.replace(":", ".") + "." + x.name, segs = [], prev = null;
        x.seq.split("").forEach(function (c, i) { var st = {o: "ok", w: "warn", g: "gone"}[c], v = D.releases[i][0]; if (st !== prev) { segs.push([v, st]); prev = st; } else segs[segs.length - 1][2] = v; });
        h += "<h3><code>" + esc(lab) + "</code>" + (x.module ? " (module)" : "") + "</h3><p><strong>Removed in scikit-learn " + esc(x.removed) + "</strong> (last in " + esc(x.last) + ").";
        if (x.fix) h += " <strong>Instead:</strong> " + esc(x.fix) + ' <span class="note">(' + esc(x.src) + ")</span>";
        h += '</p><p>To keep it: <code>pip install "scikit-learn&lt;' + esc(x.removed) + '"</code></p>';
        if (!x.pre) {
          h += '<div class="tw"><table><thead><tr><th>scikit-learn</th><th>' + esc(lab) + "</th></tr></thead><tbody>";
          segs.forEach(function (s) { h += "<tr><td>" + esc(s[0]) + (s[2] ? " to " + esc(s[2]) : "") + '</td><td class="s-' + s[1] + '">' + LBL[s[1]] + "</td></tr>"; });
          h += "</tbody></table></div>";
        } else h += "<p>Read from the source at the release tags (before the first release installed here, " + esc(D.releases[0][0]) + ").</p>";
      });
    });
    if (!h) h = "<p>Paste the ImportError or ModuleNotFoundError line, for example cannot import name 'load_boston' from 'sklearn.datasets'.</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.SK_READY = true;
})();
"""
assert "</script" not in JS
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
<p class="lede"><strong>scikit-learn 1.2.0 ({DATE["1.2.0"]}) removed <code>sklearn.datasets.load_boston</code> and <code>sklearn.metrics.plot_confusion_matrix</code> (use <code>ConfusionMatrixDisplay.from_estimator</code>); 0.24.0 ({DATE["0.24.0"]}) removed {len(m24)} modules such as <code>sklearn.ensemble.forest</code> and <code>sklearn.tree.tree</code>, which is why old pickles fail with "No module named"; 0.23.0 removed <code>sklearn.externals.joblib</code> (<code>import joblib</code>); 0.20.0 removed <code>sklearn.cross_validation</code> (<code>sklearn.model_selection</code>).</strong> If the error comes from a library you did not write, upgrade the library or pin scikit-learn below the release that removed the name. Paste the error below for the release-by-release answer.</p>
<p class="meta">Published {PUB} &middot; {len(VS)} scikit-learn releases installed and run, {VS[0]} to {LATEST} ({n_runs:,} lookups) &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line or the import statement</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'load_boston' from 'sklearn.datasets'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="sklearn_names.json">sklearn_names.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which release removed it, and what replaces it?</h2>
<p><strong>{len(rest)} public names and modules that one scikit-learn release has and a later one does not.</strong> "Instead" is scikit-learn's own deprecation text from the last release that had it ({n_fix} of {len(rest)}); for {n_data} more it names the module that still has the same name in {LATEST}. The {len(m24)} modules removed in 0.24.0 are listed after the table.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Removed in</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>
<p><strong>Modules removed in 0.24.0</strong> (each warned in 0.22 and 0.23 that its contents should be imported from the package above it): {m24_html}.</p>

<h2 id="how">How was this measured?</h2>
<p><strong>Each of {len(VS)} scikit-learn releases (the first of every minor from {VS[0]}, plus the latest) was installed from PyPI in its own environment, the public names, <code>__all__</code> and submodules of sklearn and {len(G[VS[-1]]) - 1} of its modules were listed, and <code>getattr</code> (or <code>import</code>, for a submodule) was run for the union of all names in every release.</strong> Releases: {rel_list}. A name counts when it is in the module's <code>__all__</code>, or is a submodule, so names a file merely imported are left out. The replacement text is read from the installed source of the last release that had the name (its deprecation decorator or <code>warnings.warn</code> string, or the warning given on import). Removals before 0.22 (no Python 3.8 wheels) were read from the source at the 0.19.2, 0.20.0, 0.21.3 and 0.22 tags.</p>
<p>Patch releases were not read: a name removed in x.y.1 shows at the next minor.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The scikit-learn wheels on <a href="https://pypi.org/project/scikit-learn/#history">PyPI</a>, installed and run, and their source as installed; the release dates are PyPI's.</li>
<li>scikit-learn/scikit-learn at the tags: <a href="https://github.com/scikit-learn/scikit-learn/blob/0.19.2/sklearn/cross_validation.py">sklearn/cross_validation.py at 0.19.2</a>, <a href="https://github.com/scikit-learn/scikit-learn/blob/0.21.3/sklearn/preprocessing/imputation.py">sklearn/preprocessing/imputation.py at 0.21.3</a>.</li>
</ul>
<p>The same data as JSON: <a href="sklearn_names.json">sklearn_names.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/scipy-removed-name-lookup/">"cannot import name 'triu' from 'scipy.linalg'"</a> &middot; <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a> &middot; <a href="/en/pandas-removed-attribute-lookup/">"'DataFrame' object has no attribute 'append'"</a>.</p>
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
(out_dir / "sklearn_names.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | removals %d (modules %d, 0.24 modules %d) | with text %d, data %d | releases %d" % (len(page), len(rest), len(mods), len(m24), n_fix, n_data, len(VS)), file=sys.stderr)
