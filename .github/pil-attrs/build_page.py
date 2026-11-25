#!/usr/bin/env python3
"""Build en/pillow-removed-name-lookup/ (index.html and pillow_names.json).

Usage: python3 -I build_page.py probes/ notes.json pypi.json out_dir PUBLISHED MODIFIED
probes/: dir_<v>.json (public names, __all__ and submodules), get_<v>.json (getattr, or import for a submodule, of the union in
each release), msg_<v>.json (deprecation text in the last release before each removal). notes.json: replacements for removals whose code gave no text.
ASCII only; the facts the prose names are asserted. style.css is shared with .github/llama-args.
"""
import __future__, html, json, os, re, sys, typing
from pathlib import Path

PD, PRE, P = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
DATES_EXTRA = []
SKIP = {"PIL.ImageTk", "PIL.ImageQt", "PIL.ImageGrab"}   # need tkinter / Qt / a display: their import depends on the environment
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
NOISE = set(__future__.all_feature_names) | set(typing.__all__) | set(sys.stdlib_module_names) | {"numpy", "deprecate"}


def clean(msg, n):
    msg = msg.replace("%s", n)
    if "{}" in msg:
        msg = msg.replace("{}", n, 1)
    return " ".join(s for s in re.split(r"(?<=\.)\s+", msg) if "{}" not in s and "{...}" not in s).strip()


ROWS = {}
for k in G[VS[-1]]:
    if k in SKIP:
        continue
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
        is_mod = False
        has_text = bool(G[last][k][n]["warn"]) or n in MSG.get(last, {}).get(k, {}) or (k, n) in [tuple(x) for x in PRE["keep"]]
        if n in NOISE or not (":" in k or has_text):
            continue   # Pillow's modules have no __all__: keep class members and names Pillow itself deprecated
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
for (k, n), x in ((tuple(k.split("|")), x) for k, x in PRE["notes"].items()):
    r = ROWS.get("%s.%s" % (k, n))
    if r and not r["fix"]:
        r["fix"], r["src"] = x, "our note"
R = lambda k, n: ROWS["%s.%s" % (k, n)]
rest = list(ROWS.values())
mods = [r for r in rest if r["module"]]
names_ = [r for r in rest if not r["module"]]
# facts the prose names
for k, n, v in [("PIL.Image", "ANTIALIAS", "10.0.0"), ("PIL.Image", "LINEAR", "10.0.0"), ("PIL.Image", "CUBIC", "10.0.0"),
                ("PIL.ImageDraw:ImageDraw", "textsize", "10.0.0"), ("PIL.ImageDraw:ImageDraw", "multiline_textsize", "10.0.0"),
                ("PIL.ImageFont:FreeTypeFont", "getsize", "10.0.0"), ("PIL.ImageFont:ImageFont", "getsize", "10.0.0"),
                ("PIL.ImageFont:FreeTypeFont", "getoffset", "10.0.0"), ("PIL.ImageMath", "eval", "12.0.0"), ("PIL.Image", "isImageType", "12.0.0"),
                ("PIL.Image:Image", "tostring", "8.0.0"), ("PIL.Image:Image", "get_child_images", "13.0.0")]:
    assert R(k, n)["removed"] == v, (k, n, R(k, n)["removed"])
for k, n, want in [("PIL.Image", "ANTIALIAS", "LANCZOS"), ("PIL.ImageDraw:ImageDraw", "textsize", "textbbox or textlength"),
                   ("PIL.ImageFont:FreeTypeFont", "getsize", "getbbox or getlength"), ("PIL.ImageMath", "eval", "lambda_eval"),
                   ("PIL.Image", "isImageType", "isinstance"), ("PIL.Image", "LINEAR", "BILINEAR"), ("PIL.Image", "CUBIC", "BICUBIC")]:
    assert want in (R(k, n)["fix"] or ""), (k, n, R(k, n)["fix"])
assert R("PIL.Image", "ANTIALIAS")["seq"][VS.index("9.1.0")][1] == "warn" and R("PIL.Image", "ANTIALIAS")["seq"][VS.index("9.0.0")][1] == "ok"
rest = list(ROWS.values())
r10 = [r for r in rest if r["removed"] == "10.0.0"]
n_fix = sum(1 for r in rest if r["fix"] and r["src"] not in ("this page's data", "our note"))
n_data = sum(1 for r in rest if r["src"] in ("this page's data", "our note"))
n_runs = sum(len(x) for k, x in G[VS[0]].items() if k not in SKIP) * len(VS)
CODE = {"ok": "o", "warn": "w", "gone": "g"}
ROWS_OUT = {kk: dict(r, seq="".join(CODE[s[1]] for s in r["seq"])) for kk, r in ROWS.items()}
DATA = {"releases": [[v, DATE[v], DIRS[v]["python"]] for v in VS], "rows": ROWS_OUT,
        "names": {k: sorted(set().union(*(DIRS[v]["dir"].get(k, []) for v in VS))) for k in G[VS[-1]]}}
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json
URL = "https://erimaki-kobo.github.io/en/pillow-removed-name-lookup/"
TITLE = "module 'PIL.Image' has no attribute 'ANTIALIAS' (and textsize): fix"
H1 = "AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS' (or 'ImageDraw' object has no attribute 'textsize', 'getsize', any name): which Pillow removed it and what to use"
DESC = ("Pillow 10 removed Image.ANTIALIAS (use Image.LANCZOS), ImageDraw.textsize and font.getsize (use textbbox, getbbox); 12 removed ImageMath.eval. %d releases run."
        % len(VS))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))

tab = []
for r in sorted(rest, key=lambda x: (key(x["removed"]), x["obj"], x["name"].lower())):
    tab.append("<tr><td><code>%s.%s</code></td><td>%s</td><td>%s%s</td></tr>" % (e(LAB(r["obj"])), e(r["name"]), r["removed"], e(r["fix"] or ""), " <em>(our note)</em>" if r["src"] == "our note" else ""))
tab_html = "\n".join(tab)
FAQ = [
    ("How do I fix \"module 'PIL.Image' has no attribute 'ANTIALIAS'\"?",
     "Pillow 10.0.0 (%s) removed Image.ANTIALIAS; 9.1 to 9.5 warned. Use Image.LANCZOS (the same filter), or Image.Resampling.LANCZOS, "
     "which exists from 9.1.0: img.resize((w, h), Image.LANCZOS). The same release removed Image.LINEAR (use BILINEAR) and Image.CUBIC "
     "(use BICUBIC). If the error comes from a library, upgrade it, or pin pillow<10." % DATE["10.0.0"]),
    ("How do I fix \"'ImageDraw' object has no attribute 'textsize'\"?",
     "Pillow 10.0.0 removed ImageDraw.textsize and multiline_textsize. Use draw.textbbox((0, 0), text, font=font), which returns "
     "(left, top, right, bottom): width = right - left, height = bottom - top; or draw.textlength(text, font=font) for the width alone."),
    ("How do I fix \"'FreeTypeFont' object has no attribute 'getsize'\"?",
     "Pillow 10.0.0 removed font.getsize, getsize_multiline and getoffset. Use font.getbbox(text) (left, top, right, bottom) or "
     "font.getlength(text) for the advance width."),
    ("How do I fix \"module 'PIL.ImageMath' has no attribute 'eval'\"?",
     "Pillow 12.0.0 (%s) removed ImageMath.eval. Use ImageMath.lambda_eval with a function, or ImageMath.unsafe_eval for a string "
     "expression you trust (it runs Python code)." % DATE["12.0.0"]),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["Pillow", "PIL", "AttributeError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "Pillow removed name lookup", "url": URL + "#lookup",
     "description": "Paste an AttributeError from PIL and get, for each Pillow release from %s to %s, whether the name exists, and what to use instead." % (VS[0], LATEST),
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Pillow names by release", "url": URL + "pillow_names.json", "dateModified": MOD,
     "description": "The public names of %d PIL modules and of Image, ImageDraw, FreeTypeFont and ImageFont in %d installed Pillow releases (%s to %s), and the deprecation text before each removal." % (len(G[VS[-1]]) - 4 - len(SKIP), len(VS), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "pillow_names.json"}]},
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
EX = [("AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'", "ANTIALIAS"), ("AttributeError: 'ImageDraw' object has no attribute 'textsize'", "textsize"),
      ("AttributeError: 'FreeTypeFont' object has no attribute 'getsize'", "getsize"), ("AttributeError: module 'PIL.ImageMath' has no attribute 'eval'", "ImageMath.eval")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
rel_list = ", ".join("%s (Python %s)" % (v, DIRS[v]["python"].rsplit(".", 1)[0]) for v in VS)
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var LBL = {ok: "has it", warn: "has it, warns on access", gone: "not there"};
  var CLS = {ImageDraw: "PIL.ImageDraw:ImageDraw", FreeTypeFont: "PIL.ImageFont:FreeTypeFont", ImageFont: "PIL.ImageFont:ImageFont", Image: "PIL.Image:Image", PngImageFile: "PIL.Image:Image", JpegImageFile: "PIL.Image:Image"};
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function find(t) {
    var out = [], m;
    var re = /cannot import name '(\w+)' from '(PIL(?:\.\w+)*)'|module '(PIL(?:\.\w+)*)' has no attribute '(\w+)'|'(\w+)' object has no attribute '(\w+)'|from (PIL(?:\.\w+)*) import ([\w ,()]+)|\b(PIL(?:\.\w+)+)/g;
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
      if (t[0] && !D.names[t[0]] && t[0].indexOf(".") > 0) {   // a module path in the import: the module itself may be gone
        var par = t[0].slice(0, t[0].lastIndexOf(".")), leaf = t[0].slice(t[0].lastIndexOf(".") + 1);
        var mr = Object.keys(D.rows).map(function (k) { return D.rows[k]; }).filter(function (x) { return x.module && x.obj === par && x.name === leaf; });
        if (mr.length) rs = mr.concat(rs);
      }
      if (!rs.length) {
        if (seen["?" + t[1]]) return; seen["?" + t[1]] = 1;
        var where = Object.keys(D.names).filter(function (k) { return D.names[k].indexOf(t[1]) >= 0; });
        if (!t[0] && !where.length) return;
        h += "<h3><code>" + esc((t[0] ? t[0].replace(":", ".") + "." : "") + t[1]) + "</code></h3><p>" + (where.length ? "Not removed in any release read: " + esc(t[1]) + " is in " + where.map(function (k) { return esc(k.replace(":", ".")); }).join(", ") + " in " + esc(D.releases[D.releases.length - 1][0]) + "." : "No Pillow release from " + esc(D.releases[0][0]) + " to " + esc(D.releases[D.releases.length - 1][0]) + " has this name in the modules this page covers.") + "</p>";
        return;
      }
      rs.forEach(function (x) {
        var k = x.obj + "." + x.name; if (seen[k]) return; seen[k] = 1;
        var lab = x.obj.replace(":", ".") + "." + x.name, segs = [], prev = null;
        x.seq.split("").forEach(function (c, i) { var st = {o: "ok", w: "warn", g: "gone"}[c], v = D.releases[i][0]; if (st !== prev) { segs.push([v, st]); prev = st; } else segs[segs.length - 1][2] = v; });
        h += "<h3><code>" + esc(lab) + "</code>" + (x.module ? " (module)" : "") + "</h3><p><strong>Removed in Pillow " + esc(x.removed) + "</strong> (last in " + esc(x.last) + ").";
        if (x.fix) h += " <strong>Instead:</strong> " + esc(x.fix) + ' <span class="note">(' + esc(x.src) + ")</span>";
        h += '</p><p>To keep it: <code>pip install "pillow&lt;' + esc(x.removed) + '"</code></p>';
        if (!x.pre) {
          h += '<div class="tw"><table><thead><tr><th>Pillow</th><th>' + esc(lab) + "</th></tr></thead><tbody>";
          segs.forEach(function (s) { h += "<tr><td>" + esc(s[0]) + (s[2] ? " to " + esc(s[2]) : "") + '</td><td class="s-' + s[1] + '">' + LBL[s[1]] + "</td></tr>"; });
          h += "</tbody></table></div>";
        } else h += "<p>Read from the source at the release tags (before the first release installed here, " + esc(D.releases[0][0]) + ").</p>";
      });
    });
    if (!h) h = "<p>Paste the AttributeError line, for example module 'PIL.Image' has no attribute 'ANTIALIAS'.</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.PIL_READY = true;
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
<p class="lede"><strong>Pillow 10.0.0 ({DATE["10.0.0"]}) removed <code>Image.ANTIALIAS</code> (use <code>Image.LANCZOS</code>), <code>Image.LINEAR</code> and <code>Image.CUBIC</code> (<code>BILINEAR</code>, <code>BICUBIC</code>), <code>ImageDraw.textsize</code> (use <code>textbbox</code> or <code>textlength</code>) and <code>font.getsize</code> (use <code>getbbox</code> or <code>getlength</code>); 9.1 to 9.5 warned. Pillow 12.0.0 removed <code>ImageMath.eval</code> (use <code>lambda_eval</code> or <code>unsafe_eval</code>).</strong> If the error comes from a library you did not write, upgrade the library or pin Pillow below the release that removed the name. Paste the error below for the release-by-release answer.</p>
<p class="meta">Published {PUB} &middot; {len(VS)} Pillow releases installed and run, {VS[0]} to {LATEST} ({n_runs:,} lookups) &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line</label>
<textarea id="q" spellcheck="false" placeholder="AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="pillow_names.json">pillow_names.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which release removed it, and what replaces it?</h2>
<p><strong>{len(rest)} names that one Pillow release has and a later one does not</strong> ({len(r10)} of them in 10.0.0). "Instead" is Pillow's own deprecation text from the last release that had the name ({n_fix} of {len(rest)}), except where marked.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Removed in</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>

<h2 id="how">How was this measured?</h2>
<p><strong>Each of {len(VS)} Pillow releases (every minor from {VS[0]}, plus the latest) was installed from PyPI in its own environment, the public names of the PIL modules and of the Image, ImageDraw, FreeTypeFont and ImageFont classes were listed with <code>dir()</code>, and <code>getattr</code> was run for the union of all names in every release.</strong> Releases: {rel_list}. Pillow's modules have no <code>__all__</code>, so the table keeps class members and the names Pillow itself deprecated (a warning on access, or a <code>deprecate()</code> call or warning in the definition); helpers a module merely imported are left out, but the lookup still answers for them. The text is read from the installed source of the last release that had the name; Pillow's <code>deprecate("textsize", 10, "textbbox or textlength")</code> calls are turned into the sentence its helper prints. ImageTk, ImageQt and ImageGrab were not read (their import depends on tkinter, Qt or a display).</p>
<p>Patch releases were not read: a name removed in x.y.1 shows at the next minor.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The Pillow wheels on <a href="https://pypi.org/project/pillow/#history">PyPI</a>, installed and run, and their source as installed (PIL/_deprecate.py for the wording); the release dates are PyPI's.</li>
<li><a href="https://pillow.readthedocs.io/en/stable/deprecations.html">Pillow's list of deprecations and removals</a>.</li>
</ul>
<p>The same data as JSON: <a href="pillow_names.json">pillow_names.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/torchvision-import-name-version-lookup/">"No module named 'torchvision.transforms.functional_tensor'"</a> &middot; <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a> &middot; <a href="/en/scipy-removed-name-lookup/">"cannot import name 'imread' from 'scipy.misc'"</a>.</p>
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
(out_dir / "pillow_names.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | removals %d (10.0: %d) | with text %d, notes/data %d | releases %d" % (len(page), len(rest), len(r10), n_fix, n_data, len(VS)), file=sys.stderr)
