#!/usr/bin/env python3
"""Build en/pandas-removed-attribute-lookup/ (index.html and pandas_attrs.json).

Usage: python3 -I build_page.py probes/ pypi.json out_dir PUBLISHED MODIFIED
probes/: dir_<v>.json (public names), get_<v>.json (getattr of the union in each release), msg_<v>.json (deprecation text read
from the installed source of the last release before each removal). ASCII only; the facts the prose names are asserted.
"""
import html, json, os, re, sys
from pathlib import Path

PD, P = sys.argv[1], json.load(open(sys.argv[2]))
out_dir, PUB, MOD = Path(sys.argv[3]), sys.argv[4], sys.argv[5]
HERE = Path(__file__).resolve().parent
e = html.escape
key = lambda v: tuple(int(x) for x in v.split("."))
VS = sorted((f[4:-5] for f in os.listdir(PD) if f.startswith("get_") and f.endswith(".json")), key=key)
G = {v: json.load(open(os.path.join(PD, "get_%s.json" % v)))["get"] for v in VS}
DIRS = {v: json.load(open(os.path.join(PD, "dir_%s.json" % v))) for v in VS}
MSG = {v[4:-5]: json.load(open(os.path.join(PD, v))) for v in os.listdir(PD) if v.startswith("msg_") and v.endswith(".json")}
DATE = {v: min(f["upload_time"] for f in P["releases"][v])[:10] for v in VS}
LATEST = VS[-1]
OBJ_LABEL = {"pandas": "pd", "DataFrame": "DataFrame", "Series": "Series", "Index": "Index", "DatetimeIndex": "DatetimeIndex",
             "Timestamp": "Timestamp", "DataFrameGroupBy": "DataFrameGroupBy", "SeriesGroupBy": "SeriesGroupBy", "StringMethods": "Series.str"}
# replacements for names whose own code gave no deprecation text we could read (our wording, marked as such on the page)
NOTE = {("DataFrame", "ix"): ".loc for labels, .iloc for positions", ("Series", "ix"): ".loc for labels, .iloc for positions",
        ("DataFrame", "lookup"): "df.loc / df.at, or df.to_numpy()[row_positions, column_positions]",
        ("DataFrame", "mad"): "(df - df.mean()).abs().mean()", ("Series", "mad"): "(s - s.mean()).abs().mean()",
        ("DataFrameGroupBy", "mad"): "an explicit agg, e.g. .agg(lambda x: (x - x.mean()).abs().mean())",
        ("SeriesGroupBy", "mad"): "an explicit agg, e.g. .agg(lambda x: (x - x.mean()).abs().mean())",
        ("DataFrame", "slice_shift"): "shift", ("Series", "slice_shift"): "shift",
        ("Series", "nonzero"): "s.to_numpy().nonzero()", ("Series", "compress"): "s[condition]",
        ("DataFrame", "compound"): "(1 + df).prod() - 1", ("Series", "compound"): "(1 + s).prod() - 1",
        ("DatetimeIndex", "weekday_name"): "day_name()", ("Timestamp", "weekday_name"): "day_name()",
        ("DatetimeIndex", "offset"): "freq", ("Index", "sort"): "sort_values", ("DatetimeIndex", "sort"): "sort_values"}


def state(r):
    return ("warn" if r["warn"] else "ok") if r["ok"] else "gone"


ROWS, REMOVED = {}, []
for k in G[VS[0]]:
    for n in sorted(G[VS[0]][k]):
        seq = [(v, state(G[v][k][n]), (G[v][k][n]["warn"][0][1] if G[v][k][n]["warn"] else G[v][k][n].get("error", ""))) for v in VS]
        rem = None
        for i in range(1, len(seq)):
            if seq[i][1] == "gone" and seq[i - 1][1] != "gone":
                rem = (seq[i][0], seq[i - 1][0])
        if rem is None:
            continue   # never removed: not on this page
        v_last = rem[1]
        msg, src = None, None
        acc = G[v_last][k][n]["warn"]
        if acc:
            msg, src = acc[0][1], "warning on access in %s" % v_last
        elif n in MSG.get(v_last, {}).get(k, {}):
            msg = MSG[v_last][k][n]
            src = "warning in the code of %s" % v_last
            if msg.endswith(" [found by text search]"):
                msg, src = msg[:-len(" [found by text search]")], "warning text in %s that names it" % v_last
        elif (k, n) in NOTE:
            msg, src = "Use " + NOTE[(k, n)] + ".", "our note (%s gave no warning text)" % v_last
        if msg:
            msg = msg.replace("{type(self).__name__}", k if k != "pandas" else "pandas").replace("{obj}", k)
        back = seq[-1][1] != "gone"
        ROWS["%s.%s" % (k, n)] = {"obj": k, "name": n, "seq": [[v, s] for v, s, _ in seq], "removed": rem[0], "last": rem[1],
                                  "fix": msg, "src": src, "back": back}
        REMOVED.append("%s.%s" % (k, n))
gone_now = [r for r in REMOVED if not ROWS[r]["back"]]
by = lambda v: [r for r in gone_now if ROWS[r]["removed"] == v]
R = lambda k, n: ROWS["%s.%s" % (k, n)]
# facts the prose names
for k, n, v in [("DataFrame", "append", "2.0.0"), ("Series", "append", "2.0.0"), ("DataFrame", "iteritems", "2.0.0"), ("Series", "iteritems", "2.0.0"),
                ("DataFrame", "ix", "1.0.0"), ("DataFrame", "as_matrix", "1.0.0"), ("DataFrame", "get_value", "1.0.0"), ("DataFrame", "set_value", "1.0.0"),
                ("pandas", "Int64Index", "2.0.0"), ("pandas", "Float64Index", "2.0.0"), ("pandas", "np", "2.0.0"), ("pandas", "datetime", "2.0.0"),
                ("DataFrame", "applymap", "3.0.0"), ("DataFrame", "swapaxes", "3.0.0"), ("Series", "view", "3.0.0"), ("DataFrame", "bool", "3.0.0"),
                ("DataFrame", "first", "3.0.0"), ("DataFrame", "last", "3.0.0"), ("Index", "is_integer", "3.0.0"), ("Series", "is_monotonic", "2.0.0"),
                ("DataFrame", "lookup", "2.0.0"), ("DataFrame", "mad", "2.0.0"), ("DataFrame", "tshift", "2.0.0"), ("pandas", "read_gbq", "3.0.0")]:
    assert R(k, n)["removed"] == v and not R(k, n)["back"], (k, n, R(k, n)["removed"])
for k, n, want in [("DataFrame", "append", "pandas.concat"), ("DataFrame", "iteritems", ".items"), ("DataFrame", "applymap", "DataFrame.map"),
                   ("DataFrame", "as_matrix", ".values"), ("DataFrame", "get_value", ".at[]"), ("pandas", "Int64Index", "pandas.Index"),
                   ("pandas", "np", "Import numpy directly"), ("Series", "is_monotonic", "is_monotonic_increasing"), ("DataFrame", "ix", ".loc")]:
    assert want in (R(k, n)["fix"] or ""), (k, n, R(k, n)["fix"])
assert R("Series", "flags")["back"] and R("Series", "flags")["removed"] == "1.0.0"
assert [DIRS[v]["pandas"] for v in VS] == VS
n10, n20, n30 = len(by("1.0.0")), len(by("2.0.0")), len(by("3.0.0"))
LAST1 = max((v for v in P["releases"] if re.fullmatch(r"1\.\d+\.\d+", v) and P["releases"][v]), key=key)
assert LAST1 == "1.5.3", LAST1
n_fix = sum(1 for r in gone_now if ROWS[r]["fix"])
n_runs = sum(len(x) for x in G[VS[0]].values()) * len(VS)

DATA = {"releases": [[v, DATE[v], DIRS[v]["python"], DIRS[v]["numpy"]] for v in VS], "labels": OBJ_LABEL, "rows": {r: ROWS[r] for r in REMOVED},
        "names": {k: sorted(set().union(*(DIRS[v]["dir"][k] for v in VS))) for k in OBJ_LABEL}}
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json
URL = "https://erimaki-kobo.github.io/en/pandas-removed-attribute-lookup/"
TITLE = "'DataFrame' object has no attribute 'append' (and others): pandas fix"
H1 = "AttributeError: 'DataFrame' object has no attribute 'append' (or 'iteritems', 'ix', 'applymap', any name): which pandas removed it and what to use"
DESC = ("pandas 2.0 removed DataFrame.append (use pd.concat), iteritems and Int64Index; 3.0 removed applymap. %d removals, checked by running %d releases. Paste the error."
        % (len(gone_now), len(VS)))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))

tab = []
for v in VS:
    for r in sorted(by(v), key=lambda x: (ROWS[x]["obj"] != "DataFrame", ROWS[x]["obj"], ROWS[x]["name"].lower())):
        x = ROWS[r]
        lab = "pd." + x["name"] if x["obj"] == "pandas" else "%s.%s" % (OBJ_LABEL[x["obj"]], x["name"])
        tab.append("<tr><td><code>%s</code></td><td>%s</td><td>%s%s</td></tr>" % (e(lab), v, e(x["fix"] or ""), " <em>(our note)</em>" if (x["src"] or "").startswith("our note") else ""))
tab_html = "\n".join(tab)

FAQ = [
    ("How do I fix \"'DataFrame' object has no attribute 'append'\"?",
     "pandas 2.0.0 (%s) removed DataFrame.append and Series.append; 1.4 and 1.5 warned. Collect the pieces and call pd.concat once: "
     "pd.concat([df, new_rows], ignore_index=True), where new_rows is a DataFrame (pd.DataFrame([row_dict]) for one row). Or pin "
     "pandas<2 (%s is the last 1.x)." % (DATE["2.0.0"], "1.5.3")),
    ("How do I fix \"'DataFrame' object has no attribute 'iteritems'\"?",
     "pandas 2.0.0 removed iteritems; use items(), which yields the same (column name, Series) pairs. Older libraries that call "
     "iteritems need upgrading, or pandas<2."),
    ("How do I fix \"'DataFrame' object has no attribute 'applymap'\"?",
     "pandas 3.0.0 (%s) removed DataFrame.applymap; it was renamed DataFrame.map in 2.1.0, and 2.1 to 2.3 warned. Use df.map(func)." % DATE["3.0.0"]),
    ("How do I fix \"'DataFrame' object has no attribute 'ix'\"?",
     "pandas 1.0.0 (%s) removed .ix. Use .loc for labels and .iloc for positions." % DATE["1.0.0"]),
    ("How do I fix \"module 'pandas' has no attribute 'Int64Index'\"?",
     "pandas 2.0.0 removed Int64Index, UInt64Index and Float64Index. Use pd.Index with a dtype, for example pd.Index([1, 2], dtype='int64'). "
     "The same release removed pd.np (import numpy) and pd.datetime (import datetime)."),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["pandas", "AttributeError", "pandas 2.0 migration", "pandas 3.0 migration"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "pandas removed attribute lookup", "url": URL + "#lookup",
     "description": "Paste an AttributeError from pandas and get, for each pandas release from %s to %s, whether the attribute exists, and what to use instead." % (VS[0], LATEST),
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "pandas attributes by release", "url": URL + "pandas_attrs.json", "dateModified": MOD,
     "description": "The public attributes of the pandas module, DataFrame, Series, Index, DatetimeIndex, Timestamp, the groupby objects and Series.str in %d installed pandas releases (%s to %s), and the deprecation text before each removal." % (len(VS), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "pandas_attrs.json"}]},
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
EX = [("AttributeError: 'DataFrame' object has no attribute 'append'", "append"), ("AttributeError: 'Series' object has no attribute 'iteritems'", "iteritems"),
      ("AttributeError: 'DataFrame' object has no attribute 'applymap'", "applymap"), ("AttributeError: module 'pandas' has no attribute 'Int64Index'", "Int64Index"),
      ("df.ix[0, 'a']", "ix")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
rel_list = ", ".join("%s (Python %s, NumPy %s)" % (v, DIRS[v]["python"].rsplit(".", 1)[0], DIRS[v]["numpy"]) for v in VS)
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var LBL = {ok: "has it", warn: "has it, warns on access", gone: "AttributeError"};
  var OBJ = {"DataFrame": "DataFrame", "Series": "Series", "Index": "Index", "DatetimeIndex": "DatetimeIndex", "Timestamp": "Timestamp",
             "DataFrameGroupBy": "DataFrameGroupBy", "SeriesGroupBy": "SeriesGroupBy", "StringMethods": "StringMethods", "pandas": "pandas",
             "Int64Index": "Index", "RangeIndex": "Index", "MultiIndex": "Index", "Float64Index": "Index", "CategoricalIndex": "Index"};
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function find(t) {
    var out = [], m, re = /'(\w+)' object has no attribute '(\w+)'|module 'pandas' has no attribute '(\w+)'|\b(?:pd|pandas)\.(\w+)|\.(\w+)\b/g;
    while ((m = re.exec(t))) {
      if (m[2]) out.push([OBJ[m[1]] || m[1], m[2], true]);
      else if (m[3]) out.push(["pandas", m[3], true]);
      else if (m[4]) out.push(["pandas", m[4], false]);
      else if (m[5]) out.push([null, m[5], false]);
    }
    return out;
  }
  function rowsFor(o, n) {
    var r = [];
    Object.keys(D.rows).forEach(function (k) { var x = D.rows[k]; if (x.name === n && (!o || x.obj === o)) r.push(x); });
    if (!r.length && o && o !== "pandas") Object.keys(D.rows).forEach(function (k) { var x = D.rows[k]; if (x.name === n && x.obj !== "pandas") r.push(x); });
    return r;
  }
  function show() {
    var hits = find(q.value), h = "", seen = {};
    hits.forEach(function (t) {
      var rs = rowsFor(t[0], t[1]);
      if (!rs.length) {
        if (!t[2] || seen["?" + t[1]]) return; seen["?" + t[1]] = 1;
        var where = Object.keys(D.names).filter(function (k) { return D.names[k].indexOf(t[1]) >= 0; });
        h += "<h3><code>" + esc(t[1]) + "</code></h3><p>" + (where.length ? "Not removed in any release read: it exists on " + where.map(function (k) { return esc(D.labels[k]); }).join(", ") + " in " + esc(D.releases[D.releases.length - 1][0]) + ". Check the object the error names (a DataFrame where a Series was expected, or the reverse)."
             : "No release from " + esc(D.releases[0][0]) + " to " + esc(D.releases[D.releases.length - 1][0]) + " has this name on the objects this page covers. Check the spelling, or whether it is a column name (df['" + esc(t[1]) + "'])." ) + "</p>";
        return;
      }
      rs.forEach(function (x) {
        var k = x.obj + "." + x.name; if (seen[k]) return; seen[k] = 1;
        var lab = x.obj === "pandas" ? "pd." + x.name : D.labels[x.obj] + "." + x.name, segs = [], prev = null;
        x.seq.forEach(function (s) { if (s[1] !== prev) { segs.push([s[0], s[1]]); prev = s[1]; } else segs[segs.length - 1][2] = s[0]; });
        h += "<h3><code>" + esc(lab) + "</code></h3><p><strong>Removed in pandas " + esc(x.removed) + "</strong> (last in " + esc(x.last) + ")" + (x.back ? "; a different attribute of the same name exists again later" : "") + ".";
        if (x.fix) h += " <strong>Instead:</strong> " + esc(x.fix) + " <span class=\"note\">(" + esc(x.src) + ")</span>";
        h += "</p><p>To keep it: <code>pip install \"pandas&lt;" + esc(x.removed) + "\"</code></p><div class=\"tw\"><table><thead><tr><th>pandas</th><th>" + esc(lab) + "</th></tr></thead><tbody>";
        segs.forEach(function (s) { h += "<tr><td>" + esc(s[0]) + (s[2] ? " to " + esc(s[2]) : "") + '</td><td class="s-' + s[1] + '">' + LBL[s[1]] + "</td></tr>"; });
        h += "</tbody></table></div>";
      });
    });
    if (!h) h = "<p>Paste the AttributeError line, for example 'DataFrame' object has no attribute 'append'.</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.PD_READY = true;
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
<p class="lede"><strong>pandas 2.0.0 ({DATE["2.0.0"]}) removed <code>DataFrame.append</code> and <code>Series.append</code> (use <code>pd.concat</code>), <code>iteritems</code> (use <code>items</code>), <code>Int64Index</code> and <code>Float64Index</code> (use <code>pd.Index</code>) and {n20 - 6} more; pandas 3.0.0 ({DATE["3.0.0"]}) removed <code>DataFrame.applymap</code> (use <code>DataFrame.map</code>) and {n30 - 1} more; pandas 1.0.0 removed <code>.ix</code> (use <code>.loc</code> or <code>.iloc</code>) and {n10 - 1} more.</strong> For {n_fix} of the {len(gone_now)} the last release that had the name gives a deprecation text, quoted in the table. If the error comes from a library you did not write, upgrade the library or pin pandas below the release that removed the name. Paste the error below for the release-by-release answer.</p>
<p class="meta">Published {PUB} &middot; {len(VS)} pandas releases installed and run, {VS[0]} to {LATEST} ({n_runs:,} attribute accesses) &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line</label>
<textarea id="q" spellcheck="false" placeholder="AttributeError: 'DataFrame' object has no attribute 'append'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="pandas_attrs.json">pandas_attrs.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which release removed it, and what replaces it?</h2>
<p><strong>{len(gone_now)} attributes of the pandas module, DataFrame, Series, Index, DatetimeIndex, Timestamp, the groupby objects and <code>Series.str</code> that one release has and a later one does not.</strong> "Instead" is pandas' own deprecation text from the last release that had the name ({n_fix} of {len(gone_now)}), except where marked as our note.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Removed in</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>

<h2 id="how">How was this measured?</h2>
<p><strong>Each of {len(VS)} pandas releases (the first of every minor from {VS[0]}, plus the latest) was installed from PyPI in its own environment, the public names of each object were listed with <code>dir()</code>, and <code>getattr</code> was run for the union of all names in every release.</strong> Releases: {rel_list}. A name is "removed" when <code>getattr</code> on the class (or the module) raises in a release after one where it worked. The replacement text is the string the name's own code passed to <code>warnings.warn</code> in the last release that had it, read from the installed source with <code>inspect</code> and <code>ast</code> (or, for module attributes, the warning given on access); where the code had none, a warning elsewhere in pandas that names it, or our note.</p>
<p>Patch releases were not read: a name removed in x.y.1 shows at the next minor. <code>Series.flags</code> went in 1.0.0 and came back in 1.2.0 with a different meaning.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The pandas wheels on <a href="https://pypi.org/project/pandas/#history">PyPI</a>, installed and run, and their source as installed; the release dates are PyPI's.</li>
<li>pandas release notes: <a href="https://pandas.pydata.org/docs/whatsnew/v2.0.0.html">2.0.0</a>, <a href="https://pandas.pydata.org/docs/whatsnew/v3.0.0.html">3.0.0</a>.</li>
</ul>
<p>The same data as JSON: <a href="pandas_attrs.json">pandas_attrs.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a> &middot; <a href="/en/pydantic-import-name-version-lookup/">"cannot import name 'BaseSettings' from 'pydantic'"</a> &middot; <a href="/en/datasets-import-name-version-lookup/">"... from 'datasets'"</a>.</p>
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
(out_dir / "pandas_attrs.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | removed now %d (1.0: %d, 2.0: %d, 3.0: %d) | with text %d | releases %d" % (len(page), len(gone_now), n10, n20, n30, n_fix, len(VS)), file=sys.stderr)
