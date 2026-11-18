#!/usr/bin/env python3
"""Build en/datasets-import-name-version-lookup/ (index.html; datasets.json is copied next to it).

Usage: python3 -I build_page.py <dir with datasets.json> out_dir PUBLISHED MODIFIED chk.json
ASCII only. The facts the prose names are asserted. style.css is shared with .github/llama-args; tool.js is the shared
lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["datasets"].
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK = json.load(open(sys.argv[5]))
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "datasets.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/datasets-import-name-version-lookup/"
TITLE = "cannot import name from 'datasets': the version that has it"
H1 = "ImportError: cannot import name 'X' from 'datasets' (load_metric, list_datasets, ...): which releases have it"
DESC = ("datasets 3.0.0 removed load_metric (use evaluate.load), list_datasets, Metric and set_caching_enabled; 2.21.0 is the "
        "last with them. Paste the error.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def pairs(ri):
    r = T[ri]
    return list(zip(r[::2], r[1::2]))


def span(m, n):
    a, b = pairs(D["names"][m][n])[-1]
    return R[a][0], (R[b][0] if b else None)


def idx(v):
    return [k for k, r in enumerate(R) if r[0] == v][0]


date_of = lambda v: R[idx(v)][1]
last_before = lambda v: R[idx(v) - 1][2]

for n in ("load_metric", "list_metrics", "Metric", "list_datasets", "inspect_metric", "inspect_dataset"):
    assert span("", n)[1] == "3.0.0", n
assert span("", "set_caching_enabled") == ("1.3.0", "3.0.0") and span("", "disable_caching")[1] is None and span("", "enable_caching")[1] is None
assert span("", "load_dataset") == ("1.0.0", None) and span("", "List") == ("4.0.0", None)
assert last_before("3.0.0") == "2.21.0"
assert span("", "enable_caching")[0] == "2.0.0" and span("arrow_writer", "SchemaInferenceError") == ("2.7.0", None)
assert {"Optional", "dill"} <= {n for n, ri in D["names"][""].items() if pairs(ri)[-1][1] == idx("1.4.0")}
G30 = sorted(n for n, ri in D["names"][""].items() if pairs(ri)[-1][1] == idx("3.0.0"))
assert len(G30) == 30, len(G30)
TASKS = ["AudioClassification", "AutomaticSpeechRecognition", "ImageClassification", "LanguageModeling", "QuestionAnsweringExtractive",
         "Summarization", "TaskTemplate", "TextClassification"]
assert set(TASKS) <= set(G30)
d30, l21 = date_of("3.0.0"), last_before("3.0.0")

HINTS = {
    "datasets::load_metric": "<code>import evaluate; evaluate.load(...)</code>. datasets %s said: \"Use `evaluate.load` instead, from the new library Evaluate.\"" % l21,
    "datasets::list_metrics": "<code>evaluate.list_evaluation_modules()</code> (the datasets %s note)." % l21,
    "datasets::inspect_metric": "<code>evaluate.inspect_evaluation_module(...)</code> (the datasets %s note)." % l21,
    "datasets::Metric": "the Evaluate library (<code>evaluate.load</code> returns the metric object).",
    "datasets::list_datasets": "<code>from huggingface_hub import list_datasets</code>. datasets %s said: \"Use 'huggingface_hub.list_datasets' instead.\"" % l21,
    "datasets::set_caching_enabled": "<code>datasets.enable_caching()</code> or <code>datasets.disable_caching()</code> (from 2.0.0), as the datasets %s note says." % l21,
}
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(D["names"][m][n])[-1][1], k

REPL = {"load_metric": "evaluate.load", "list_metrics": "evaluate.list_evaluation_modules", "inspect_metric": "evaluate.inspect_evaluation_module",
        "Metric": "evaluate (the object evaluate.load returns)", "MetricInfo": "evaluate", "list_datasets": "huggingface_hub.list_datasets",
        "set_caching_enabled": "datasets.enable_caching / datasets.disable_caching"}
rows30 = []
for n in G30:
    kind = "task template" if n in TASKS else "module" if n[0].islower() and n not in REPL and "_" in n or n in ("metric", "readme", "tasks") else ""
    rows30.append("<tr><td><code>%s</code></td><td>%s</td></tr>" % (n, ("<code>%s</code>" % e(REPL[n])) if n in REPL else
                                                                    "none in datasets (task templates were dropped)" if n in TASKS else "none named"))

by = {}
for m in ("", "utils"):
    for n, ri in D["names"][m].items():
        b = pairs(ri)[-1][1]
        if b:
            by.setdefault((b, m), []).append(n)
gone_rows = []
for (b, m) in sorted(by, key=lambda k: (-k[0], k[1])):
    ns = sorted(by[(b, m)])
    gone_rows.append("<tr><td>%s</td><td>%s</td><td><code>%s</code></td><td>%d</td><td>%s</td></tr>" % (
        R[b][0], R[b][1], "datasets" + ("." + m if m else ""), len(ns), ", ".join("<code>%s</code>" % e(n) for n in ns)))
n_top = len(D["names"][""])
n_top_gone = sum(1 for ri in D["names"][""].values() if pairs(ri)[-1][1])
n_mods = len(D["mods"])
n_mods_gone = sum(1 for ri in D["mods"].values() if pairs(ri)[-1][1])
n_pairs = sum(len(v) for v in D["names"].values())
kb = (src / "datasets.json").stat().st_size // 1024

FAQ = [
    ("How do I fix \"cannot import name 'load_metric' from 'datasets'\"?",
     "datasets 3.0.0 (%s) removed load_metric; %s is the last release with it. Install the Evaluate library and use evaluate.load: "
     "pip install evaluate, then import evaluate; metric = evaluate.load(\"accuracy\"). To keep old code unchanged, pin pip install \"datasets<3.0.0\"." % (d30, l21)),
    ("What else did datasets 3.0.0 remove?",
     "%d top-level names: load_metric, list_metrics, inspect_metric, Metric and MetricInfo (moved to Evaluate), list_datasets (use "
     "huggingface_hub.list_datasets), set_caching_enabled (use enable_caching or disable_caching), inspect_dataset, the task templates "
     "such as TextClassification, and a few modules. The full list is on this page." % len(G30)),
    ("How do I fix \"cannot import name 'list_datasets' from 'datasets'\"?",
     "Use huggingface_hub.list_datasets, which datasets %s already pointed to. datasets 3.0.0 removed its own list_datasets." % l21),
    ("The error says \"cannot import name ... from 'datasets'\" and the path ends in a folder of my project. What is wrong?",
     "A file or folder named datasets in your project (or an old datasets.py) is imported instead of the library. The path in parentheses "
     "shows which one; rename yours. The same holds for \"unknown location\", which means a datasets folder without __init__.py."),
    ("Does this page cover names below the top level, like datasets.utils or datasets.arrow_writer?",
     "Yes: every module of datasets from %s to %s, %s module-and-name pairs in %d modules." % (R[0][0], LATEST, "{:,}".format(n_pairs), n_mods)),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["Hugging Face Datasets", "ImportError", "load_metric"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "datasets import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the datasets releases in which that name can be imported from that module, the range to pin, and where the name lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from datasets and its modules, by release", "url": URL + "datasets.json", "dateModified": MOD,
     "description": "For %d releases of datasets (%s to %s): the names importable from every module as release ranges and the life of each module. Read from the source of each release tag." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "datasets.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.pin code{white-space:nowrap}.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\n#res td:first-child{min-width:9em}td code{overflow-wrap:anywhere}\n"
js = (HERE.parent / "pta-imports" / "tool.js").read_text(encoding="ascii")
assert "</script" not in js and "window.LOOKUP_LIBS" in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'load_metric' from 'datasets' (/usr/local/lib/python3.10/site-packages/datasets/__init__.py)", "3.0.1", "load_metric"),
      ("from datasets import list_datasets, set_caching_enabled", "", "list_datasets"),
      ("from datasets.tasks import TextClassification", "", "task templates"),
      ("ImportError: cannot import name 'SchemaInferenceError' from 'datasets.arrow_writer'", "2.6.1", "SchemaInferenceError"),
      ("from datasets import List", "3.6.0", "List (4.0.0)")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/huggingface/datasets/blob/"

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
<p class="lede"><strong>Most of these errors come from datasets 3.0.0 ({d30}), which removed {len(G30)} top-level names; {l21} is the last release that has them.</strong> <code>load_metric</code>, <code>list_metrics</code> and <code>Metric</code> moved to the Evaluate library (<code>evaluate.load</code>). <code>list_datasets</code> is now <code>huggingface_hub.list_datasets</code>. <code>set_caching_enabled</code> is now <code>enable_caching</code> or <code>disable_caching</code>. The task templates, such as <code>TextClassification</code>, were dropped with no replacement in datasets. To run old code unchanged, pin <code>pip install "datasets&lt;3.0.0"</code>. For any other name, in any module of datasets, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; datasets {R[0][0]} to {LATEST}, the first release of each of {N} minor versions &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'load_metric' from 'datasets' (/usr/lib/python3/site-packages/datasets/__init__.py)"></textarea>
<div class="grid">
<div><label for="v">Your datasets version (optional; <code>pip show datasets</code>)</label><input id="v" inputmode="decimal" placeholder="for example 3.0.1"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="datasets.json">datasets.json</a> ({kb} KB); nothing you paste is sent anywhere. Covers {n_top} top-level names and {"{:,}".format(n_pairs)} module-and-name pairs in {n_mods} modules.</p>
</div>

<h2 id="v3">What did datasets 3.0.0 remove, and what replaces each name?</h2>
<p><strong>These {len(G30)} names left <code>from datasets import ...</code> in 3.0.0; each replacement is quoted from the deprecation notes in {l21}.</strong></p>
<div class="tw"><table class="flt">
<thead><tr><th>Removed in 3.0.0</th><th>Use instead</th></tr></thead>
<tbody>
{chr(10).join(rows30)}
</tbody></table></div>

<h2 id="removed">What did each datasets release remove from <code>datasets</code> and <code>datasets.utils</code>?</h2>
<p><strong>{n_top_gone} of the {n_top} names that <code>from datasets import</code> has ever accepted are gone from {LATEST}.</strong> Most of the rest left in 1.4.0 and 2.0.0, when the top level stopped passing along everything <code>datasets.utils</code> imported (names like <code>Optional</code> and <code>dill</code>). {n_mods_gone} of the {n_mods} modules that have existed are gone as well; paste <code>No module named 'datasets...'</code> into the lookup for any of them.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Release</th><th>Date (PyPI)</th><th>Module</th><th>Names</th><th>Removed names</th></tr></thead>
<tbody>
{chr(10).join(gone_rows)}
</tbody></table></div>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>The path in parentheses</strong> is the copy of datasets that was imported. If it points into your project (a folder or a file named <code>datasets</code>), that shadows the library: rename yours. <code>(unknown location)</code> means a <code>datasets</code> folder without <code>__init__.py</code> was found first.</li>
<li><strong>The module after "from"</strong> decides which table applies: <code>from 'datasets'</code> is the top level, <code>from 'datasets.arrow_writer'</code> is that module. When another library raises it (trl, for example, imports <code>SchemaInferenceError</code> from <code>datasets.arrow_writer</code>, which exists from 2.7.0), upgrade datasets, not that library.</li>
<li>In a notebook, restart the kernel after <code>pip install -U datasets</code>; the old copy stays loaded until then.</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong> datasets imports eagerly, so a module's names are everything it binds at module level: classes, functions, assignments, imports, and what <code>from .x import *</code> brings in. Code under <code>if TYPE_CHECKING:</code> is skipped. Dates come from PyPI.</p>
<p>Checks, by a second reading: (1) each of the {CHK["CHK_TOP"]} top-level names is found as plain text in <code>__init__.py</code> (or in the modules it star-imports) in every release of its range ({"{:,}".format(CHK["CHK_TOP_PAIRS"])} name-and-release pairs), and is not imported there in the release on either side ({CHK["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {"{:,}".format(CHK["CHK_DEFS"])} definitions in {"{:,}".format(CHK["CHK_DEF_FILES"])} file versions; all are among the names read. (3) {CHK["CHK_ANCHORS"]} known facts hold, among them the release named in the public reports under Sources.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the source.</li>
<li>Only the first release of each minor version was read (and the newest). A change in a patch release is attributed to the next minor.</li>
<li>A star import of a package carries along the submodules that package has loaded; the lookup counts all of its submodules, so for a few old releases it may list a submodule name at the top level that was not loaded yet.</li>
<li>Errors that are not about import names, such as dataset loading scripts no longer being run, are not covered.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>huggingface/datasets, release tags {R[0][0]} to {LATEST}: every <code>.py</code> file under <a href="{GH}{LATEST}/src/datasets/__init__.py">src/datasets</a>; release dates from <a href="https://pypi.org/project/datasets/#history">PyPI</a>.</li>
<li>Notes quoted: <a href="{GH}{l21}/src/datasets/load.py">load.py at {l21}</a> (load_metric), <a href="{GH}{l21}/src/datasets/inspect.py">inspect.py at {l21}</a> (list_datasets, list_metrics, inspect_metric), <a href="{GH}{l21}/src/datasets/fingerprint.py">fingerprint.py at {l21}</a> (set_caching_enabled).</li>
<li>Reports: <a href="https://discuss.huggingface.co/t/cant-import-load-metric-from-datasets/107524">Can't import load_metric from datasets</a>, <a href="https://discuss.huggingface.co/t/trl-importation-error-on-kaggle/66817">SchemaInferenceError from datasets.arrow_writer, raised by trl</a>.</li>
</ul>
<p>The same data as JSON: <a href="datasets.json">datasets.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/transformers-import-name-version-lookup/">"cannot import name ... from 'transformers'"</a> &middot; <a href="/en/huggingface-hub-import-name-version-lookup/">"... from 'huggingface_hub'"</a> &middot; <a href="/en/peft-trl-accelerate-import-name-lookup/">"... from 'peft', 'trl' or 'accelerate'"</a> &middot; <a href="/en/diffusers-import-name-version-lookup/">"... from 'diffusers'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["datasets"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "datasets.json", out_dir / "datasets.json")
print("index.html %d bytes | 3.0.0 removed %d | top %d (gone %d) | modules %d (gone %d) | pairs %d | rows %d" % (
    len(page), len(G30), n_top, n_top_gone, n_mods, n_mods_gone, n_pairs, len(gone_rows)), file=sys.stderr)
