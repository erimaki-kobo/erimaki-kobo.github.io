#!/usr/bin/env python3
"""Build en/scipy-removed-name-lookup/ (index.html and scipy_names.json).

Usage: python3 -I build_page.py probes/ pre13.json pypi.json out_dir PUBLISHED MODIFIED
probes/: dir_<v>.json (public names and __all__), get_<v>.json (getattr of the union in each release), msg_<v>.json
(deprecation text in the last release before each removal). pre13.json: scipy.misc names removed in 1.3.0 (pre13.py).
ASCII only; the facts the prose names are asserted. style.css is shared with .github/llama-args.
"""
import __future__, html, json, os, re, sys, typing
from pathlib import Path

PD, PRE, P = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
out_dir, PUB, MOD = Path(sys.argv[4]), sys.argv[5], sys.argv[6]
HERE = Path(__file__).resolve().parent
e = html.escape
key = lambda v: tuple(int(x) for x in v.split("."))
VS = sorted((f[4:-5] for f in os.listdir(PD) if f.startswith("get_") and f.endswith(".json")), key=key)
G = {v: json.load(open(os.path.join(PD, "get_%s.json" % v)))["get"] for v in VS}
DIRS = {v: json.load(open(os.path.join(PD, "dir_%s.json" % v))) for v in VS}
MSG = {f[4:-5]: json.load(open(os.path.join(PD, f))) for f in os.listdir(PD) if f.startswith("msg_") and f.endswith(".json")}
DATE = {v: min(f["upload_time"] for f in P["releases"][v])[:10] for v in (VS + ["1.3.0", "1.2.3"])}
LATEST = VS[-1]
LAB = lambda k: k.replace(":", ".")
NOISE = set(__future__.all_feature_names) | set(typing.__all__) | set(sys.stdlib_module_names) | {"np", "numpy", "xpx"}


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
        if (n in NOISE and not (k == "scipy" and n not in __future__.all_feature_names and n != "np")) or (k != "scipy" and ":" not in k and allv is not None and n not in allv):
            continue   # a module the file imported, typing or __future__ names, or a helper outside __all__
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
        if not msg and k == "scipy":
            msg, src = "Use numpy.%s: the scipy namespace re-exported NumPy's names." % n, "our note"
        ROWS["%s.%s" % (k, n)] = {"obj": k, "name": n, "seq": [list(s) for s in seq], "removed": rem[0], "last": rem[1], "fix": msg, "src": src}
for r in ROWS.values():   # no text: the same name still public in another module of the latest release
    if r["fix"] or r["obj"] == "scipy":
        continue
    alive = [k2 for k2 in G[LATEST] if k2 != r["obj"] and ":" not in k2 and r["name"] in DIRS[LATEST]["all"].get(k2, DIRS[LATEST]["dir"].get(k2, []))
             and G[LATEST][k2].get(r["name"], {}).get("ok")]
    if alive:
        r["fix"] = "From %s import %s (still there in %s)." % (alive[0], r["name"], LATEST)
        r["src"] = "this page's data"
for n, x in PRE.items():
    ROWS["scipy.misc.%s" % n] = {"obj": "scipy.misc", "name": n, "seq": [[v, "gone"] for v in VS], "removed": "1.3.0", "last": "1.2.3",
                                 "fix": x["message"], "src": "source of 1.2.0 (%s)" % x["file"], "pre": True}
R = lambda k, n: ROWS["%s.%s" % (k, n)]
top = [r for r in ROWS.values() if r["obj"] == "scipy"]
top12 = [r for r in top if r["removed"] == "1.12.0"]
rest = [r for r in ROWS.values() if r["obj"] != "scipy"]
# facts the prose names
for k, n, v in [("scipy.linalg", "triu", "1.13.0"), ("scipy.linalg", "tril", "1.13.0"), ("scipy.integrate", "simps", "1.14.0"),
                ("scipy.integrate", "cumtrapz", "1.14.0"), ("scipy.integrate", "trapz", "1.14.0"), ("scipy.sparse:csr_matrix", "A", "1.14.0"),
                ("scipy.misc", "imread", "1.3.0"), ("scipy.misc", "imresize", "1.3.0"), ("scipy.misc", "comb", "1.3.0"),
                ("scipy.misc", "face", "1.15.0"), ("scipy.misc", "derivative", "1.15.0"), ("scipy.linalg", "pinv2", "1.9.0"),
                ("scipy.integrate", "quadrature", "1.15.0"), ("scipy.integrate", "romberg", "1.15.0"), ("scipy.signal", "cwt", "1.15.0"),
                ("scipy.special", "sph_harm", "1.17.0"), ("scipy.linalg", "kron", "1.17.0"), ("scipy.stats", "binom_test", "1.12.0"),
                ("scipy.signal", "gaussian", "1.13.0"), ("scipy.signal", "hann", "1.13.0")]:
    assert R(k, n)["removed"] == v, (k, n, R(k, n)["removed"])
for k, n, want in [("scipy.linalg", "triu", "numpy"), ("scipy.integrate", "simps", "simpson"), ("scipy.integrate", "cumtrapz", "cumulative_trapezoid"),
                   ("scipy.integrate", "trapz", "trapezoid"), ("scipy.sparse:csr_matrix", "A", ".toarray()"), ("scipy.misc", "imread", "imageio.imread"),
                   ("scipy.misc", "comb", "scipy.special.comb"), ("scipy.linalg", "pinv2", "scipy.linalg.pinv"), ("scipy.stats", "binom_test", "binomtest"),
                   ("scipy.misc", "face", "scipy.datasets"), ("scipy.integrate", "quadrature", "scipy.integrate.quad")]:
    assert want in (R(k, n)["fix"] or ""), (k, n, R(k, n)["fix"])
assert len(top12) > 400 and all(R("scipy", n)["removed"] == "1.12.0" for n in ("arange", "array", "interp", "zeros", "pi"))
n_fix = sum(1 for r in rest if r["fix"] and r["src"] != "this page's data")
n_data = sum(1 for r in rest if r["src"] == "this page's data")
n_runs = sum(len(x) for x in G[VS[0]].values()) * len(VS)
assert DIRS["1.3.3"]["import_errors"].get("scipy.fft") and all(not DIRS[v]["import_errors"] for v in VS[1:])

CODE = {"ok": "o", "warn": "w", "gone": "g"}
ROWS_OUT = {kk: dict(r, seq="".join(CODE[s[1]] for s in r["seq"])) for kk, r in ROWS.items()}
DATA = {"releases": [[v, DATE[v], DIRS[v]["python"], DIRS[v]["numpy"]] for v in VS], "rows": ROWS_OUT,
        "names": {k: sorted(set().union(*(DIRS[v]["dir"].get(k, []) for v in VS))) for k in G[VS[-1]]}}
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json
URL = "https://erimaki-kobo.github.io/en/scipy-removed-name-lookup/"
TITLE = "cannot import name 'triu' from 'scipy.linalg' (and others): scipy fix"
H1 = "ImportError: cannot import name 'triu' from 'scipy.linalg' (or 'simps', 'imread', any name): which SciPy removed it and what to use"
DESC = ("SciPy 1.13 removed linalg.triu (gensim breaks), 1.14 integrate.simps and sparse .A, 1.3 misc.imread. %d removals, checked by running %d releases. Paste the error."
        % (len(rest) + len(top), len(VS)))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))

tab = []
for r in sorted(rest, key=lambda x: (key(x["removed"]), x["obj"], x["name"].lower())):
    tab.append("<tr><td><code>%s.%s</code></td><td>%s</td><td>%s</td></tr>" % (e(LAB(r["obj"])), e(r["name"]), r["removed"], e(r["fix"] or "")))
tab_html = "\n".join(tab)
FAQ = [
    ("How do I fix \"cannot import name 'triu' from 'scipy.linalg'\" (gensim)?",
     "SciPy 1.13.0 (%s) removed scipy.linalg.tri, tril and triu; 1.11 and 1.12 warned. Use numpy.triu, numpy.tril and numpy.tri, which take "
     "the same arguments. gensim 4.3.2 and earlier import triu from scipy.linalg in gensim/matutils.py and fail on import; gensim 4.3.3 "
     "(2024-07-19) takes it from numpy. Upgrade gensim, or pin scipy<1.13." % DATE["1.13.0"]),
    ("How do I fix \"cannot import name 'simps' from 'scipy.integrate'\"?",
     "SciPy 1.14.0 (%s) removed simps, trapz and cumtrapz. Use scipy.integrate.simpson, trapezoid and cumulative_trapezoid." % DATE["1.14.0"]),
    ("How do I fix \"'csr_matrix' object has no attribute 'A'\"?",
     "SciPy 1.14.0 removed the .A and .H attributes of the sparse matrix classes. Use .toarray() for .A and .T.conjugate() (or .conj().T) for .H."),
    ("How do I fix \"cannot import name 'imread' from 'scipy.misc'\"?",
     "SciPy 1.3.0 (%s) removed the image functions of scipy.misc (imread, imsave, imresize, imrotate, imshow, toimage, fromimage, "
     "bytescale, imfilter); 1.2.3 is the last release with them, and they needed Pillow. Read and write images with imageio "
     "(imageio.imread) or Pillow; resize with Pillow's Image.resize. The same release removed misc.comb, factorial and logsumexp: "
     "import them from scipy.special." % DATE["1.3.0"]),
    ("Why does \"module 'scipy' has no attribute 'interp'\" (or 'array', 'zeros') appear?",
     "Until 1.11 the scipy namespace re-exported NumPy's functions. SciPy 1.12.0 (%s) removed %d of them. Call them on numpy: np.interp, np.array." % (DATE["1.12.0"], len(top12))),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["SciPy", "ImportError", "AttributeError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "SciPy removed name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or AttributeError from scipy and get, for each SciPy release from %s to %s, whether the name exists, and what to use instead." % (VS[0], LATEST),
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "SciPy names by release", "url": URL + "scipy_names.json", "dateModified": MOD,
     "description": "The public names of scipy and %d submodules and the sparse matrix classes in %d installed SciPy releases (%s to %s), and the deprecation text before each removal." % (len(G[VS[-1]]) - 4, len(VS), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "scipy_names.json"}]},
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
EX = [("ImportError: cannot import name 'triu' from 'scipy.linalg' (/usr/lib/python3/dist-packages/scipy/linalg/__init__.py)", "triu"),
      ("ImportError: cannot import name 'simps' from 'scipy.integrate'", "simps"), ("AttributeError: 'csr_matrix' object has no attribute 'A'", ".A"),
      ("from scipy.misc import imread, imresize", "imread"), ("AttributeError: module 'scipy' has no attribute 'interp'", "scipy.interp")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
rel_list = ", ".join("%s (Python %s, NumPy %s)" % (v, DIRS[v]["python"].rsplit(".", 1)[0], DIRS[v]["numpy"]) for v in VS)
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var LBL = {ok: "has it", warn: "has it, warns on access", gone: "not there"};
  var CLS = {csr_matrix: "scipy.sparse:csr_matrix", coo_matrix: "scipy.sparse:coo_matrix", lil_matrix: "scipy.sparse:lil_matrix"};
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function find(t) {
    var out = [], m;
    var re = /cannot import name '(\w+)' from '(scipy(?:\.\w+)*)'|module '(scipy(?:\.\w+)*)' has no attribute '(\w+)'|'(\w+)' object has no attribute '(\w+)'|from (scipy(?:\.\w+)*) import ([\w ,()]+)|\b(scipy(?:\.\w+)+)/g;
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
      if (!rs.length) {
        if (seen["?" + t[1]]) return; seen["?" + t[1]] = 1;
        var where = Object.keys(D.names).filter(function (k) { return D.names[k].indexOf(t[1]) >= 0; });
        if (!t[0] && !where.length) return;
        h += "<h3><code>" + esc((t[0] ? t[0].replace(":", ".") + "." : "") + t[1]) + "</code></h3><p>" + (where.length ? "Not removed in any release read: " + esc(t[1]) + " is in " + where.map(function (k) { return esc(k.replace(":", ".")); }).join(", ") + " in " + esc(D.releases[D.releases.length - 1][0]) + "." : "No SciPy release from " + esc(D.releases[0][0]) + " to " + esc(D.releases[D.releases.length - 1][0]) + " has this name in the modules this page covers.") + "</p>";
        return;
      }
      rs.forEach(function (x) {
        var k = x.obj + "." + x.name; if (seen[k]) return; seen[k] = 1;
        var lab = x.obj.replace(":", ".") + "." + x.name, segs = [], prev = null;
        x.seq.split("").forEach(function (c, i) { var st = {o: "ok", w: "warn", g: "gone"}[c], v = D.releases[i][0]; if (st !== prev) { segs.push([v, st]); prev = st; } else segs[segs.length - 1][2] = v; });
        h += "<h3><code>" + esc(lab) + "</code></h3><p><strong>Removed in SciPy " + esc(x.removed) + "</strong> (last in " + esc(x.last) + ").";
        if (x.fix) h += " <strong>Instead:</strong> " + esc(x.fix) + ' <span class="note">(' + esc(x.src) + ")</span>";
        h += '</p><p>To keep it: <code>pip install "scipy&lt;' + esc(x.removed) + '"</code></p>';
        if (!x.pre) {
          h += '<div class="tw"><table><thead><tr><th>SciPy</th><th>' + esc(lab) + "</th></tr></thead><tbody>";
          segs.forEach(function (s) { h += "<tr><td>" + esc(s[0]) + (s[2] ? " to " + esc(s[2]) : "") + '</td><td class="s-' + s[1] + '">' + LBL[s[1]] + "</td></tr>"; });
          h += "</tbody></table></div>";
        } else h += "<p>Read from the source at the release tags (before the first release installed here, " + esc(D.releases[0][0]) + ").</p>";
      });
    });
    if (!h) h = "<p>Paste the ImportError or AttributeError line, for example cannot import name 'triu' from 'scipy.linalg'.</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.SP_READY = true;
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
<p class="lede"><strong>SciPy 1.13.0 ({DATE["1.13.0"]}) removed <code>scipy.linalg.triu</code>, <code>tril</code> and <code>tri</code> (use <code>numpy.triu</code>), which breaks gensim 4.3.2 and earlier; 1.14.0 ({DATE["1.14.0"]}) removed <code>scipy.integrate.simps</code>, <code>trapz</code>, <code>cumtrapz</code> (use <code>simpson</code>, <code>trapezoid</code>, <code>cumulative_trapezoid</code>) and the sparse <code>.A</code> (use <code>.toarray()</code>); 1.3.0 removed <code>scipy.misc.imread</code> and <code>imresize</code> (use imageio or Pillow).</strong> If the error comes from a library you did not write, upgrade the library or pin SciPy below the release that removed the name. Paste the error below for the release-by-release answer.</p>
<p class="meta">Published {PUB} &middot; {len(VS)} SciPy releases installed and run, {VS[0]} to {LATEST} ({n_runs:,} name lookups) &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line or the import statement</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'triu' from 'scipy.linalg'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="scipy_names.json">scipy_names.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which release removed it, and what replaces it?</h2>
<p><strong>{len(rest)} public names of SciPy's submodules and sparse matrix classes that one release has and a later one does not</strong>, plus {len(top)} NumPy names the <code>scipy</code> namespace used to re-export ({len(top12)} of them removed in 1.12.0; the lookup answers for each). "Instead" is SciPy's own deprecation text from the last release that had the name ({n_fix} of {len(rest)}); for {n_data} more it names the module that still has the same name in {LATEST}.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Removed in</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>

<h2 id="how">How was this measured?</h2>
<p><strong>Each of {len(VS)} SciPy releases (the first of every minor from {VS[0]}, plus the latest) was installed from PyPI in its own environment, the public names of scipy, {len(G[VS[-1]]) - 4} submodules and the sparse matrix classes were listed with <code>dir()</code> and <code>__all__</code>, and <code>getattr</code> was run for the union of all names in every release.</strong> Releases: {rel_list}. A name counts when it is in the module's <code>__all__</code> (or the module has none), so modules a file merely imported (<code>np</code>, <code>warnings</code>) are left out. The replacement text is read from the installed source of the last release that had the name: the strings of its deprecation decorator or <code>warnings.warn</code> call, or another deprecation string in SciPy that names it. The scipy.misc image functions and re-exports removed in 1.3.0 were read from the source at the v1.2.0 and v1.3.0 tags. scipy.fft did not exist in 1.3.3.</p>
<p>Patch releases were not read: a name removed in x.y.1 shows at the next minor.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The SciPy wheels on <a href="https://pypi.org/project/scipy/#history">PyPI</a>, installed and run, and their source as installed; the release dates are PyPI's.</li>
<li>scipy/scipy at the tags: <a href="https://github.com/scipy/scipy/blob/v1.2.0/scipy/misc/pilutil.py">scipy/misc/pilutil.py at v1.2.0</a>, <a href="https://github.com/scipy/scipy/blob/v1.3.0/scipy/misc/__init__.py">scipy/misc/__init__.py at v1.3.0</a>.</li>
</ul>
<p>The same data as JSON: <a href="scipy_names.json">scipy_names.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a> &middot; <a href="/en/pandas-removed-attribute-lookup/">"'DataFrame' object has no attribute 'append'"</a> &middot; <a href="/en/torchvision-import-name-version-lookup/">"No module named 'torchvision.transforms.functional_tensor'"</a>.</p>
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
(out_dir / "scipy_names.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | submodule removals %d (with SciPy text %d) | top-level %d (1.12: %d) | releases %d" % (len(page), len(rest), n_fix, len(top), len(top12), len(VS)), file=sys.stderr)
