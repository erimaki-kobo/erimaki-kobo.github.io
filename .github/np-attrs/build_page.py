#!/usr/bin/env python3
"""Build en/numpy-removed-attribute-lookup/ (index.html and numpy_attrs.json).

Usage: python3 -I build_page.py np_attrs.json probes/ verify.json removal_msgs.json pypi.json out_dir PUBLISHED MODIFIED
np_attrs.json: the __getattr__ tables read from the source (np_attrs.py). probes/<version>.json: getattr(numpy, name) run in an
installed numpy (probe.py). verify.json: the two agree (verify.py). removal_msgs.json: deprecation messages for the names
removed without one (removal_msgs.py). ASCII only; the facts the prose names are asserted. style.css is shared with
.github/llama-args.
"""
import html, json, os, re, sys
from pathlib import Path

A, PD, VER, RM, P = json.load(open(sys.argv[1])), sys.argv[2], json.load(open(sys.argv[3])), json.load(open(sys.argv[4])), json.load(open(sys.argv[5]))
out_dir, PUB, MOD = Path(sys.argv[6]), sys.argv[7], sys.argv[8]
HERE = Path(__file__).resolve().parent
e = html.escape
key = lambda v: tuple(int(x) for x in v.split("."))
VS = sorted((f[:-5] for f in os.listdir(PD) if f.endswith(".json")), key=key)
PR = {v: json.load(open(os.path.join(PD, v + ".json"))) for v in VS}
DATE = {v: min(f["upload_time"] for f in P["releases"][v])[:10] for v in VS}
LATEST = VS[-1]
assert VER["confirmed"] >= 600 and not VER["mismatches"] and set(VER["releases"]) == set(VS) - {"1.19.5"}
URL = "https://erimaki-kobo.github.io/en/numpy-removed-attribute-lookup/"
TITLE = "module 'numpy' has no attribute 'float_' (or float, NaN): fix by version"
H1 = "AttributeError: module 'numpy' has no attribute 'float_' (or 'float', 'NaN', 'product', any name): which NumPy removed it and what to use"
DESC = ("NumPy 1.24 removed np.float, np.int and np.bool; 2.0 removed 77 names such as np.float_, np.NaN and np.product. Checked by "
        "running 15 releases. Paste the error.")
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 165, (len(TITLE), len(DESC))


def state(r):
    if r["ok"]:
        return "warn" if r["warn"] else "ok"
    return "msg" if not (r["error"].startswith("module 'numpy' has no attribute") and "\n" not in r["error"]) else "gone"


NAMES = sorted(PR[VS[0]]["names"])
ROWS = {}
for n in NAMES:
    seq = [(v, state(PR[v]["names"][n]), PR[v]["names"][n]) for v in VS]
    fix = None
    for v, s, r in reversed(seq):   # the newest message that names the replacement
        if s == "msg":
            fix = r["error"]
            break
    if fix is None:
        for v in reversed(VS):
            dep = A.get(v, {}).get("deprecated", {}).get(n) or A.get(v, {}).get("expired_fn", {}).get(n)
            if dep:
                fix = dep
                break
    if fix is None and n in RM:
        fix = RM[n]["message"]
    ROWS[n] = {"seq": [[v, s, (r.get("error") or ",".join(r["warn"]))] for v, s, r in seq], "fix": fix}

def first_state(n, s):
    return next((v for v, st, _ in ROWS[n]["seq"] if st == s), None)

def removed_in(n):   # first release from which access fails, after one where it worked
    seq = ROWS[n]["seq"]
    for i in range(1, len(seq)):
        if seq[i][1] in ("gone", "msg") and seq[i - 1][1] in ("ok", "warn"):
            return seq[i][0]
    return None

# facts the prose names
for n in ("float", "int", "bool", "object", "str", "complex", "long", "unicode"):
    assert removed_in(n) == "1.24.0" and first_state(n, "warn") == "1.20.0", n
for n in ("float", "int", "object", "str", "complex", "bool"):
    assert first_state(n, "msg") == "1.25.0", n
assert ROWS["bool"]["seq"][VS.index("2.0.0")][1] == "ok" and ROWS["long"]["seq"][VS.index("2.0.0")][1] == "ok"
for n in ("float_", "NaN", "Inf", "complex_", "string_", "unicode_", "round_", "cfloat", "infty", "PINF", "NINF", "mat", "sctypes"):
    assert removed_in(n) == "2.0.0" and ROWS[n]["seq"][-1][1] == "msg", n
for n in ("product", "cumproduct", "msort", "bool8", "int0", "object0", "math"):
    assert removed_in(n) == "2.0.0" and ROWS[n]["seq"][-1][1] == "gone", n
assert removed_in("in1d") == "2.4.1" and removed_in("trapz") == "2.4.1" and removed_in("row_stack") == "2.5.0" and removed_in("chararray") == "2.5.0"
assert removed_in("asscalar") == "1.23.0" and removed_in("typeDict") == "1.24.0" and removed_in("MachAr") == "1.24.0"
assert all(f.get("yanked") for f in P["releases"]["2.4.0"])
assert ROWS["_core"]["seq"][VS.index("1.26.0")][1] == "gone" and ROWS["_core"]["seq"][VS.index("2.0.0")][1] == "ok"
for n, want in (("float_", "np.float64"), ("NaN", "np.nan"), ("Inf", "np.inf"), ("complex_", "np.complex128"), ("string_", "np.bytes_"),
                ("unicode_", "np.str_"), ("round_", "np.round"), ("product", "prod"), ("in1d", "np.isin"), ("trapz", "trapezoid"), ("row_stack", "np.vstack")):
    assert want in ROWS[n]["fix"], (n, ROWS[n]["fix"])
n20 = sorted(n for n in NAMES if removed_in(n) == "2.0.0")
n20msg = [n for n in n20 if ROWS[n]["seq"][VS.index("2.0.0")][1] == "msg"]
n_runs = len(VS) * len(NAMES)
assert len(n20) == 77 and len(VS) == 15 and "77 names" in DESC and "15 releases" in DESC

DATA = {"releases": [[v, DATE[v], PR[v]["python"]] for v in VS], "names": {n: ROWS[n] for n in NAMES}}
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json

GROUPS = [("1.23.0", "1.23"), ("1.24.0", "1.24"), ("2.0.0", "2.0"), ("2.4.1", "2.4"), ("2.5.0", "2.5")]
def short(msg):
    m = msg.split("\n")[0] if msg and msg.startswith("module 'numpy'") and "\n" in msg else msg
    if msg and msg.startswith("module 'numpy'") and "\n" in msg:
        m = msg.split("\n")[1]
    return m or ""
tab = []
for v, label in GROUPS:
    for n in sorted((n for n in NAMES if removed_in(n) == v), key=str.lower):
        tab.append("<tr><td><code>np.%s</code></td><td>%s</td><td>%s</td></tr>" % (e(n), label, e(short(ROWS[n]["fix"] or ""))))
tab_html = "\n".join(tab)
n_tab = len(tab)

FAQ = [
    ("How do I fix \"module 'numpy' has no attribute 'float'\" (or 'int', 'bool', 'object')?",
     "NumPy 1.24.0 (%s) removed these aliases of the Python builtins; 1.20 to 1.23 warned. Use float, int, bool, object (the builtins) "
     "or the NumPy types np.float64, np.int64, np.bool_. From 1.25 the error explains this. np.bool and np.long exist again from 2.0, "
     "now as NumPy types (np.bool is np.bool_). If the error comes from a library, upgrade it, or pin numpy<1.24." % DATE["1.24.0"]),
    ("How do I fix \"`np.float_` was removed in the NumPy 2.0 release\"?",
     "Use np.float64. NumPy 2.0.0 (%s) removed %d names; %d of them answer with a message naming the replacement (np.NaN to np.nan, "
     "np.Inf to np.inf, np.complex_ to np.complex128, np.string_ to np.bytes_, np.unicode_ to np.str_). The others fail with the plain "
     "AttributeError; the table on this page gives their replacement from the deprecation warning they showed before." % (DATE["2.0.0"], len(n20), len(n20msg))),
    ("Why does \"No module named 'numpy._core'\" appear?",
     "numpy._core exists from NumPy 2.0 (numpy.core before). A pickle, joblib or model file written with NumPy 2 refers to numpy._core, "
     "so loading it under NumPy 1.x fails. Load it with NumPy 2, or write it again under the NumPy you load it with."),
    ("What does \"A module that was compiled using NumPy 1.x cannot be run in NumPy 2.0.0\" mean?",
     "An installed package has a C extension built against NumPy 1.x. NumPy 2 prints this from numpy/core/_multiarray_umath.py and "
     "suggests the two fixes: upgrade that package to a release built for NumPy 2, or pin numpy<2."),
    ("np.trapz and np.in1d stopped working. What changed?",
     "NumPy 2.4 removed them (2.4.0 was yanked from PyPI; 2.4.1 is the first 2.4 release). Use np.trapezoid and np.isin. NumPy 2.5 "
     "removed np.row_stack (use np.vstack) and np.chararray from the main namespace."),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["NumPy", "AttributeError", "NumPy 2.0 migration"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "NumPy removed attribute lookup", "url": URL + "#lookup",
     "description": "Paste an AttributeError from numpy and get what np.<name> does in each NumPy release from 1.19 to %s, measured by running each release, and what to use instead." % LATEST,
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "What getattr(numpy, name) does, by NumPy release", "url": URL + "numpy_attrs.json", "dateModified": MOD,
     "description": "%d removed or deprecated NumPy attributes, each accessed in %d installed NumPy releases (%s to %s): works, warns, or the AttributeError message." % (len(NAMES), len(VS), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "numpy_attrs.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\ntd code,p code,li code,h1,h2,h3{overflow-wrap:anywhere}main p,main li,td{overflow-wrap:break-word}\n.s-ok{color:var(--ok,#1a7f37)}.s-warn{color:#9a6700}.s-gone,.s-msg{color:#cf222e}\n"
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("AttributeError: module 'numpy' has no attribute 'float'.", "float"), ("AttributeError: `np.float_` was removed in the NumPy 2.0 release. Use `np.float64` instead.", "float_"),
      ("np.NaN", "NaN"), ("AttributeError: module 'numpy' has no attribute 'product'", "product"), ("np.trapz", "trapz"), ("np.bool", "bool")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
rel_list = ", ".join("%s (Python %s)" % (v, PR[v]["python"].rsplit(".", 1)[0]) for v in VS)
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var LBL = {ok: "works", warn: "works, warns", gone: "AttributeError", msg: "AttributeError with a message"};
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function names(t) {
    var out = [], m, re = /has no attribute ['"`]?([A-Za-z_]\w*)|`np\.([A-Za-z_]\w*)`|\b(?:np|numpy)\.([A-Za-z_]\w*)/g;
    while ((m = re.exec(t))) { var n = m[1] || m[2] || m[3]; if (out.indexOf(n) < 0) out.push(n); }
    if (!out.length) (t.match(/[A-Za-z_]\w*/g) || []).forEach(function (w) { if (D.names[w] && out.indexOf(w) < 0) out.push(w); });
    return out;
  }
  function show() {
    var ns = names(q.value), h = "";
    if (!ns.length) { res.innerHTML = "<p>Paste the error line, or write np.&lt;name&gt;.</p>"; res.setAttribute("data-done", String(Date.now())); return; }
    ns.slice(0, 8).forEach(function (n) {
      var r = D.names[n];
      if (!r) { h += "<h3><code>np." + esc(n) + "</code></h3><p>Not one of the " + Object.keys(D.names).length + " names this page covers: NumPy " + esc(D.releases[0][0]) + " to " + esc(D.releases[D.releases.length - 1][0]) + " never listed it as removed or deprecated. Check the spelling, or whether it lives in a submodule (np.linalg, np.char).</p>"; return; }
      var segs = [], prev = null;
      r.seq.forEach(function (s, i) { if (s[1] !== prev) { segs.push([s[0], s[1], s[2]]); prev = s[1]; } else segs[segs.length - 1][3] = s[0]; });
      h += "<h3><code>np." + esc(n) + "</code></h3>";
      if (r.fix) h += "<p><strong>Instead:</strong> " + esc(r.fix) + "</p>";
      h += '<div class="tw"><table><thead><tr><th>NumPy</th><th>np.' + esc(n) + '</th></tr></thead><tbody>';
      segs.forEach(function (s) { h += "<tr><td>" + esc(s[0]) + (s[3] ? " to " + esc(s[3]) : "") + '</td><td class="s-' + s[1] + '">' + LBL[s[1]] + (s[1] === "warn" ? " (" + esc(s[2]) + ")" : "") + "</td></tr>"; });
      h += "</tbody></table></div>";
    });
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.NP_READY = true;
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
<p class="lede"><strong>NumPy 1.24.0 ({DATE["1.24.0"]}) removed <code>np.float</code>, <code>np.int</code>, <code>np.bool</code>, <code>np.object</code>, <code>np.str</code>, <code>np.complex</code>, <code>np.long</code> and <code>np.unicode</code>: use the Python builtins (<code>float</code>, <code>int</code>) or NumPy types (<code>np.float64</code>). NumPy 2.0.0 ({DATE["2.0.0"]}) removed {len(n20)} more, among them <code>np.float_</code> (use <code>np.float64</code>), <code>np.NaN</code> (<code>np.nan</code>), <code>np.Inf</code> (<code>np.inf</code>), <code>np.complex_</code> (<code>np.complex128</code>) and <code>np.product</code> (<code>np.prod</code>).</strong> 2.4 removed <code>np.trapz</code> and <code>np.in1d</code>, 2.5 <code>np.row_stack</code>. If the error comes from a library you did not write, upgrade the library or pin NumPy below the release that removed the name. Paste the error below for the release-by-release answer.</p>
<p class="meta">Published {PUB} &middot; {len(VS)} NumPy releases installed and run, {VS[0]} to {LATEST} ({n_runs:,} attribute accesses) &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line, or np.&lt;name&gt;</label>
<textarea id="q" spellcheck="false" placeholder="AttributeError: module 'numpy' has no attribute 'float_'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="numpy_attrs.json">numpy_attrs.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which release removed it, and what replaces it?</h2>
<p><strong>{n_tab} names that worked in one NumPy release and fail in a later one.</strong> "Instead" is NumPy's own text: the error message where it has one, otherwise the deprecation warning the name gave before it went.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Fails from</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>
<p>NumPy 2.4.0 was yanked from PyPI, so the 2.4 row was measured on 2.4.1. <code>np.bool</code> and <code>np.long</code> fail in 1.24 to 1.26 and work again from 2.0, as NumPy types.</p>

<h2 id="how">How was this measured?</h2>
<p><strong>Each of {len(VS)} NumPy releases was installed from PyPI in its own environment and <code>getattr(numpy, name)</code> was run for every name, recording whether it worked, which warning it gave, and the exact AttributeError text.</strong> Releases: {rel_list}. The names are those in the tables NumPy's module <code>__getattr__</code> answers from (<code>__deprecated_attrs__</code>, <code>__expired_functions__</code>, <code>__former_attrs__</code>, <code>__future_scalars__</code>, <code>numpy/_expired_attrs_2_0.py</code>) in the first release of every minor from 1.16, plus a few removed without an entry. Those tables were also read from the source at the release tags: all {VER["confirmed"]} entries predict what the installed release did, with no mismatch.</p>
<p>The table covers access to the attribute. Some names (<code>np.product</code> in 1.25 and 1.26) warn only when called, so they show here as "works".</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>numpy/numpy at the release tags: <a href="https://github.com/numpy/numpy/blob/v2.0.0/numpy/_expired_attrs_2_0.py">numpy/_expired_attrs_2_0.py</a>, <a href="https://github.com/numpy/numpy/blob/v2.0.0/numpy/__init__.py">numpy/__init__.py at v2.0.0</a>, <a href="https://github.com/numpy/numpy/blob/v2.0.0/numpy/core/_multiarray_umath.py">numpy/core/_multiarray_umath.py at v2.0.0</a>.</li>
<li>The wheels of each release on <a href="https://pypi.org/project/numpy/#history">PyPI</a>, which also give the dates.</li>
</ul>
<p>The same data as JSON: <a href="numpy_attrs.json">numpy_attrs.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/torchvision-import-name-version-lookup/">"No module named 'torchvision.transforms.functional_tensor'"</a> &middot; <a href="/en/transformers-import-name-version-lookup/">"cannot import name ... from 'transformers'"</a> &middot; <a href="/en/pydantic-import-name-version-lookup/">"... from 'pydantic'"</a>.</p>
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
(out_dir / "numpy_attrs.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | names %d | releases %d | table rows %d | removed in 2.0: %d (%d with a message)" % (len(page), len(NAMES), len(VS), n_tab, len(n20), len(n20msg)), file=sys.stderr)
