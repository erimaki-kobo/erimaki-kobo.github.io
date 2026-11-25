#!/usr/bin/env python3
"""Build en/llama-index-import-name-version-lookup/ (index.html; llama_index.json is copied next to it).

Usage: python3 -I build_page.py <dir with llama_index.json> out_dir PUBLISHED MODIFIED chk0.json chk1.json anchors.json mappings.json
ASCII only. The facts the prose names are asserted. style.css is shared with .github/llama-args; tool.js is the shared
lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["llama_index"].
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK0, CHK1, ANC, MAP = (json.load(open(a)) for a in sys.argv[5:9])   # MAP: llama-index-core command_line/mappings.json
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "llama_index.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/llama-index-import-name-version-lookup/"
TITLE = "cannot import name from 'llama_index': the version that has it"
H1 = "ImportError: cannot import name 'VectorStoreIndex' (or ServiceContext, OpenAI, any name) from 'llama_index...': which LlamaIndex releases have it"
DESC = ("LlamaIndex 0.10.0 moved the old top level to llama_index.core and split integrations into packages such as "
        "llama-index-llms-openai. Paste the error.")
assert len(TITLE) <= 66 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def pairs(ri):
    r = T[ri]
    return list(zip(r[::2], r[1::2]))


def span(m, n):
    a, b = pairs(D["names"][m][n])[-1]
    return R[a][0], (R[b][0] if b else None)


def mspan(m):
    a, b = pairs(D["mods"][m])[-1]
    return [(R[a][0], R[b][0] if b else None)]


def first(m, n):
    return R[pairs(D["names"][m][n])[0][0]][0]


def idx(v):
    return [k for k, r in enumerate(R) if r[0] == v][0]


date_of = lambda v: R[idx(v)][1]
last_before = lambda v: R[idx(v) - 1][2]

pkg = lambda mod: mod.replace(".", "-").replace("_", "-")   # the rule of llama-index-core command_line/upgrade.py
i10 = idx("0.10.0")
for m, n in [("", "VectorStoreIndex"), ("", "ServiceContext"), ("", "SimpleDirectoryReader"), ("", "StorageContext"), ("", "Document"),
             ("", "load_index_from_storage"), ("", "GPTVectorStoreIndex"), ("llms", "OpenAI"), ("embeddings", "OpenAIEmbedding"),
             ("vector_stores", "ChromaVectorStore"), ("node_parser", "SimpleNodeParser"), ("agent", "ReActAgent"), ("", "LLMPredictor")]:
    assert span(m, n)[1] == "0.10.0", (m, n, span(m, n))
for m, n, want in [("core", "VectorStoreIndex", ("0.10.0", None)), ("core", "ServiceContext", ("0.10.0", None)), ("core", "Settings", ("0.10.1", None)),
                   ("core.agent", "AgentRunner", ("0.10.0", "0.13.0")), ("core.agent", "FunctionCallingAgentWorker", ("0.10.24", "0.13.0")),
                   ("core.query_pipeline", "QueryPipeline", ("0.10.0", "0.13.0")), ("core.agent.workflow", "FunctionAgent", ("0.12.12", None)),
                   ("core.agent.workflow", "ReActAgent", ("0.13.0", None)) if "ReActAgent" in D["names"].get("core.agent.workflow", {}) and span("core.agent.workflow", "ReActAgent")[0] == "0.13.0" else ("core.agent.workflow", "AgentWorkflow", ("0.12.12", None)),
                   ("core", "download_loader", ("0.10.3", "0.14.21"))]:
    assert span(m, n) == want, (m, n, span(m, n))
assert mspan("core.llama_pack")[-1][1] == "0.14.21" and mspan("core.llama_dataset")[-1][1] == "0.14.21" and mspan("core.query_pipeline")[-1][1] == "0.13.0"
assert span("", "core") == ("0.9.0", None) and last_before("0.10.0") == "0.9.48"
assert all(a["wheel"] == a["expected"] == a["data"] for a in ANC) and len(ANC) == 14
assert MAP["OpenAI"] == "llama_index.llms.openai" and MAP["VectorStoreIndex"] == "llama_index.core" and MAP["ChromaVectorStore"] == "llama_index.vector_stores.chroma"
d10, d11, d13, d1421 = date_of("0.10.0"), date_of("0.11.0"), date_of("0.13.0"), date_of("0.14.21")

HINTS = {}
for m, names in D["names"].items():
    if m.startswith("core") or m.count(".") > 0:
        continue
    for n, ri in names.items():
        if pairs(ri)[-1][1] != i10 or n not in MAP:
            continue
        new = MAP[n]
        if new.startswith("llama_index.core"):
            HINTS["llama_index:%s:%s" % (m, n)] = "<code>from %s import %s</code> (llama-index-core, which <code>pip install llama-index</code> brings)." % (new, n)
        else:
            HINTS["llama_index:%s:%s" % (m, n)] = "<code>pip install %s</code>, then <code>from %s import %s</code>." % (pkg(new), new, n)
SC = ("<code>from llama_index.core import ServiceContext</code> still imports, but from 0.11.0 creating one raises "
      "\"ServiceContext is deprecated. Use llama_index.settings.Settings instead\". Set <code>Settings.llm</code>, "
      "<code>Settings.embed_model</code> and the like on <code>from llama_index.core import Settings</code> (from 0.10.1).")
HINTS["llama_index::ServiceContext"] = SC
HINTS["llama_index::set_global_service_context"] = "<code>llama_index.core.Settings</code> (from 0.10.1); the function stays in llama_index.core but its ServiceContext argument cannot be created from 0.11.0."
HINTS["llama_index::LLMPredictor"] = "pass the LLM itself: <code>Settings.llm = OpenAI(...)</code> (with <code>from llama_index.llms.openai import OpenAI</code>)."
HINTS["llama_index:core.agent:AgentRunner"] = "the workflow agents: <code>from llama_index.core.agent.workflow import FunctionAgent, ReActAgent, AgentWorkflow</code> (FunctionAgent and AgentWorkflow from 0.12.12)."
HINTS["llama_index:core.query_pipeline:QueryPipeline"] = "workflows: <code>from llama_index.core.workflow import Workflow, step</code> (from 0.11.0)."
for k in list(HINTS):
    l, m, n = k.split(":")
    assert pairs(D["names"][m][n])[-1][1], k
assert len(HINTS) > 500, len(HINTS)
COMMON = [("", "VectorStoreIndex"), ("", "SimpleDirectoryReader"), ("", "StorageContext"), ("", "load_index_from_storage"), ("", "Document"),
          ("", "PromptTemplate"), ("llms", "OpenAI"), ("embeddings", "OpenAIEmbedding"), ("embeddings", "HuggingFaceEmbedding"),
          ("vector_stores", "ChromaVectorStore"), ("llms", "Ollama"), ("node_parser", "SentenceSplitter"), ("agent", "ReActAgent")]
rows = []
for m, n in COMMON:
    assert n in D["names"][m] and pairs(D["names"][m][n])[-1][1] == i10 and n in MAP, (m, n)
    new = MAP[n]
    rows.append("<tr><td><code>from llama_index%s import %s</code></td><td><code>from %s import %s</code></td><td>%s</td></tr>" % (
        "." + m if m else "", n, new, n, "llama-index-core" if new.startswith("llama_index.core") else "<code>%s</code>" % pkg(new)))
common_rows = "\n".join(rows)
n_top = len(D["names"][""])
n_mods = len(D["mods"])
n_mods_gone = sum(1 for ri in D["mods"].values() if pairs(ri)[-1][1])
n_pairs = sum(len(v) for v in D["names"].values())
kb = (src / "llama_index.json").stat().st_size // 1024
n_map, n_ext = len(MAP), sum(1 for v in MAP.values() if not v.startswith("llama_index.core"))

FAQ = [
    ("How do I fix \"cannot import name 'VectorStoreIndex' from 'llama_index'\"?",
     "LlamaIndex 0.10.0 (%s) moved it: from llama_index.core import VectorStoreIndex. The same holds for SimpleDirectoryReader, "
     "StorageContext, Document, load_index_from_storage and the rest of the old top level; 0.9.48 is the last release with the old "
     "layout. To keep old code unchanged, pin pip install \"llama-index<0.10.0\"." % d10),
    ("How do I fix \"cannot import name 'OpenAI' from 'llama_index.llms'\"?",
     "From 0.10.0 each integration is its own package: pip install llama-index-llms-openai, then from llama_index.llms.openai "
     "import OpenAI. Embeddings and vector stores work the same way, for example llama-index-embeddings-openai and "
     "llama-index-vector-stores-chroma. The table on this page and the lookup give the package for %d names." % n_ext),
    ("ServiceContext imports but fails. What replaces it?",
     "From 0.11.0 (%s) creating a ServiceContext raises \"ServiceContext is deprecated. Use llama_index.settings.Settings instead\". "
     "Set Settings.llm, Settings.embed_model, Settings.chunk_size and so on, or pass the objects to the functions that use them. "
     "Settings is in llama_index.core from 0.10.1." % d11),
    ("Where did AgentRunner, FunctionCallingAgentWorker and QueryPipeline go?",
     "llama-index-core 0.13.0 (%s) removed the old agent classes and query pipelines. Agents are workflow-based: "
     "llama_index.core.agent.workflow has FunctionAgent, ReActAgent and AgentWorkflow; pipelines are written as workflows "
     "(llama_index.core.workflow, from 0.11.0)." % d13),
    ("Why does \"from llama_index.core import download_loader\" fail now?",
     "llama-index-core 0.14.21 (%s) removed download_loader together with llama_index.core.download, llama_dataset and llama_pack. "
     "Install the reader package instead, for example pip install llama-index-readers-file." % d1421),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["LlamaIndex", "ImportError", "llama-index-core"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "LlamaIndex import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the LlamaIndex releases in which that name can be imported from that module, the range to pin, and the new import and package.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from llama_index and llama_index.core, by release", "url": URL + "llama_index.json", "dateModified": MOD,
     "description": "For %d releases (llama-index %s to 0.9.48, llama-index-core 0.10.0 to %s): the names importable from every module as release ranges. Read from the PyPI wheels." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "llama_index.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.pin code{white-space:nowrap}.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\n#res td:first-child{min-width:9em}td code,p code,li code,h1{overflow-wrap:anywhere}main p,main li{overflow-wrap:break-word}\n"
js = (HERE.parent / "pta-imports" / "tool.js").read_text(encoding="ascii")
assert "</script" not in js and "window.LOOKUP_LIBS" in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'VectorStoreIndex' from 'llama_index' (unknown location)", "0.10.12", "VectorStoreIndex"),
      ("from llama_index.llms import OpenAI", "0.10.30", "llms.OpenAI"),
      ("from llama_index import ServiceContext, set_global_service_context", "", "ServiceContext"),
      ("from llama_index.core.agent import AgentRunner, FunctionCallingAgentWorker", "0.13.0", "AgentRunner"),
      ("ModuleNotFoundError: No module named 'llama_index.core.query_pipeline'", "", "query_pipeline")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/run-llama/llama_index/blob/"
a_rows = "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
    e("llama_index." + (a["module"] + "." if a["module"] else "") + a["name"]), a["release"], "has it" if a["expected"] else "does not") for a in ANC)
hint_kb = len(json.dumps(HINTS)) // 1024

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
<p class="lede"><strong>LlamaIndex 0.10.0 ({d10}) moved the whole old top level into <code>llama_index.core</code> and split every integration into its own package; 0.9.48 is the last release with the old layout.</strong> <code>from llama_index import VectorStoreIndex</code> becomes <code>from llama_index.core import VectorStoreIndex</code>. <code>from llama_index.llms import OpenAI</code> becomes <code>pip install llama-index-llms-openai</code> and <code>from llama_index.llms.openai import OpenAI</code>; embeddings, vector stores and readers work the same way. <code>ServiceContext</code> still imports but fails from 0.11.0: use <code>Settings</code>. llama-index-core 0.13.0 removed the old agents (<code>AgentRunner</code>) and <code>QueryPipeline</code>, and 0.14.21 removed <code>download_loader</code>. For any other name, paste the error below; the lookup gives the new import and the package for {len(HINTS)} old names.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; every release of llama-index {R[0][0]} to 0.9.48 and llama-index-core 0.10.0 to {LATEST} ({N} releases) &middot; read from the PyPI wheels, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'VectorStoreIndex' from 'llama_index' (unknown location)"></textarea>
<div class="grid">
<div><label for="v">Your version (optional; <code>pip show llama-index-core</code>, or <code>llama-index</code> before 0.10)</label><input id="v" inputmode="decimal" placeholder="for example 0.10.12"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="llama_index.json">llama_index.json</a> ({kb} KB) and {hint_kb} KB of hints in this page; nothing you paste is sent anywhere. Covers {"{:,}".format(n_pairs)} module-and-name pairs in {"{:,}".format(n_mods)} modules.</p>
</div>

<h2 id="v010">What replaces the old imports, and which package do I install?</h2>
<p><strong>The new import for each old name comes from LlamaIndex's own upgrade map (<code>llama_index/core/command_line/mappings.json</code>, {n_map:,} names, {n_ext} of them in integration packages); the package name follows the rule its <code>llamaindex-cli upgrade</code> uses.</strong> Common ones:</p>
<div class="tw"><table class="flt">
<thead><tr><th>Before 0.10.0</th><th>From 0.10.0</th><th>Package</th></tr></thead>
<tbody>
{common_rows}
</tbody></table></div>
<p><code>llamaindex-cli upgrade &lt;folder&gt;</code> (installed with llama-index-core) rewrites the imports of a project with the same map. <code>(unknown location)</code> in the error means <code>llama_index</code> is now a namespace package with nothing at its top level.</p>

<h2 id="later">What changed after 0.10?</h2>
<ul>
<li><strong>0.11.0 ({d11})</strong>: <code>ServiceContext</code> raises on use; <code>Settings</code> (from 0.10.1) replaces it. <code>llama_index.core.workflow</code> arrives.</li>
<li><strong>0.13.0 ({d13})</strong>: <code>llama_index.core.query_pipeline</code> and the old agent classes (<code>AgentRunner</code>, <code>ReActAgentWorker</code>, <code>FunctionCallingAgentWorker</code>, <code>StructuredPlannerAgent</code> and more) are gone; use <code>llama_index.core.agent.workflow</code> (<code>FunctionAgent</code> and <code>AgentWorkflow</code> from 0.12.12).</li>
<li><strong>0.14.21 ({d1421})</strong>: <code>download_loader</code>, <code>llama_index.core.download</code>, <code>llama_dataset</code> and <code>llama_pack</code> are gone; install the reader or pack package directly.</li>
</ul>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>Check both packages</strong>: <code>pip show llama-index llama-index-core</code>. From 0.10 the code is in llama-index-core; the llama-index package only pulls it in with a few integrations.</li>
<li><strong>A mixed install</strong> (an old llama-index 0.9 next to llama-index-core) makes imports fail in surprising ways. Uninstall both and install one side.</li>
<li><strong>An integration name</strong> (<code>llama_index.llms.openai</code>, <code>llama_index.vector_stores.chroma</code>) that fails with "No module named" means its package is not installed; the lookup names the package.</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the Python files of every release's wheel on PyPI (llama-index {R[0][0]} to 0.9.48, llama-index-core 0.10.0 to {LATEST}), read by HTTP range requests and parsed with Python's <code>ast</code> module.</strong> The git tags were not used for the data: the v0.10.0 tag exports <code>Settings</code>, the published 0.10.0 wheel does not. A module's names are everything it binds at module level and what <code>from .x import *</code> brings in; names that appear only in <code>__all__</code> without a binding (0.9.0 lists <code>BeautifulSoupWebReader</code>) are not importable and are not counted. Integration packages are not read; their imports come from the upgrade map.</p>
<p>Checks: (1) the top-level names of each part are found as plain text in its <code>__init__.py</code> in every release of their range ({"{:,}".format(CHK0["CHK_TOP_PAIRS"] + CHK1["CHK_TOP_PAIRS"])} name-and-release pairs) and are not bound on either side ({CHK0["CHK_TOP_EDGES"] + CHK1["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {"{:,}".format(CHK0["CHK_DEFS"] + CHK1["CHK_DEFS"])} definitions in {"{:,}".format(CHK0["CHK_DEF_FILES"] + CHK1["CHK_DEF_FILES"])} file versions; all are among the names read. (3) {len(ANC)} release checks against the wheels by plain-text search agree:</p>
<div class="tw"><table>
<thead><tr><th>Name</th><th>Release</th><th>Wheel and data</th></tr></thead>
<tbody>
{a_rows}
</tbody></table></div>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the Python files of the wheel.</li>
<li>llama-index before {R[0][0]} is not covered (0.6 and older had no pure-Python wheel of this layout).</li>
<li>Integration packages (llama-index-llms-*, -embeddings-*, -vector-stores-*, -readers-*) have their own versions and are not read; for them the page gives the import and the package from the upgrade map.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The wheels of <a href="https://pypi.org/project/llama-index/#history">llama-index</a> and <a href="https://pypi.org/project/llama-index-core/#history">llama-index-core</a> on PyPI (file names and sha256 in the build notes), which also give the release dates.</li>
<li>run-llama/llama_index: <a href="{GH}v{LATEST}/llama-index-core/llama_index/core/command_line/mappings.json">llama-index-core/llama_index/core/command_line/mappings.json</a> and <a href="{GH}v{LATEST}/llama-index-core/llama_index/core/command_line/upgrade.py">upgrade.py</a> at v{LATEST}; <a href="{GH}v0.11.0/llama-index-core/llama_index/core/service_context.py">service_context.py at v0.11.0</a> (the ServiceContext message).</li>
</ul>
<p>The same data as JSON: <a href="llama_index.json">llama_index.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/langchain-import-name-version-lookup/">"cannot import name ... from 'langchain'"</a> &middot; <a href="/en/openai-python-import-name-version-lookup/">"... from 'openai'"</a> &middot; <a href="/en/transformers-import-name-version-lookup/">"... from 'transformers'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["llama_index"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "llama_index.json", out_dir / "llama_index.json")
print("index.html %d bytes | hints %d | modules %d (gone %d) | pairs %d" % (len(page), len(HINTS), n_mods, n_mods_gone, n_pairs), file=sys.stderr)
