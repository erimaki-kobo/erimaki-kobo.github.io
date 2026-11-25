#!/usr/bin/env python3
"""Build en/networkx-removed-name-lookup/ (index.html and networkx_names.json).

Usage: python3 -I build_page.py probes/ notes.json pypi.json out_dir PUBLISHED MODIFIED
probes/: dir_<v>.json (public names, __all__, submodules), get_<v>.json (getattr, or import for a submodule, of the union in each
release), inst_<v>.json (hasattr on a small graph of each class),
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
MSG = {f[4:-5]: json.load(open(os.path.join(PD, f))) for f in os.listdir(PD) if f.startswith("msg_") and f.endswith(".json")}
DATE = {v: min(f["upload_time"] for f in P["releases"][v])[:10] for v in (VS + DATES_EXTRA)}
LATEST = VS[-1]
LAB = lambda k: k.replace(":", ".")
NOISE = set(__future__.all_feature_names) | set(typing.__all__) | set(sys.stdlib_module_names) | {"numpy", "np", "nx", "networkx", "absolute_import", "division", "print_function", "not_implemented_for", "decorator"}


def clean(msg, n):
    msg = msg.replace("%s", n).replace("``", "")
    if "{}" in msg:
        msg = msg.replace("{}", n, 1)
    return " ".join(s for s in re.split(r"(?<=\.)\s+", msg) if "{}" not in s and "{...}" not in s).strip()


ALLN = {v: set().union(*DIRS[v]["all"].values()) | set().union(*DIRS[v]["submodules"].values()) for v in VS}
KEEP = {tuple(x) for x in PRE["keep"]}
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
        is_mod = bool(G[last][k][n].get("module")) or n in DIRS[last]["submodules"].get(k, [])
        has_text = bool(G[last][k][n]["warn"]) or n in MSG.get(last, {}).get(k, {}) or (k, n) in KEEP or "%s|%s" % (k, n) in PRE["notes"]
        in_all = n in ALLN[last]   # networkx re-exports each module's __all__ at the top
        mirror = False
        if n in NOISE or not (":" in k or has_text or in_all or mirror):
            continue   # keep class members, __all__ names (of any module, networkx re-exports them), and names networkx deprecated
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
for (k, n), x in ((tuple(k.split("|")), x) for k, x in PRE["notes"].items()):
    r = ROWS.get("%s.%s" % (k, n))
    if r and not r["fix"]:
        r["fix"], r["src"] = x, "our note"
    elif r and not re.search(r"\b(use|instead|replaced|renamed)\b|-->", r["fix"], re.I):
        r["fix"], r["src"] = r["fix"] + " Instead (our note): " + x, r["src"] + ", and our note"
R = lambda k, n: ROWS["%s.%s" % (k, n)]
rest = list(ROWS.values())
mods = [r for r in rest if r["module"]]
names_ = [r for r in rest if not r["module"]]
# facts the prose names
for k, n, v in [("networkx", "from_numpy_matrix", "3.0"), ("networkx", "to_numpy_matrix", "3.0"), ("networkx", "read_gpickle", "3.0"), ("networkx", "write_gpickle", "3.0"),
                ("networkx", "info", "3.0"), ("networkx", "from_scipy_sparse_matrix", "3.0"), ("networkx", "to_scipy_sparse_matrix", "3.0"), ("networkx", "OrderedGraph", "3.0"),
                ("networkx", "connected_component_subgraphs", "2.4"), ("networkx:Graph", "node", "2.4"), ("networkx:Graph", "add_path", "2.4"), ("networkx:Graph", "selfloop_edges", "2.4"),
                ("networkx:Graph", "nodes_iter", "2.0"), ("networkx:Graph", "edges_iter", "2.0"), ("networkx:Graph", "edge", "2.0"), ("networkx", "from_pandas_dataframe", "2.1"),
                ("networkx", "gpickle", "3.0"), ("networkx", "d_separated", "3.5")]:
    assert R(k, n)["removed"] == v, (k, n, R(k, n)["removed"])
for k, n, want in [("networkx", "from_numpy_matrix", "from_numpy_array"), ("networkx", "to_numpy_matrix", "to_numpy_array"), ("networkx", "read_gpickle", "pickle.load"),
                   ("networkx", "from_scipy_sparse_matrix", "from_scipy_sparse_array"), ("networkx", "connected_component_subgraphs", "G.subgraph(c).copy() for c in connected_components(G)"),
                   ("networkx:Graph", "node", "G.nodes"), ("networkx:Graph", "add_path", "nx.add_path"), ("networkx:Graph", "selfloop_edges", "nx.selfloop_edges"),
                   ("networkx", "from_pandas_dataframe", "from_pandas_edgelist"), ("networkx", "info", "print(G)"), ("networkx", "OrderedGraph", "Use `Graph` instead"),
                   ("networkx:Graph", "edge", "G.adj"), ("networkx:Graph", "nodes_iter", "G.nodes()")]:
    assert want in (R(k, n)["fix"] or ""), (k, n, R(k, n)["fix"])
assert R("networkx:Graph", "node")["seq"][0][1] == "ok" and R("networkx:Graph", "edge")["seq"][0][1] == "ok"   # on the object in 1.11
for n in ("from_numpy_array", "to_numpy_array", "from_scipy_sparse_array", "to_scipy_sparse_array", "selfloop_edges", "add_path", "from_pandas_edgelist", "edge_betweenness_centrality", "betweenness_centrality_subset"):
    assert G[LATEST]["networkx"][n]["ok"], n
rest = list(ROWS.values())
n_fix = sum(1 for r in rest if r["fix"] and r["src"] not in ("this page's data", "our note"))
n_data = sum(1 for r in rest if r["src"] in ("this page's data", "our note"))
n_runs = sum(len(x) for k, x in G[VS[0]].items()) * len(VS)
CODE = {"ok": "o", "warn": "w", "gone": "g"}
ROWS_OUT = {kk: dict(r, seq="".join(CODE[s[1]] for s in r["seq"])) for kk, r in ROWS.items()}
DATA = {"releases": [[v, DATE[v], DIRS[v]["python"]] for v in VS], "rows": ROWS_OUT,
        "names": {k: sorted(set().union(*(DIRS[v]["dir"].get(k, []) for v in VS))) for k in G[VS[-1]]}}
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json
URL = "https://erimaki-kobo.github.io/en/networkx-removed-name-lookup/"
TITLE = "module 'networkx' has no attribute 'from_numpy_matrix' (and G.node): fix"
H1 = "AttributeError: module 'networkx' has no attribute 'from_numpy_matrix' (or 'read_gpickle', 'Graph' object has no attribute 'node', 'nodes_iter', any name): which networkx removed it and what to use"
DESC = ("networkx 3.0 removed from_numpy_matrix (use from_numpy_array), read_gpickle (use pickle) and nx.info; 2.4 removed G.node (use G.nodes). %d releases installed and run."
        % len(VS))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))
r30 = [r for r in rest if r["removed"] == "3.0"]
tab = []
for r in sorted(rest, key=lambda x: (key(x["removed"]), x["obj"], x["name"].lower())):
    lab = ("G." + r["name"] + " (" + r["obj"].split(":")[1] + ")") if ":" in r["obj"] else "%s.%s" % (r["obj"], r["name"])
    tab.append("<tr><td><code>%s</code></td><td>%s%s</td><td>%s%s</td></tr>" % (e(lab), r["removed"], " (also missing in %s)" % ", ".join(r["gaps"]) if r["gaps"] else "",
                                                                        e(r["fix"] or ""), " <em>(our note)</em>" if r["src"] == "our note" else ""))
tab_html = "\n".join(tab)
FAQ = [
    ("How do I fix \"module 'networkx' has no attribute 'from_numpy_matrix'\"?",
     "networkx 3.0 (%s) removed from_numpy_matrix and to_numpy_matrix; 2.6 to 2.8 warn when they are called. Use nx.from_numpy_array(A) and nx.to_numpy_array(G), which take "
     "the same arguments; wrap with np.asmatrix(...) if you really need a matrix. The same release removed from_scipy_sparse_matrix and "
     "to_scipy_sparse_matrix: use from_scipy_sparse_array and to_scipy_sparse_array." % DATE["3.0"]),
    ("How do I fix \"module 'networkx' has no attribute 'read_gpickle'\"?",
     "networkx 3.0 removed read_gpickle, write_gpickle and the networkx.readwrite.gpickle module. Use pickle directly: "
     "with open('g.gpickle', 'wb') as f: pickle.dump(G, f, pickle.HIGHEST_PROTOCOL); and with open('g.gpickle', 'rb') as f: G = pickle.load(f). "
     "A file written by write_gpickle in 2.8.8 loads this way in 3.7 (tried)."),
    ("How do I fix \"'Graph' object has no attribute 'node'\"?",
     "networkx 2.4 (%s) removed G.node; 2.0 to 2.3 kept it as a pointer to G.nodes. Use G.nodes[n] for a node's attribute dict, "
     "G.nodes(data=True) for (node, data) pairs, and for n in G: to loop. The same release removed G.add_path, G.add_cycle, G.add_star and "
     "G.selfloop_edges (use nx.add_path(G, ...), nx.selfloop_edges(G))." % DATE["2.4"]),
    ("How do I fix \"module 'networkx' has no attribute 'connected_component_subgraphs'\"?",
     "networkx 2.4 removed connected_component_subgraphs (and the strongly, weakly and biconnected versions); 2.1 to 2.3 warned. "
     "Use (G.subgraph(c).copy() for c in nx.connected_components(G)), or max(nx.connected_components(G), key=len) for the largest component's nodes."),
    ("How do I fix \"'Graph' object has no attribute 'nodes_iter'\" (or edges_iter, degree_iter)?",
     "networkx 2.0 (%s) removed every *_iter method. Call the method without _iter: G.nodes(), G.edges(), G.degree(), G.neighbors(n); "
     "they return views or iterators. G.edge also went in 2.0: use G.adj (G.adj[u][v] is the edge data dict)." % DATE["2.0"]),
    ("How do I fix \"module 'networkx' has no attribute 'info'\"?",
     "networkx 3.0 removed nx.info. print(G) gives the same one-line summary ('Graph with 3 nodes and 2 edges'); "
     "use G.number_of_nodes() and G.number_of_edges() for the numbers."),
]
n_cls = sum(1 for k in G[LATEST] if ":" in k)
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["NetworkX", "AttributeError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "networkx removed name lookup", "url": URL + "#lookup",
     "description": "Paste an AttributeError or ImportError from networkx and get, for each networkx release from %s to %s, whether the name exists, and what to use instead." % (VS[0], LATEST),
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "networkx names by release", "url": URL + "networkx_names.json", "dateModified": MOD,
     "description": "The public names of %d networkx modules and of Graph, DiGraph, MultiGraph and MultiDiGraph in %d installed networkx releases (%s to %s), and the deprecation text before each removal." % (len(G[LATEST]) - n_cls, len(VS), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "networkx_names.json"}]},
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
EX = [("AttributeError: module 'networkx' has no attribute 'from_numpy_matrix'", "from_numpy_matrix"),
      ("AttributeError: module 'networkx' has no attribute 'read_gpickle'", "read_gpickle"),
      ("AttributeError: 'Graph' object has no attribute 'node'", "G.node"),
      ("AttributeError: module 'networkx' has no attribute 'connected_component_subgraphs'", "connected_component_subgraphs"),
      ("AttributeError: 'DiGraph' object has no attribute 'nodes_iter'", "nodes_iter")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
by_py = {}
for v in VS:
    by_py.setdefault(DIRS[v]["python"].rsplit(".", 1)[0], []).append(v)
rel_list = "; ".join("%s (Python %s)" % (", ".join(vs), py) for py, vs in by_py.items())
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var LBL = {ok: "has it", warn: "has it, warns", gone: "not there"};
  var CLS = {Graph: "networkx:Graph", DiGraph: "networkx:DiGraph", MultiGraph: "networkx:MultiGraph", MultiDiGraph: "networkx:MultiDiGraph",
             OrderedGraph: "networkx:Graph", OrderedDiGraph: "networkx:DiGraph"};
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  var M = "(networkx(?:\\.\\w+)*)";
  function find(t) {
    var out = [], m;
    var re = new RegExp("cannot import name '(\\w+)' from '" + M + "'|module '" + M + "' has no attribute '(\\w+)'|'(\\w+)' object has no attribute '(\\w+)'|" +
      "from " + M + " import ([\\w ,()]+)|No module named '" + M + "'|\\b(?:nx|networkx)\\.(\\w+)(?:\\.(\\w+))?", "g");
    while ((m = re.exec(t))) {
      if (m[1]) out.push([m[2], m[1]]);
      else if (m[3]) out.push([m[3], m[4]]);
      else if (m[5]) { if (CLS[m[5]]) out.push([CLS[m[5]], m[6]]); }
      else if (m[7]) m[8].replace(/[()]/g, " ").split(",").forEach(function (p) { var n = p.trim().split(/\s+as\s+/)[0]; if (n) out.push([m[7], n]); });
      else if (m[9]) { var s = m[9].split("."); if (s.length > 1) out.push([s.slice(0, -1).join("."), s[s.length - 1]]); }
      else if (m[10]) { if (m[11] && D.names["networkx." + m[10]]) out.push(["networkx." + m[10], m[11]]); else out.push(["networkx", m[10]]); }
    }
    return out;
  }
  function label(x) { return x.obj.indexOf(":") > 0 ? "G." + x.name + " (" + x.obj.split(":")[1] + ")" : x.obj + "." + x.name; }
  function show() {
    var h = "", seen = {}, all = Object.keys(D.rows).map(function (k) { return D.rows[k]; });
    find(q.value).forEach(function (t) {
      var rs = all.filter(function (x) { return x.name === t[1] && (!t[0] || x.obj === t[0]); });
      if (!rs.length && t[0] === "networkx") rs = all.filter(function (x) { return x.name === t[1] && x.obj.indexOf(":") < 0; }).slice(0, 1);
      if (!rs.length) {
        if (seen["?" + t[1]]) return; seen["?" + t[1]] = 1;
        var where = Object.keys(D.names).filter(function (k) { return D.names[k].indexOf(t[1]) >= 0; });
        if (!where.length && t[0] && D.names[t[0]] === undefined && !/^networkx/.test(t[0])) return;
        var last = D.releases[D.releases.length - 1][0];
        h += "<h3><code>" + esc((t[0] ? t[0].replace(":", ".") + "." : "") + t[1]) + "</code></h3><p>" +
          (where.length ? "Not removed in any release read: " + esc(t[1]) + " is in " + where.map(function (k) { return esc(k.replace(":", ".")); }).join(", ") + " in " + esc(last) + "." :
           t[0] && t[0].indexOf(":") > 0 ? "Not on a " + esc(t[0].split(":")[1]) + " in any networkx release from " + esc(D.releases[0][0]) + " to " + esc(last) + " (class attributes and a small graph's attributes were checked); the name may be set by your own code, or be a typo." :
           "No networkx release from " + esc(D.releases[0][0]) + " to " + esc(last) + " has this name in the modules this page covers.") + "</p>";
        return;
      }
      rs.forEach(function (x) {
        var k = x.obj + "." + x.name; if (seen[k]) return; seen[k] = 1;
        var lab = label(x), segs = [], prev = null;
        x.seq.split("").forEach(function (c, i) { var st = {o: "ok", w: "warn", g: "gone"}[c], v = D.releases[i][0]; if (st !== prev) { segs.push([v, st]); prev = st; } else segs[segs.length - 1][2] = v; });
        h += "<h3><code>" + esc(lab) + "</code>" + (x.module ? " (module)" : "") + "</h3><p><strong>Removed in networkx " + esc(x.removed) + "</strong> (last in " + esc(x.last) + ")";
        h += x.gaps.length ? "; also missing in " + esc(x.gaps.join(", ")) + ", then back." : ".";
        if (x.fix) h += " <strong>Instead:</strong> " + esc(x.fix) + ' <span class="note">(' + esc(x.src) + ")</span>";
        h += '</p><p>To keep it: <code>pip install "networkx&lt;' + esc(x.removed) + '"</code></p>';
        h += '<div class="tw"><table><thead><tr><th>networkx</th><th>' + esc(lab) + "</th></tr></thead><tbody>";
        segs.forEach(function (s) { h += "<tr><td>" + esc(s[0]) + (s[2] ? " to " + esc(s[2]) : "") + '</td><td class="s-' + s[1] + '">' + LBL[s[1]] + "</td></tr>"; });
        h += "</tbody></table></div>";
      });
    });
    if (!h) h = "<p>Paste the error line, for example module 'networkx' has no attribute 'from_numpy_matrix'.</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.NX_READY = true;
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
<p class="lede"><strong>networkx 3.0 ({DATE["3.0"]}) removed <code>from_numpy_matrix</code> and <code>to_numpy_matrix</code> (use <code>from_numpy_array</code>, <code>to_numpy_array</code>), <code>read_gpickle</code> and <code>write_gpickle</code> (use <code>pickle</code>), <code>from_scipy_sparse_matrix</code> (<code>from_scipy_sparse_array</code>) and <code>nx.info</code> (<code>print(G)</code>). 2.4 ({DATE["2.4"]}) removed <code>G.node</code> (use <code>G.nodes</code>) and <code>connected_component_subgraphs</code>. 2.0 removed <code>nodes_iter</code>, <code>edges_iter</code> and <code>G.edge</code>.</strong> If the error comes from a library you did not write, upgrade the library or pin networkx below the release that removed the name. Paste the error below for the release-by-release answer.</p>
<p class="meta">Published {PUB} &middot; {len(VS)} networkx releases installed and run, {VS[0]} to {LATEST} ({n_runs:,} lookups) &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line</label>
<textarea id="q" spellcheck="false" placeholder="AttributeError: module 'networkx' has no attribute 'from_numpy_matrix'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="networkx_names.json">networkx_names.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which release removed it, and what replaces it?</h2>
<p><strong>{len(rest)} names that one networkx release has and a later one does not</strong> ({len(r30)} of them in 3.0). "Instead" is networkx's own deprecation text from the last release that had the name ({n_fix} of {len(rest)}), except where marked "our note" (from networkx's migration guides and release notes, for names removed without a warning, as most of the 1.x API was in 2.0).</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>Removed in</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>

<h2 id="how">How was this measured?</h2>
<p><strong>Each of {len(VS)} networkx releases (every release from {VS[0]} to {LATEST}, patch releases included) was installed from PyPI in its own environment, the public names of {len(G[LATEST]) - n_cls} networkx modules and of the Graph, DiGraph, MultiGraph and MultiDiGraph classes were listed with <code>dir()</code>, and <code>getattr</code> was run for the union of all names in every release.</strong> A small graph of each class was also built and checked with <code>hasattr</code>, because networkx 1.x set <code>G.node</code> and <code>G.edge</code> on the object, not the class. Releases: {rel_list}. 1.11 and 2.0 to 2.5.1 were installed with decorator 4.4.2, and 1.11 to 2.2 with setuptools below 70 (they import pkg_resources).</p>
<p>The table keeps class members, names in any module's <code>__all__</code> (networkx re-exports them at the top) and names networkx itself deprecated; helpers a module merely imported are left out, but the lookup still answers for them. The text is read from the installed source of the last release that had the name: the <code>warnings.warn(..., DeprecationWarning)</code> in its body, with a local <code>msg = ...</code> resolved.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The networkx packages on <a href="https://pypi.org/project/networkx/#history">PyPI</a>, installed and run, and their source as installed; the release dates are PyPI's.</li>
<li>networkx's <a href="https://networkx.org/documentation/stable/release/migration_guide_from_1.x_to_2.0.html">migration guide from 1.x to 2.0</a>, <a href="https://networkx.org/documentation/stable/release/migration_guide_from_2.x_to_3.0.html">from 2.x to 3.0</a> and <a href="https://networkx.org/documentation/stable/release/index.html">release notes</a> (for the notes).</li>
</ul>
<p>The same data as JSON: <a href="networkx_names.json">networkx_names.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a> &middot; <a href="/en/scipy-removed-name-lookup/">"cannot import name 'triu' from 'scipy.linalg'"</a> &middot; <a href="/en/matplotlib-removed-name-lookup/">"module 'matplotlib.cm' has no attribute 'get_cmap'"</a>.</p>
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
(out_dir / "networkx_names.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | removals %d (3.0: %d) | with text %d, notes/data %d | releases %d" % (len(page), len(rest), len(r30), n_fix, n_data, len(VS)), file=sys.stderr)
