#!/usr/bin/env python3
"""Build en/matplotlib-removed-name-lookup/ (index.html and matplotlib_names.json).

Usage: python3 -I build_page.py probes/ notes.json pypi.json out_dir PUBLISHED MODIFIED
probes/: dir_<v>.json (public names, __all__, submodules, style.available), get_<v>.json (getattr, or import for a submodule, of the
union in each release), inst_<v>.json (hasattr on a real object of each class), style_<v>.json (plt.style.use of every style name),
msg_<v>.json (deprecation text in the last release before each removal). notes.json: replacements for removals whose code gave no text.
ASCII only; the facts the prose names are asserted. style.css is shared with .github/llama-args.
"""
import __future__, html, json, os, re, sys, typing
from pathlib import Path

PD, PRE, P = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
DATES_EXTRA = []
SKIP = set()
out_dir, PUB, MOD = Path(sys.argv[4]), sys.argv[5], sys.argv[6]
HERE = Path(__file__).resolve().parent
e = html.escape
key = lambda v: tuple(int(x) for x in v.split("."))
VS = sorted((f[4:-5] for f in os.listdir(PD) if f.startswith("get_") and f.endswith(".json")), key=key)
G = {v: json.load(open(os.path.join(PD, "get_%s.json" % v)))["get"] for v in VS}
DIRS = {v: json.load(open(os.path.join(PD, "dir_%s.json" % v))) for v in VS}
INST = {v: json.load(open(os.path.join(PD, "inst_%s.json" % v)))["inst"] for v in VS}
STY = {v: json.load(open(os.path.join(PD, "style_%s.json" % v)))["styles"] for v in VS}
MSG = {f[4:-5]: json.load(open(os.path.join(PD, f))) for f in os.listdir(PD) if f.startswith("msg_") and f.endswith(".json")}
DATE = {v: min(f["upload_time"] for f in P["releases"][v])[:10] for v in (VS + DATES_EXTRA)}
LATEST = VS[-1]
LAB = lambda k: k.replace(":", ".")
NOISE = set(__future__.all_feature_names) | set(typing.__all__) | set(sys.stdlib_module_names) | {"numpy", "np", "ma", "mpl", "matplotlib", "cbook", "Number", "Integral", "Real"}


def clean(msg, n):
    msg = msg.replace("%s", n).replace("``", "")
    if "{}" in msg:
        msg = msg.replace("{}", n, 1)
    return " ".join(s for s in re.split(r"(?<=\.)\s+", msg) if "{}" not in s and "{...}" not in s).strip()


ROWS = {}
for k in G[VS[-1]]:
    if k in SKIP:
        continue
    for n in sorted(G[VS[-1]][k]):
        seq = [(v, ("warn" if G[v][k][n]["warn"] else "ok") if G[v][k][n]["ok"] else "ok" if INST[v].get(k, {}).get(n) else "gone") for v in VS]
        rem = None
        for i in range(1, len(seq)):
            if seq[i][1] == "gone" and seq[i - 1][1] != "gone":
                rem = (seq[i][0], seq[i - 1][0])
        if rem is None or seq[-1][1] != "gone":
            continue
        last = rem[1]
        allv = DIRS[last]["all"].get(k)
        is_mod = bool(G[last][k][n].get("module"))
        has_text = bool(G[last][k][n]["warn"]) or n in MSG.get(last, {}).get(k, {}) or (k, n) in [tuple(x) for x in PRE["keep"]]
        in_all = n in (allv or [])
        mirror = k == "matplotlib.pyplot" and any(":" in k2 and n in G[last][k2] and G[last][k2][n]["ok"] and not G[rem[0]][k2][n]["ok"] for k2 in G[last])
        if n in NOISE or not (":" in k or has_text or in_all or mirror):
            continue   # most matplotlib modules have no __all__: keep class members, __all__ names and names matplotlib deprecated
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
        gaps = [seq[i][0] for i in range(1, len(seq)) if seq[i][1] == "gone" and any(x[1] != "gone" for x in seq[:i]) and any(x[1] != "gone" for x in seq[i:])]
        ROWS["%s.%s" % (k, n)] = {"obj": k, "name": n, "seq": [list(s) for s in seq], "removed": rem[0], "last": rem[1], "fix": msg, "src": src, "module": is_mod, "gaps": gaps}
for r in ROWS.values():   # no text: the same name still public in another module of the latest release
    if r["fix"] or r["module"]:
        continue
    alive = [k2 for k2 in G[LATEST] if k2 != r["obj"] and ":" not in k2 and r["name"] in DIRS[LATEST]["all"].get(k2, DIRS[LATEST]["dir"].get(k2, []))
             and G[LATEST][k2].get(r["name"], {}).get("ok")]
    if alive:
        r["fix"] = "From %s import %s (still there in %s)." % (alive[0], r["name"], LATEST)
        r["src"] = "this page's data"
for r in ROWS.values():   # pyplot wrappers (plt.plot_date) carry no text of their own: use the Axes method's, removed in the same release
    if r["obj"] == "matplotlib.pyplot" and not r["fix"]:
        m = [r2 for r2 in ROWS.values() if r2["obj"] in ("matplotlib.axes:Axes", "matplotlib.figure:Figure") and r2["name"] == r["name"] and r2["removed"] == r["removed"] and r2["fix"]]
        if m:
            r["fix"], r["src"] = m[0]["fix"], "the text of %s.%s" % (LAB(m[0]["obj"]), r["name"])
for (k, n), x in ((tuple(k.split("|")), x) for k, x in PRE["notes"].items()):
    r = ROWS.get("%s.%s" % (k, n))
    if r and not r["fix"]:
        r["fix"], r["src"] = x, "our note"
# style names: plt.style.use(name) in every release
SNAMES = sorted(STY[LATEST])
for n in SNAMES:
    seq = [(v, ("warn" if STY[v][n]["warn"] else "ok") if STY[v][n]["ok"] else "gone") for v in VS]
    rem = None
    for i in range(1, len(seq)):
        if seq[i][1] == "gone" and seq[i - 1][1] != "gone":
            rem = (seq[i][0], seq[i - 1][0])
    if rem is None or seq[-1][1] != "gone":
        continue
    new = n.replace("seaborn", "seaborn-v0_8", 1)
    assert new in SNAMES and STY[LATEST][new]["ok"] and not STY[LATEST][new]["warn"], n
    assert any("seaborn-v0_8-" in w[0] for v in VS for w in [STY[v][n]["warn"]] if w)   # matplotlib's own warning names the new style
    ROWS["style." + n] = {"obj": "style", "name": n, "seq": [list(x) for x in seq], "removed": rem[0], "last": rem[1], "module": False, "gaps": [],
                          "fix": "plt.style.use(%r): the same style under the name matplotlib gave it in %s (still there in %s), or seaborn's own seaborn.set_theme()." % (new, next(v for v in VS if STY[v][new]["ok"]), LATEST),
                          "src": "plt.style.use run in every release"}
R = lambda k, n: ROWS["%s.%s" % (k, n)]
rest = list(ROWS.values())
mods = [r for r in rest if r["module"]]
names_ = [r for r in rest if not r["module"]]
# facts the prose names
for k, n, v in [("matplotlib.cm", "get_cmap", "3.11.0"), ("matplotlib.cm", "register_cmap", "3.9.0"), ("matplotlib.pyplot", "register_cmap", "3.9.0"),
                ("matplotlib.legend:Legend", "legendHandles", "3.9.0"), ("matplotlib.backends.backend_agg:FigureCanvasAgg", "tostring_rgb", "3.10.0"),
                ("matplotlib.axes:Axes", "plot_date", "3.11.0"), ("matplotlib.pyplot", "plot_date", "3.11.0"), ("matplotlib", "docstring", "3.8.0"),
                ("mpl_toolkits.mplot3d.axes3d:Axes3D", "w_xaxis", "3.8.0"), ("mpl_toolkits.mplot3d.axes3d:Axes3D", "dist", "3.8.0"),
                ("matplotlib.cbook", "mplDeprecation", "3.8.0"), ("matplotlib.colorbar:Colorbar", "draw_all", "3.8.0")]:
    assert R(k, n)["removed"] == v, (k, n, R(k, n)["removed"])
assert R("matplotlib.cm", "get_cmap")["gaps"] == ["3.9.0"], R("matplotlib.cm", "get_cmap")["gaps"]
assert R("matplotlib.legend:Legend", "legendHandles")["seq"][0][1] == "ok"   # on the object before 3.7, on the class 3.7 to 3.8
for k, n, want in [("matplotlib.cm", "get_cmap", "matplotlib.colormaps[name]"), ("matplotlib.legend:Legend", "legendHandles", "legend_handles"),
                   ("matplotlib.backends.backend_agg:FigureCanvasAgg", "tostring_rgb", "buffer_rgba"), ("matplotlib.axes:Axes", "plot_date", "plot"),
                   ("matplotlib.cm", "register_cmap", "matplotlib.colormaps.register"), ("style", "seaborn-whitegrid", "seaborn-v0_8-whitegrid")]:
    assert want in (R(k, n)["fix"] or ""), (k, n, R(k, n)["fix"])
assert G[LATEST]["matplotlib.pyplot"]["get_cmap"]["ok"] and G[LATEST]["matplotlib"]["colormaps"]["ok"]
assert G[LATEST]["matplotlib.backends.backend_agg:FigureCanvasAgg"]["tostring_argb"]["ok"] and G[LATEST]["matplotlib.backends.backend_agg:FigureCanvasAgg"]["buffer_rgba"]["ok"]
assert R("style", "seaborn")["removed"] == "3.8.0" and R("style", "seaborn")["seq"][VS.index("3.6.0")][1] == "warn" and R("style", "seaborn")["seq"][VS.index("3.5.3")][1] == "ok"
assert "3.9.1" not in VS and all(f.get("yanked") for f in P["releases"]["3.9.1"])
rest = list(ROWS.values())
sty = [r for r in rest if r["obj"] == "style"]
n_fix = sum(1 for r in rest if r["fix"] and r["obj"] != "style" and r["src"] not in ("this page's data", "our note"))
n_data = sum(1 for r in rest if r["src"] in ("this page's data", "our note"))
n_runs = sum(len(x) for k, x in G[VS[0]].items()) * len(VS)
CODE = {"ok": "o", "warn": "w", "gone": "g"}
ROWS_OUT = {kk: dict(r, seq="".join(CODE[s[1]] for s in r["seq"])) for kk, r in ROWS.items()}
DATA = {"releases": [[v, DATE[v], DIRS[v]["python"]] for v in VS], "rows": ROWS_OUT,
        "names": {k: sorted(set().union(*(DIRS[v]["dir"].get(k, []) for v in VS))) for k in G[VS[-1]]}}
DATA["names"]["style"] = SNAMES
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json
URL = "https://erimaki-kobo.github.io/en/matplotlib-removed-name-lookup/"
TITLE = "module 'matplotlib.cm' has no attribute 'get_cmap' (and tostring_rgb): fix"
H1 = "AttributeError: module 'matplotlib.cm' has no attribute 'get_cmap' (or 'FigureCanvasAgg' object has no attribute 'tostring_rgb', 'seaborn' is not a valid package style, any name): which matplotlib removed it and what to use"
DESC = ("matplotlib 3.11 removed cm.get_cmap (use matplotlib.colormaps[name]), 3.10 tostring_rgb (use buffer_rgba), 3.8 the 'seaborn' styles. %d releases installed and run."
        % len(VS))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))

tab = []
for r in sorted(rest, key=lambda x: (key(x["removed"]), x["obj"], x["name"].lower())):
    lab = "plt.style.use(%r)" % r["name"] if r["obj"] == "style" else "%s.%s" % (LAB(r["obj"]), r["name"])
    tab.append("<tr><td><code>%s</code></td><td>%s%s</td><td>%s%s</td></tr>" % (e(lab), r["removed"], " (also missing in %s)" % ", ".join(r["gaps"]) if r["gaps"] else "",
                                                                        e(r["fix"] or ""), " <em>(our note)</em>" if r["src"] == "our note" else ""))
tab_html = "\n".join(tab)
FAQ = [
    ("How do I fix \"module 'matplotlib.cm' has no attribute 'get_cmap'\"?",
     "matplotlib 3.11.0 (%s) removed matplotlib.cm.get_cmap; it was deprecated in 3.7. 3.9.0 had removed it too; 3.9.1 (yanked on PyPI) and 3.9.2 put it back. "
     "Use matplotlib.colormaps[name] (from 3.5.0) or matplotlib.colormaps.get_cmap(name), or plt.get_cmap(name), which is still in %s. "
     "cm.register_cmap went in 3.9.0: use matplotlib.colormaps.register(cmap, name=...)." % (DATE["3.11.0"], LATEST)),
    ("How do I fix \"'FigureCanvasAgg' object has no attribute 'tostring_rgb'\"?",
     "matplotlib 3.10.0 (%s) removed tostring_rgb; it was deprecated in 3.8. Use fig.canvas.draw() and then "
     "np.asarray(fig.canvas.buffer_rgba()), an (height, width, 4) RGBA array; take [..., :3] for RGB. tostring_argb is still there in %s." % (DATE["3.10.0"], LATEST)),
    ("How do I fix \"'seaborn' is not a valid package style\"?",
     "matplotlib 3.6.0 renamed its seaborn styles to seaborn-v0_8-<name> and warned on the old names; 3.8.0 (%s) dropped the old names. "
     "Use plt.style.use('seaborn-v0_8-whitegrid') (or the matching name), or seaborn's own seaborn.set_theme()." % DATE["3.8.0"]),
    ("How do I fix \"'Legend' object has no attribute 'legendHandles'\"?",
     "matplotlib 3.9.0 removed legendHandles; it was deprecated in 3.7. Use legend.legend_handles (a list, same content)."),
    ("How do I fix \"'Axes' object has no attribute 'plot_date'\"?",
     "matplotlib 3.11.0 removed Axes.plot_date and pyplot.plot_date; they were deprecated in 3.9. Pass the dates to ax.plot directly "
     "(datetime or numpy datetime64 values are converted for you), with linestyle and marker as you want."),
]
n_cls = sum(1 for k in G[LATEST] if ":" in k)
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["matplotlib", "AttributeError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "matplotlib removed name lookup", "url": URL + "#lookup",
     "description": "Paste an AttributeError or style error from matplotlib and get, for each matplotlib release from %s to %s, whether the name exists, and what to use instead." % (VS[0], LATEST),
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "matplotlib names by release", "url": URL + "matplotlib_names.json", "dateModified": MOD,
     "description": "The public names of %d matplotlib modules and %d classes (Figure, Axes, FigureCanvasAgg, Legend, Axes3D, ...) and the style names in %d installed matplotlib releases (%s to %s), and the deprecation text before each removal." % (len(G[LATEST]) - n_cls, n_cls, len(VS), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "matplotlib_names.json"}]},
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
EX = [("AttributeError: module 'matplotlib.cm' has no attribute 'get_cmap'", "cm.get_cmap"),
      ("AttributeError: 'FigureCanvasAgg' object has no attribute 'tostring_rgb'", "tostring_rgb"),
      ("OSError: 'seaborn-whitegrid' is not a valid package style, path of style file, URL of style file, or library style name", "seaborn style"),
      ("AttributeError: 'Legend' object has no attribute 'legendHandles'", "legendHandles"),
      ("AttributeError: 'Axes' object has no attribute 'plot_date'", "plot_date")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
by_minor = {}
for v in VS:
    by_minor.setdefault(v.rsplit(".", 1)[0], []).append(v)
rel_list = "; ".join("%s (Python %s)" % (", ".join(vs), DIRS[vs[0]]["python"].rsplit(".", 1)[0]) for vs in by_minor.values())
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var LBL = {ok: "has it", warn: "has it, warns", gone: "not there"};
  var AX = "matplotlib.axes:Axes", CV = "matplotlib.backends.backend_agg:FigureCanvasAgg", CM = "matplotlib.colors:Colormap", A3 = "mpl_toolkits.mplot3d.axes3d:Axes3D";
  var CLS = {Figure: "matplotlib.figure:Figure", Axes: AX, AxesSubplot: AX, Axes3D: A3, Axes3DSubplot: A3, Legend: "matplotlib.legend:Legend",
             Colorbar: "matplotlib.colorbar:Colorbar", ColorbarBase: "matplotlib.colorbar:Colorbar", Text: "matplotlib.text:Text", Line2D: "matplotlib.lines:Line2D",
             Colormap: CM, ListedColormap: CM, LinearSegmentedColormap: CM, FuncAnimation: "matplotlib.animation:FuncAnimation"};
  function cls(n) { return CLS[n] || (/^FigureCanvas\w*$/.test(n) ? CV : null); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  var M = "((?:matplotlib|mpl_toolkits)(?:\\.\\w+)*)";
  function find(t) {
    var out = [], m;
    var re = new RegExp("cannot import name '(\\w+)' from '" + M + "'|module '" + M + "' has no attribute '(\\w+)'|'(\\w+)' object has no attribute '(\\w+)'|" +
      "'([\\w.-]+)' (?:is not a valid package style|not found in the style library)|style\\.(?:use|context)\\(\\s*['\"]([\\w.-]+)['\"]|" +
      "from " + M + " import ([\\w ,()]+)|No module named '" + M + "'|\\b" + M.slice(1, -1).replace("*", "+") + "(?![\\w.])", "g");
    while ((m = re.exec(t))) {
      if (m[1]) out.push([m[2], m[1]]);
      else if (m[3]) out.push([m[3], m[4]]);
      else if (m[5]) out.push([cls(m[5]), m[6]]);
      else if (m[7] || m[8]) out.push(["style", m[7] || m[8]]);
      else if (m[9]) m[10].replace(/[()]/g, " ").split(",").forEach(function (p) { var n = p.trim().split(/\s+as\s+/)[0]; if (n) out.push([m[9], n]); });
      else {
        var s = (m[11] || m[0]).split(".");
        if (s.length > 1) out.push([s.slice(0, -1).join("."), s[s.length - 1]]);
      }
    }
    return out;
  }
  function label(x) { return x.obj === "style" ? "plt.style.use('" + x.name + "')" : x.obj.replace(":", ".") + "." + x.name; }
  function show() {
    var h = "", seen = {}, all = Object.keys(D.rows).map(function (k) { return D.rows[k]; });
    find(q.value).forEach(function (t) {
      var rs = all.filter(function (x) { return x.name === t[1] && (!t[0] || x.obj === t[0]); });
      if (!rs.length) {
        if (seen["?" + t[1]]) return; seen["?" + t[1]] = 1;
        var where = Object.keys(D.names).filter(function (k) { return D.names[k].indexOf(t[1]) >= 0; });
        if (!t[0] && !where.length) return;
        var last = D.releases[D.releases.length - 1][0];
        h += "<h3><code>" + esc(t[0] === "style" ? "plt.style.use('" + t[1] + "')" : (t[0] ? t[0].replace(":", ".") + "." : "") + t[1]) + "</code></h3><p>" +
          (where.length ? "Not removed in any release read: " + esc(t[1]) + " is " + (t[0] === "style" ? "a style name" : "in " + where.map(function (k) { return esc(k.replace(":", ".")); }).join(", ")) + " in " + esc(last) + "." :
           t[0] === "style" ? "No matplotlib release from " + esc(D.releases[0][0]) + " to " + esc(last) + " ships a style with this name; plt.style.available lists the names, and a path to your own .mplstyle file works too." :
           t[0] && t[0].indexOf(":") > 0 ? "Not on the " + esc(t[0].split(":")[1]) + " class in any matplotlib release from " + esc(D.releases[0][0]) + " to " + esc(last) + ", and not one of the removed names this page checked on a real object; the name may be set by your own code, or be a typo." :
           "No matplotlib release from " + esc(D.releases[0][0]) + " to " + esc(last) + " has this name in the modules and classes this page covers.") + "</p>";
        return;
      }
      rs.forEach(function (x) {
        var k = x.obj + "." + x.name; if (seen[k]) return; seen[k] = 1;
        var lab = label(x), segs = [], prev = null;
        x.seq.split("").forEach(function (c, i) { var st = {o: "ok", w: "warn", g: "gone"}[c], v = D.releases[i][0]; if (st !== prev) { segs.push([v, st]); prev = st; } else segs[segs.length - 1][2] = v; });
        h += "<h3><code>" + esc(lab) + "</code>" + (x.module ? " (module)" : "") + "</h3><p><strong>Removed in matplotlib " + esc(x.removed) + "</strong> (last in " + esc(x.last) + ")";
        h += x.gaps.length ? "; also missing in " + esc(x.gaps.join(", ")) + ", then back." : ".";
        if (x.fix) h += " <strong>Instead:</strong> " + esc(x.fix) + ' <span class="note">(' + esc(x.src) + ")</span>";
        h += '</p><p>To keep it: <code>pip install "matplotlib&lt;' + esc(x.removed) + '"</code></p>';
        h += '<div class="tw"><table><thead><tr><th>matplotlib</th><th>' + esc(lab) + "</th></tr></thead><tbody>";
        segs.forEach(function (s) { h += "<tr><td>" + esc(s[0]) + (s[2] ? " to " + esc(s[2]) : "") + '</td><td class="s-' + s[1] + '">' + LBL[s[1]] + "</td></tr>"; });
        h += "</tbody></table></div>";
      });
    });
    if (!h) h = "<p>Paste the error line, for example module 'matplotlib.cm' has no attribute 'get_cmap'.</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.MPL_READY = true;
})();
"""
assert "</script" not in JS
r39 = [r for r in rest if r["removed"] == "3.9.0"]
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
<p class="lede"><strong>matplotlib 3.11.0 ({DATE["3.11.0"]}) removed <code>matplotlib.cm.get_cmap</code>: use <code>matplotlib.colormaps[name]</code> or <code>plt.get_cmap(name)</code> (3.9.0 had removed it too; 3.9.2 put it back). 3.10.0 removed <code>FigureCanvasAgg.tostring_rgb</code>: use <code>np.asarray(fig.canvas.buffer_rgba())</code>. 3.8.0 dropped the <code>'seaborn-*'</code> style names: use <code>'seaborn-v0_8-*'</code>. 3.9.0 removed <code>cm.register_cmap</code> and <code>Legend.legendHandles</code> (<code>legend_handles</code>).</strong> If the error comes from a library you did not write, upgrade the library or pin matplotlib below the release that removed the name. Paste the error below for the release-by-release answer.</p>
<p class="meta">Published {PUB} &middot; {len(VS)} matplotlib releases installed and run, {VS[0]} to {LATEST} ({n_runs:,} lookups) &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line</label>
<textarea id="q" spellcheck="false" placeholder="AttributeError: module 'matplotlib.cm' has no attribute 'get_cmap'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="matplotlib_names.json">matplotlib_names.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which release removed it, and what replaces it?</h2>
<p><strong>{len(rest)} names that one matplotlib release has and a later one does not</strong> ({len(r39)} of them in 3.9.0, {len(sty)} of them style names). "Instead" is matplotlib's own deprecation text from the last release that had the name ({n_fix} of {len(rest) - len(sty)} names), except where marked; for a style, the new name that works in {LATEST}.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Removed in</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>

<h2 id="how">How was this measured?</h2>
<p><strong>Each of {len(VS)} matplotlib releases (every release with a Linux x86-64 wheel from {VS[0]} to {LATEST}, patch releases included) was installed from PyPI in its own environment, the public names of {len(G[LATEST]) - n_cls} matplotlib modules and of {n_cls} classes were listed with <code>dir()</code>, and <code>getattr</code> was run for the union of all names in every release.</strong> A class member that is not on the class (set in <code>__init__</code>, as <code>Legend.legendHandles</code> was before 3.7) was checked with <code>hasattr</code> on a real object of that class, built on the Agg canvas. Every style name was tried with <code>plt.style.context(name)</code>. Releases: {rel_list}. 3.9.1 is yanked on PyPI and is not in the table; 3.1.0 and 3.1.1 have no wheel for the Pythons used here.</p>
<p>Most matplotlib modules have no <code>__all__</code>, so the table keeps class members, <code>__all__</code> names and the names matplotlib itself deprecated (a warning on access, or an <code>_api.deprecated</code> decorator or warning in the definition); helpers a module merely imported are left out, but the lookup still answers for them. The text is read from the installed source of the last release that had the name; <code>@_api.deprecated("3.8", alternative="buffer_rgba")</code> is turned into a sentence of the same content.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The matplotlib wheels on <a href="https://pypi.org/project/matplotlib/#history">PyPI</a>, installed and run, and their source as installed; the release dates are PyPI's.</li>
<li><a href="https://matplotlib.org/stable/api/api_changes.html">matplotlib's API changes for each release</a>.</li>
</ul>
<p>The same data as JSON: <a href="matplotlib_names.json">matplotlib_names.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a> &middot; <a href="/en/pillow-removed-name-lookup/">"module 'PIL.Image' has no attribute 'ANTIALIAS'"</a> &middot; <a href="/en/pandas-removed-attribute-lookup/">"'DataFrame' object has no attribute 'append'"</a>.</p>
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
(out_dir / "matplotlib_names.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | removals %d (3.9.0: %d, styles %d) | with text %d, notes/data %d | releases %d" % (len(page), len(rest), len(r39), len(sty), n_fix, n_data, len(VS)), file=sys.stderr)
