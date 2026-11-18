#!/usr/bin/env python3
"""Build en/langchain-import-name-version-lookup/ (index.html; langchain.json, langchain_classic.json, langchain_core.json).

Usage: python3 -I build_page.py <dir with the three json files> out_dir PUBLISHED MODIFIED chk_langchain.json chk_langchain_classic.json chk_langchain_core.json CHK_GETATTR
ASCII only; the facts the prose names are asserted. tool.js is the shared lookup of .github/pta-imports.
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
LIBS = ["langchain", "langchain_classic", "langchain_core"]
CHK = {l: json.load(open(f)) for l, f in zip(LIBS, sys.argv[5:8])}
N_GETATTR = int(sys.argv[8])
HERE = Path(__file__).resolve().parent
D = {l: json.load(open(src / (l + ".json"))) for l in LIBS}
e = html.escape
URL = "https://erimaki-kobo.github.io/en/langchain-import-name-version-lookup/"
TITLE = "cannot import name from langchain: where it moved in 1.0"
H1 = "ImportError: cannot import name 'X' from 'langchain.chains', 'langchain.schema', 'langchain.chat_models' ...: which version has it, and where it is now"
DESC = ("LangChain 1.0 removed langchain.chains, .schema, .memory, .llms and 35 more modules; they live on in langchain-classic. "
        "Paste the error: get the new import.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def pairs(l, ri):
    r = D[l]["ranges"][ri]
    return list(zip(r[::2], r[1::2]))


def rel(l, i):
    return D[l]["releases"][i]


def idx(l, v):
    return [k for k, r in enumerate(D[l]["releases"]) if r[0] == v][0]


def span(l, m, n):
    a, b = pairs(l, D[l]["names"][m][n])[-1]
    return rel(l, a)[0], (rel(l, b)[0] if b else None)


def mspan(l, m):
    a, b = pairs(l, D[l]["mods"][m])[-1]
    return rel(l, a)[0], (rel(l, b)[0] if b else None)


L, C, K = D["langchain"], D["langchain_classic"], D["langchain_core"]
i10 = idx("langchain", "1.0.0")
d10 = rel("langchain", i10)[1]
last03 = rel("langchain", i10 - 1)[2]
GONE10 = sorted(m for m, ri in L["mods"].items() if "." not in m and pairs("langchain", ri)[-1][1] == i10)
assert len(GONE10) == 39 and {"chains", "schema", "memory", "llms", "agents"} - {"agents"} <= set(GONE10), GONE10
in_classic = [m for m in GONE10 if m in C["mods"]]
assert len(in_classic) == 38 and "pydantic_v1" not in in_classic
assert span("langchain", "chains", "LLMChain") == ("0.1.0", "1.0.0") and span("langchain_classic", "chains", "LLMChain")[1] is None
assert span("langchain", "agents", "create_agent") == ("1.0.0", None) and span("langchain", "agents", "AgentExecutor")[1] == "1.0.0"
assert span("langchain", "messages", "HumanMessage") == ("1.0.0", None) and span("langchain_core", "messages", "HumanMessage")[1] is None
assert L["via"]["chat_models"]["ChatOpenAI"] == "langchain_community.chat_models"
assert mspan("langchain_core", "memory")[1] == "1.0.0" and mspan("langchain_core", "pydantic_v1")[1] == "1.0.0"
assert rel("langchain_classic", 0)[0] == "1.0.0" and rel("langchain_core", 0)[0] == "0.1.47"
n_fwd = sum(len(v) for v in L["via"].values())
n_fwd_names = len({n for v in L["via"].values() for n in v})
CHAT = {"ChatOpenAI": "langchain_openai", "AzureChatOpenAI": "langchain_openai", "OpenAIEmbeddings": "langchain_openai",
        "AzureOpenAIEmbeddings": "langchain_openai", "OpenAI": "langchain_openai", "AzureOpenAI": "langchain_openai",
        "ChatAnthropic": "langchain_anthropic", "ChatOllama": "langchain_ollama", "OllamaEmbeddings": "langchain_ollama",
        "HuggingFaceEmbeddings": "langchain_huggingface", "ChatHuggingFace": "langchain_huggingface"}
HINTS = {}
for m, ns in L["via"].items():
    for n in ns:
        if n in CHAT:
            HINTS["langchain:%s:%s" % (m, n)] = "<code>from %s import %s</code> (pip install %s), the provider's own package." % (CHAT[n], n, CHAT[n].replace("_", "-"))
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(l, D[l]["names"][m][n])[-1][1], k

KEY = [("chains", "LLMChain"), ("chains", "RetrievalQA"), ("chains", "ConversationalRetrievalChain"), ("memory", "ConversationBufferMemory"),
       ("agents", "AgentExecutor"), ("agents", "initialize_agent"), ("text_splitter", "RecursiveCharacterTextSplitter"),
       ("schema", "HumanMessage"), ("schema", "Document"), ("prompts", "PromptTemplate"), ("chat_models", "ChatOpenAI"),
       ("vectorstores", "FAISS"), ("document_loaders", "PyPDFLoader"), ("embeddings", "OpenAIEmbeddings")]
NOW = {("schema", "HumanMessage"): "<code>from langchain_core.messages import HumanMessage</code>, or <code>from langchain.messages import HumanMessage</code> (1.0.0 on)",
       ("schema", "Document"): "<code>from langchain_core.documents import Document</code>",
       ("prompts", "PromptTemplate"): "<code>from langchain_core.prompts import PromptTemplate</code>",
       ("text_splitter", "RecursiveCharacterTextSplitter"): "<code>from langchain_text_splitters import RecursiveCharacterTextSplitter</code> (pip install langchain-text-splitters)",
       ("agents", "AgentExecutor"): "<code>from langchain_classic.agents import AgentExecutor</code>; new code: <code>langchain.agents.create_agent</code>",
       ("agents", "initialize_agent"): "<code>from langchain_classic.agents import initialize_agent</code>; new code: <code>langchain.agents.create_agent</code>"}
assert span("langchain_core", "documents", "Document")[1] is None and span("langchain_core", "prompts", "PromptTemplate")[1] is None
assert span("langchain", "text_splitter", "RecursiveCharacterTextSplitter")[1] == "1.0.0"
key_rows = []
for m, n in KEY:
    a, b = span("langchain", m, n)
    assert b == "1.0.0", (m, n, b)
    via = L.get("via", {}).get(m, {}).get(n)
    if (m, n) in NOW:
        now = NOW[(m, n)]
    elif n in CHAT:
        now = "<code>from %s import %s</code>" % (CHAT[n], n)
    elif via:
        now = "<code>from %s import %s</code> (pip install langchain-community)" % (via, n)
    else:
        assert span("langchain_classic", m, n)[1] is None, (m, n)
        now = "<code>from langchain_classic.%s import %s</code> (pip install langchain-classic)" % (m, n)
    key_rows.append("<tr><td><code>from langchain.%s import %s</code></td><td>%s</td><td>%s</td></tr>" % (
        m, n, ("forwarded to <code>%s</code>" % via) if via else "defined in langchain", now))

mod_rows = "\n".join("<tr><td><code>langchain.%s</code></td><td>%s</td></tr>" % (
    m, "<code>langchain_classic.%s</code>" % m if m in C["mods"] else "none: use pydantic directly") for m in GONE10)
core_gone = sorted(m for m, ri in K["mods"].items() if pairs("langchain_core", ri)[-1][1] and "." not in m)
n_pairs = sum(sum(len(v) for v in D[l]["names"].values()) for l in LIBS)
kb = {l: (src / (l + ".json")).stat().st_size // 1024 for l in LIBS}
chk = lambda k: sum(CHK[l].get(k, 0) for l in LIBS)

FAQ = [
    ("How do I fix \"cannot import name 'LLMChain' from 'langchain.chains'\"?",
     "LangChain 1.0.0 (%s) removed langchain.chains; %s is the last release with it. Install the package that keeps the old code: "
     "pip install langchain-classic, then from langchain_classic.chains import LLMChain. Or pin pip install \"langchain<1.0.0\"." % (d10, last03)),
    ("Where did langchain.schema, langchain.memory and langchain.agents.AgentExecutor go?",
     "To langchain-classic: %d of the %d top-level modules that LangChain 1.0 removed exist under the same path in langchain_classic. Messages, "
     "documents and prompts are also in langchain_core (langchain_core.messages, langchain_core.documents, langchain_core.prompts). For agents, "
     "LangChain 1.0 has langchain.agents.create_agent." % (len(in_classic), len(GONE10))),
    ("Why did \"from langchain.chat_models import ChatOpenAI\" work in 0.3 but not in 1.0?",
     "In 0.1 to 0.3, langchain.chat_models did not define ChatOpenAI; it forwarded the name to langchain_community.chat_models with a deprecation "
     "warning, and only when langchain-community was installed. 1.0 dropped the forwarding. Use from langchain_openai import ChatOpenAI."),
    ("I installed langchain-classic and \"from langchain_classic.document_loaders import PyPDFLoader\" still fails. Why?",
     "langchain_classic forwards document loaders, vector stores and other integrations to langchain_community, like langchain 0.3 did. Install "
     "langchain-community, or import from langchain_community.document_loaders directly."),
    ("What did langchain-core 1.0 remove?",
     "The modules %s. Memory classes live in langchain_classic.memory; for pydantic_v1, import from pydantic directly." % ", ".join("langchain_core." + m for m in core_gone)),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["LangChain", "langchain-classic", "langchain-core", "ImportError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "LangChain import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the langchain, langchain-classic or langchain-core releases in which that name can be imported from that module, and where it is now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from langchain, langchain_classic and langchain_core, by release", "url": URL + "langchain.json", "dateModified": MOD,
     "description": "The names importable from every module of langchain (0.1.0 to %s, every release), langchain_classic and langchain_core, including names forwarded to langchain_community. Read from the source of each release tag." % L["latest"],
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + l + ".json"} for l in LIBS]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.pin code{white-space:nowrap}.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\n#res td:first-child{min-width:9em}td code{overflow-wrap:anywhere}main p,main h3,main li{overflow-wrap:break-word}\n"
js = (HERE.parent / "pta-imports" / "tool.js").read_text(encoding="ascii")
assert "</script" not in js and "LOOKUP_SIBLINGS" in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'LLMChain' from 'langchain.chains' (/usr/lib/python3/site-packages/langchain/chains/__init__.py)", "1.0.0", "LLMChain"),
      ("ModuleNotFoundError: No module named 'langchain.schema'", "", "langchain.schema"),
      ("from langchain.chat_models import ChatOpenAI", L["latest"], "ChatOpenAI"),
      ("from langchain.memory import ConversationBufferMemory", "", "ConversationBufferMemory"),
      ("from langchain_classic.document_loaders import PyPDFLoader", "", "PyPDFLoader (classic)"),
      ("ImportError: cannot import name 'content' from 'langchain_core.messages'", "0.3.79", "messages.content")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/langchain-ai/langchain/blob/"

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
<p class="lede"><strong>LangChain 1.0.0 ({d10}) removed {len(GONE10)} of its top-level modules, among them <code>langchain.chains</code>, <code>langchain.schema</code>, <code>langchain.memory</code>, <code>langchain.llms</code> and <code>langchain.vectorstores</code>; {last03} is the last release with them.</strong> {len(in_classic)} of them live on under the same path in the separate package <code>langchain-classic</code>: <code>pip install langchain-classic</code>, then <code>from langchain_classic.chains import LLMChain</code>. Messages, documents and prompts are in <code>langchain_core</code>. Model classes such as <code>ChatOpenAI</code> are in the provider packages (<code>langchain_openai</code>). Many names under <code>langchain.*</code> in 0.1 to 0.3 were never defined there: they were forwarded to <code>langchain_community</code> and worked only with it installed. For any name, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {L["asof"]} &middot; langchain {rel("langchain", 0)[0]} to {L["latest"]} (every release, {len(L["releases"])}), langchain-classic {rel("langchain_classic", 0)[0]} to {C["latest"]}, langchain-core {rel("langchain_core", 0)[0]} to {K["latest"]} &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'LLMChain' from 'langchain.chains'"></textarea>
<div class="grid">
<div><label for="v">Your version of that package (optional; <code>pip show langchain</code>)</label><input id="v" inputmode="decimal" placeholder="for example 1.0.0"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="langchain.json">langchain.json</a> ({kb["langchain"]} KB), <a href="langchain_classic.json">langchain_classic.json</a> ({kb["langchain_classic"]} KB) and <a href="langchain_core.json">langchain_core.json</a> ({kb["langchain_core"]} KB), loaded as needed; nothing you paste is sent anywhere. Covers {"{:,}".format(n_pairs)} module-and-name pairs.</p>
</div>

<h2 id="common">The imports people hit, and the import that works now</h2>
<p><strong>All of these work in langchain {rel("langchain", 0)[0]} to {last03} and fail from 1.0.0.</strong></p>
<div class="tw"><table class="flt">
<thead><tr><th>Old import</th><th>In 0.1 to 0.3</th><th>Now</th></tr></thead>
<tbody>
{chr(10).join(key_rows)}
</tbody></table></div>

<h2 id="modules">Which modules did LangChain 1.0 remove?</h2>
<p><strong>{len(GONE10)} top-level modules; the right column is where the same module lives from 1.0.0.</strong> What stayed in <code>langchain</code> is small: <code>agents</code> (with <code>create_agent</code>), <code>chat_models</code> (<code>init_chat_model</code>), <code>embeddings</code>, <code>messages</code>, <code>tools</code> and a few more.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Removed in 1.0.0</th><th>Same module now</th></tr></thead>
<tbody>
{mod_rows}
</tbody></table></div>

<h2 id="forwarded">Why did some imports work only with langchain-community installed?</h2>
<p><strong>In 0.1 to 0.3, modules such as <code>langchain.chat_models</code>, <code>langchain.llms</code>, <code>langchain.vectorstores</code> and <code>langchain.document_loaders</code> forwarded {"{:,}".format(n_fwd_names)} names to <code>langchain_community</code> through a module-level <code>__getattr__</code>, with a deprecation warning.</strong> Without langchain-community the same line raised ImportError, on any version. <code>langchain_classic</code> keeps that forwarding. The lookup marks each forwarded name and gives the <code>langchain_community</code> module to import from directly.</p>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag of the langchain monorepo, with Python's <code>ast</code> module; no release was installed or imported.</strong> langchain 0.x is read from <code>libs/langchain</code>, 1.x from <code>libs/langchain_v1</code>, langchain-classic from <code>libs/langchain/langchain_classic</code>, langchain-core from <code>libs/core</code>. A module's names are everything it binds at module level, plus the names its <code>__getattr__</code> serves: the strings of <code>__all__</code> and the keys of its lookup tables (<code>DEPRECATED_LOOKUP</code>, <code>_dynamic_imports</code>, <code>create_importer(...)</code>). Dates come from PyPI.</p>
<p>Checks, by a second reading: (1) each top-level name is found as plain text in <code>__init__.py</code> in every release of its range ({"{:,}".format(chk("CHK_TOP_PAIRS"))} name-and-release pairs). (2) A regular expression finds {"{:,}".format(chk("CHK_DEFS"))} definitions in {"{:,}".format(chk("CHK_DEF_FILES"))} file versions; all are among the names read. (3) Regular expressions over every module that defines <code>__getattr__</code> find {"{:,}".format(N_GETATTR)} served names (summed over releases); all are among the names read. (4) {chk("CHK_ANCHORS")} known facts hold, among them the reports under Sources.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import resolves in the source, with langchain-community installed for forwarded names.</li>
<li>langchain 0.0.x is not read; "0.1.0 or earlier" means the name was there in the first release read. langchain-core is read from 0.1.47 (its first git tag), at the first release of each minor.</li>
<li>langchain_community and the provider packages (langchain_openai, ...) are not read; the lookup names them only where langchain itself points to them.</li>
<li>A forwarded name is taken from <code>__all__</code>; in 0.1 the forwarding passed along any name of the target module, so a few more names worked.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>langchain-ai/langchain, release tags <code>v0.1.x</code>, <code>langchain==</code>, <code>langchain-classic==</code> and <code>langchain-core==</code>: every <code>.py</code> file of the package at each tag; for example <a href="{GH}langchain%3D%3D{last03}/libs/langchain/langchain/chat_models/__init__.py">langchain/chat_models/__init__.py at {last03}</a> (the forwarding) and <a href="{GH}langchain%3D%3D1.0.0/libs/partners/openai/langchain_openai/__init__.py">langchain_openai/__init__.py</a>. Release dates from PyPI.</li>
<li>Reports: <a href="https://forum.langchain.com/t/issues-importing-langchain-chains-langchain-prompts-after-installing-langchain-v1-1-2-3-modular-packages/2704">langchain.chains and langchain.prompts after v1</a>, <a href="https://forum.langchain.com/t/module-langchain-core-runnables-base-not-found-no-module-named-jsonpointer/2420">PyPDFLoader from langchain_classic.document_loaders</a>, <a href="https://forum.langchain.com/t/error-with-import-content-from-langchain-core-message-with-langchain-v1/1976">content from langchain_core.messages</a>.</li>
</ul>
<p>The same data as JSON: <a href="langchain.json">langchain.json</a>, <a href="langchain_classic.json">langchain_classic.json</a>, <a href="langchain_core.json">langchain_core.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/transformers-import-name-version-lookup/">"cannot import name ... from 'transformers'"</a> &middot; <a href="/en/huggingface-hub-import-name-version-lookup/">"... from 'huggingface_hub'"</a> &middot; <a href="/en/sentence-transformers-import-name-version-lookup/">"... from 'sentence_transformers'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = {json.dumps(LIBS)}; window.LOOKUP_PIP = {{"langchain_classic": "langchain-classic", "langchain_core": "langchain-core", "langchain_community": "langchain-community"}};
window.LOOKUP_SIBLINGS = {{"langchain": ["langchain_classic", "langchain_core"]}}; window.LOOKUP_PARTIAL = {{"langchain": true, "langchain_core": true}};
window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
for l in LIBS:
    d = dict(D[l])
    if l in ("langchain", "langchain_classic"):
        d["every"] = True
    (out_dir / (l + ".json")).write_text(json.dumps(d, separators=(",", ":"), sort_keys=True), encoding="ascii")
print("index.html %d bytes | 1.0 removed %d modules (%d in classic) | forwarded %d names | pairs %d" % (len(page), len(GONE10), len(in_classic), n_fwd_names, n_pairs), file=sys.stderr)
