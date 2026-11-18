#!/usr/bin/env python3
"""Build en/openai-python-import-name-version-lookup/ (index.html; openai.json next to it).

Usage: python3 -I build_page.py <dir with openai.json> out_dir PUBLISHED MODIFIED chk.json
ASCII only; the facts the prose names are asserted. tool.js is the shared lookup of .github/pta-imports.
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK = json.load(open(sys.argv[5]))
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "openai.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/openai-python-import-name-version-lookup/"
TITLE = "cannot import name 'OpenAI' from 'openai': which version"
H1 = "ImportError: cannot import name 'OpenAI' from 'openai', module 'openai' has no attribute 'error', openai.ChatCompletion: which openai version has it"
DESC = ("from openai import OpenAI needs openai 1.0.0; openai.error and ChatCompletion.create are 0.x only (pin openai==0.28). "
        "Paste the error for any name.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def pairs(ri):
    r = T[ri]
    return list(zip(r[::2], r[1::2]))


def idx(v):
    return [k for k, r in enumerate(R) if r[0] == v][0]


def spans(m, n):
    return [(R[a][0], R[b][0] if b else None) for a, b in pairs(D["names"][m][n])]


def mspan(m):
    a, b = pairs(D["mods"][m])[-1]
    return R[a][0], (R[b][0] if b else None)


date_of = lambda v: R[idx(v)][1]
last_before = lambda v: R[idx(v) - 1][2]
assert spans("", "OpenAI") == [("1.0.0", None)] and spans("", "AzureOpenAI") == [("1.0.0", None)] and spans("", "AsyncOpenAI") == [("1.0.0", None)]
assert mspan("error") == (R[0][0], "1.0.0") and mspan("api_resources")[1] == "1.0.0"
assert spans("", "ChatCompletion") == [("0.27.0", "1.0.0"), ("1.2.0", None)]
PROXY = sorted(D["proxies"][""])
assert len(PROXY) == 15 and "ChatCompletion" in PROXY and "Completion" in PROXY
assert last_before("1.0.0") == "0.28.1"
assert spans("types.beta", "VectorStore") == [("1.21.0", "1.66.0")] and spans("types", "VectorStore") == [("1.66.0", None)]
L165 = last_before("1.66.0")
d10, d12 = date_of("1.0.0"), date_of("1.2.0")
last = N - 1
top_now = {n for n, r in D["names"][""].items() if pairs(r)[-1][1] == 0}
ERR = sorted(n for n in D["names"]["error"] if n[0].isupper())
err_rows = []
for n in ERR:
    now = n in top_now
    err_rows.append("<tr><td><code>openai.error.%s</code></td><td>%s</td></tr>" % (n, "<code>openai.%s</code> (from 1.0.0)" % n if now else "no class of that name in %s" % LATEST))
n_err_same = sum(1 for n in ERR if n in top_now)
assert {"RateLimitError", "APIError", "AuthenticationError", "APIConnectionError"} <= {n for n in ERR if n in top_now}
proxy_rows = "\n".join("<tr><td><code>openai.%s</code></td><td>%s to %s</td></tr>" % (n, spans("", n)[0][0], last_before("1.0.0")) for n in PROXY)
MSG = ("<code>APIRemovedInV1</code>: \"You tried to access openai.X, but this is no longer supported in openai&gt;=1.0.0\". "
       "The same message suggests <code>openai migrate</code> or <code>pip install openai==0.28</code>.")
n_pairs = sum(len(v) for v in D["names"].values())
n_mods = len(D["mods"])
kb = (src / "openai.json").stat().st_size // 1024
HINTS = {"openai::%s" % n: "<code>client = OpenAI()</code>, then the matching method (for ChatCompletion: <code>client.chat.completions.create(...)</code>)." for n in ("ChatCompletion",)}
HINTS["openai::error"] = "the exception classes are at the top level from 1.0.0: <code>openai.RateLimitError</code>, <code>openai.APIError</code>, <code>openai.BadRequestError</code> ..."
assert spans("", "BadRequestError") == [("1.0.0", None)]

FAQ = [
    ("How do I fix \"ImportError: cannot import name 'OpenAI' from 'openai'\"?",
     "The OpenAI client class exists from openai 1.0.0 (%s). Check the version the error comes from with python -c \"import openai; print(openai.__version__, openai.__file__)\": "
     "if it is 0.x, run pip install -U openai in that environment. If the path points into your own project, a file named openai.py (or a folder named openai) "
     "is shadowing the library; rename it." % d10),
    ("How do I fix \"AttributeError: module 'openai' has no attribute 'error'\"?",
     "openai 1.0.0 removed the openai.error module. The exception classes are at the top level now: openai.RateLimitError, openai.APIError, "
     "openai.AuthenticationError, openai.APIConnectionError and openai.OpenAIError keep their names; openai.InvalidRequestError has no class of that name in 1.x."),
    ("My old code calls openai.ChatCompletion.create. What happens on openai 1.x?",
     "From 1.2.0 (%s), \"from openai import ChatCompletion\" and openai.ChatCompletion succeed, but they are placeholders: using them raises APIRemovedInV1, "
     "\"You tried to access openai.ChatCompletion, but this is no longer supported in openai>=1.0.0\". In 1.0.0 and 1.1.x the name is missing altogether. "
     "Rewrite to client = OpenAI(); client.chat.completions.create(...), or pin pip install openai==0.28." % d12),
    ("Which version should I pin to keep openai 0.x code running?",
     "openai %s is the last 0.x release; pip install \"openai<1.0.0\" installs it. The 1.x message itself suggests openai==0.28." % last_before("1.0.0")),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["openai-python", "OpenAI API", "ImportError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "openai-python import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the openai-python releases in which that name can be imported from that module, and the range to pin.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from openai-python and its modules, by release", "url": URL + "openai.json", "dateModified": MOD,
     "description": "For %d releases of the openai Python package (%s to %s): the names importable from every module, including openai.types, and the 0.x names kept as placeholders. Read from the source of each release tag." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "openai.json"}]},
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
assert "</script" not in js and "LOOKUP_PROXY_MSG" in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'OpenAI' from 'openai' (/usr/local/lib/python3.11/site-packages/openai/__init__.py)", "0.28.1", "OpenAI on 0.28.1"),
      ("AttributeError: module 'openai' has no attribute 'error'", "1.40.0", "openai.error"),
      ("from openai import ChatCompletion", "1.30.0", "ChatCompletion on 1.x"),
      ("cannot import name 'AzureOpenAI' from 'openai'", "0.27.8", "AzureOpenAI"),
      ("from openai.types.beta import VectorStore", "1.70.0", "types.beta.VectorStore"),
      ("from openai import DefaultHttpxClient", "1.12.0", "DefaultHttpxClient")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/openai/openai-python/blob/"

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
<p class="lede"><strong><code>from openai import OpenAI</code> needs openai 1.0.0 ({d10}) or later; on 0.x it raises this ImportError.</strong> Check which copy is imported: <code>python -c "import openai; print(openai.__version__, openai.__file__)"</code>. A 0.x version means upgrade (<code>pip install -U openai</code>) in that environment; a path into your project means a file named <code>openai.py</code> is shadowing the library. The other direction: 0.x code on 1.x. <code>openai.error</code> is gone since 1.0.0 (the exceptions are <code>openai.RateLimitError</code> and so on). <code>openai.ChatCompletion</code> imports again from 1.2.0 but is a placeholder that raises <code>APIRemovedInV1</code> when used. To keep 0.x code, pin <code>pip install "openai&lt;1.0.0"</code> ({last_before("1.0.0")}). For any other name, including <code>openai.types</code>, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; openai {R[0][0]} to {LATEST}, the first release of each of {N} minor versions &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'OpenAI' from 'openai' (/usr/lib/python3/site-packages/openai/__init__.py)"></textarea>
<div class="grid">
<div><label for="v">Your openai version (optional; <code>pip show openai</code>)</label><input id="v" inputmode="decimal" placeholder="for example 0.28.1"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="openai.json">openai.json</a> ({kb} KB); nothing you paste is sent anywhere. Covers {"{:,}".format(n_pairs)} module-and-name pairs in {n_mods} modules.</p>
</div>

<h2 id="placeholders">Which 0.x names still import on 1.x, but only as placeholders?</h2>
<p><strong>These {len(PROXY)} names were classes in 0.x. From 1.2.0 ({d12}) the import succeeds again, but the object raises on first use</strong>: {MSG} In 1.0.0 and 1.1.x the import itself fails.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>A real class in</th></tr></thead>
<tbody>
{proxy_rows}
</tbody></table></div>

<h2 id="errors">Where did the openai.error exceptions go?</h2>
<p><strong>To the top level of <code>openai</code>, for the {n_err_same} that kept their names; the others have no class of the same name in 1.x.</strong> <code>except openai.error.RateLimitError:</code> becomes <code>except openai.RateLimitError:</code>.</p>
<div class="tw"><table class="flt">
<thead><tr><th>0.x</th><th>Now</th></tr></thead>
<tbody>
{chr(10).join(err_rows)}
</tbody></table></div>

<h2 id="types">Names under openai.types that moved</h2>
<p><strong>The 1.x and later releases move types between modules too.</strong> For example, <code>openai.types.beta.VectorStore</code> worked from 1.21.0 to {L165} and is <code>openai.types.VectorStore</code> from 1.66.0. When a name left a module, the lookup lists the other modules that had it in that release.</p>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong> 0.x is read from <code>openai/</code>, 1.x and later from <code>src/openai/</code>. A module's names are everything it binds at module level, including what star imports bring in. The placeholders are read from the <code>SYMBOLS</code> list in <code>src/openai/lib/_old_api.py</code>, which <code>openai/__init__.py</code> star-imports. Dates come from PyPI.</p>
<p>Checks, by a second reading: (1) each of the {CHK["CHK_TOP"]} top-level names is found as plain text in <code>__init__.py</code> (or the modules it star-imports) in every release of its range ({"{:,}".format(CHK["CHK_TOP_PAIRS"])} name-and-release pairs), and is not bound there in the release on either side ({CHK["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {"{:,}".format(CHK["CHK_DEFS"])} definitions in {"{:,}".format(CHK["CHK_DEF_FILES"])} file versions; all are among the names read. (3) {CHK["CHK_ANCHORS"]} known facts hold, among them the versions in the public reports under Sources.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the source.</li>
<li>Only the first release of each minor version was read (and the newest). A change in a patch release is attributed to the next minor.</li>
<li>Errors from other packages that use openai (for example <code>cannot import name ... from 'httpx'</code>) are not covered.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>openai/openai-python, release tags v{R[0][0]} to v{LATEST}: every <code>.py</code> file of the package; the placeholders and their message in <a href="{GH}v{LATEST}/src/openai/lib/_old_api.py">src/openai/lib/_old_api.py</a>; release dates from <a href="https://pypi.org/project/openai/#history">PyPI</a>.</li>
<li>Reports: <a href="https://community.openai.com/t/cannot-import-name-openai-from-openai/486147">Cannot import name 'OpenAI' from 'openai' (openai 0.27.4)</a>, <a href="https://community.openai.com/t/cannot-import-name-openai-from-openai/575538">the same error from a file named openai.py</a>, <a href="https://community.openai.com/t/cannot-import-name-azureopenai-from-openai/615606">Cannot import name 'AzureOpenAI'</a>.</li>
</ul>
<p>The same data as JSON: <a href="openai.json">openai.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/langchain-import-name-version-lookup/">"cannot import name ... from 'langchain'"</a> &middot; <a href="/en/transformers-import-name-version-lookup/">"... from 'transformers'"</a> &middot; <a href="/en/huggingface-hub-import-name-version-lookup/">"... from 'huggingface_hub'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["openai"]; window.LOOKUP_PROXY_MSG = {json.dumps(MSG)}; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "openai.json", out_dir / "openai.json")
print("index.html %d bytes | proxies %d | error classes %d (%d same) | pairs %d" % (len(page), len(PROXY), len(ERR), n_err_same, n_pairs), file=sys.stderr)
