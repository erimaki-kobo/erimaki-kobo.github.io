#!/usr/bin/env python3
"""Build en/gradio-import-name-version-lookup/ (index.html; gradio.json is copied next to it).

Usage: python3 -I build_page.py <dir with gradio.json> out_dir PUBLISHED MODIFIED chk1.json chk0.json anchors.json
ASCII only. The facts the prose names are asserted. style.css is shared with .github/llama-args; tool.js is the shared
lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["gradio"].
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK1, CHK0, ANC = json.load(open(sys.argv[5])), json.load(open(sys.argv[6])), json.load(open(sys.argv[7]))
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "gradio.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/gradio-import-name-version-lookup/"
TITLE = "cannot import name from 'gradio': the version that has it"
H1 = "ImportError: cannot import name 'X' from 'gradio' (inputs, Box, IOComponent, ChatInterface, ...): which releases have it"
DESC = ("gradio 4.0.0 removed gr.inputs, gr.outputs, Box and IOComponent (3.50.2 is the last with them); ChatInterface needs "
        "3.37.0. Paste the error for any name.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def pairs(ri):
    r = T[ri]
    return list(zip(r[::2], r[1::2]))


def span(m, n):
    a, b = pairs(D["names"][m][n])[-1]
    return R[a][0], (R[b][0] if b else None)


def first(m, n):
    return R[pairs(D["names"][m][n])[0][0]][0]


def idx(v):
    return [k for k, r in enumerate(R) if r[0] == v][0]


date_of = lambda v: R[idx(v)][1]
last_before = lambda v: R[idx(v) - 1][2]

G4 = sorted(n for n, ri in D["names"][""].items() if pairs(ri)[-1][1] == idx("4.0.0"))
assert {"inputs", "outputs", "Box", "Carousel", "Interpretation", "Variable", "StatusTracker", "Webcam", "Pil", "TimeSeries",
        "Parallel", "Series", "mix", "interpretation"} <= set(G4), G4
assert len(G4) == 21, len(G4)
assert span("components", "IOComponent")[1] == "4.0.0" and last_before("4.0.0") == "3.50.2"
assert span("", "make_waveform")[1] == "5.0.0" and span("", "HuggingFaceDatasetSaver")[1] == "5.0.0" and last_before("5.0.0") == "4.44.1"
assert span("", "ChatInterface") == ("3.37.0", None) and span("", "ChatMessage") == ("4.38.0", None)
assert span("", "http_server") == ("4.23.0", None) and span("", "Sidebar") == ("5.14.0", None)
assert first("", "Blocks") == R[0][0] == "3.0.1"
assert all(a["wheel"] == a["expected"] == a["data"] for a in ANC) and len(ANC) == 22
d4, l3 = date_of("4.0.0"), last_before("4.0.0")
d5, l4 = date_of("5.0.0"), last_before("5.0.0")

HINTS = {
    "gradio::inputs": "the components themselves: <code>gr.Textbox()</code>, <code>gr.Image()</code> and so on. gradio %s said: \"Usage of gradio.inputs is deprecated, and will not be supported in the future, please import your component from gradio.components\"." % l3,
    "gradio::outputs": "the components themselves (<code>gr.Textbox()</code>, <code>gr.Label()</code>, ...); gradio.outputs was deprecated in %s like gradio.inputs." % l3,
    "gradio::Box": "no named replacement; %s marks Box \"DEPRECATED\". <code>gr.Group()</code> or <code>gr.Column()</code> are the layouts that remain." % l3,
    "gradio::Carousel": "<code>gr.Gallery()</code>. gradio %s said: \"The Carousel component is deprecated. Please consider using the Gallery component\"." % l3,
    "gradio::Variable": "<code>gr.State()</code>. gradio %s said: \"Variable was renamed to State\"." % l3,
    "gradio::StatusTracker": "nothing; it was deprecated in %s and removed." % l3,
    "gradio::Webcam": "<code>gr.Image(sources=[\"webcam\"])</code> (4.0.0 renamed <code>source</code> to <code>sources</code>).",
    "gradio::Interpretation": "nothing; gradio 4.0.0 removed interpretation.",
    "gradio::interpretation": "nothing; gradio 4.0.0 removed interpretation.",
    "gradio::Parallel": "nothing in gradio; Parallel and Series (gradio.mix) were removed in 4.0.0.",
    "gradio::Series": "nothing in gradio; Parallel and Series (gradio.mix) were removed in 4.0.0.",
    "gradio:components:IOComponent": "<code>gradio.components.Component</code> (custom components subclass it from 4.0.0).",
}
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(D["names"][m][n])[-1][1], k

by = {}
for m in ("", "components"):
    for n, ri in D["names"][m].items():
        b = pairs(ri)[-1][1]
        if b and not (m == "components" and n[:1].islower() or n in ("Any", "Callable", "Dict", "List", "Literal", "Optional", "Set", "Tuple", "Type", "TYPE_CHECKING", "PIL", "Path", "Enum", "ModuleType", "UploadFile", "MarkdownIt", "Context", "TempFileManager", "FFmpeg")):
            by.setdefault((b, m), []).append(n)
gone_rows = []
for (b, m) in sorted(by, key=lambda k: (-k[0], k[1])):
    ns = sorted(by[(b, m)])
    gone_rows.append("<tr><td>%s</td><td>%s</td><td><code>%s</code></td><td>%d</td><td>%s</td></tr>" % (
        R[b][0], R[b][1], "gradio" + ("." + m if m else ""), len(ns), ", ".join("<code>%s</code>" % e(n) for n in ns)))
NEW = [("ChatInterface", "3.37.0"), ("LoginButton", "3.40.0"), ("on", "3.45.0"), ("http_server", "4.23.0"), ("render", "4.31.0"),
       ("ChatMessage", "4.38.0"), ("load_chat", "5.10.0"), ("Sidebar", "5.14.0"), ("Navbar", "5.45.0"), ("Server", "6.10.0")]
for n, v in NEW:
    assert span("", n) == (v, None), (n, span("", n))
new_rows = "\n".join("<tr><td><code>gr.%s</code></td><td>%s</td><td>%s</td></tr>" % (n, v, date_of(v)) for n, v in NEW)
n_top = len(D["names"][""])
n_top_gone = sum(1 for ri in D["names"][""].values() if pairs(ri)[-1][1])
n_mods = len(D["mods"])
n_mods_gone = sum(1 for ri in D["mods"].values() if pairs(ri)[-1][1])
n_pairs = sum(len(v) for v in D["names"].values())
kb = (src / "gradio.json").stat().st_size // 1024

FAQ = [
    ("How do I fix \"cannot import name 'inputs' from 'gradio'\" (or 'outputs')?",
     "gradio 4.0.0 (%s) removed gradio.inputs and gradio.outputs; %s is the last release with them. Replace gr.inputs.Textbox(...) "
     "with gr.Textbox(...), gr.outputs.Label(...) with gr.Label(...), and so on, as the %s deprecation message said. To run the old "
     "code unchanged, pin pip install \"gradio<4.0.0\"; on a Hugging Face Space, set sdk_version in README.md." % (d4, l3, l3)),
    ("How do I fix \"cannot import name 'IOComponent' from 'gradio.components'\"?",
     "IOComponent was removed in gradio 4.0.0 (%s is the last release with it). Code that subclasses it, usually a custom "
     "component or an old extension, has to subclass gradio.components.Component instead, or pin gradio<4.0.0." % l3),
    ("Why does \"from gradio import ChatInterface\" fail?",
     "Your gradio is older than 3.37.0, the first release (of each minor version read) that has ChatInterface. Upgrade gradio. "
     "The same holds for ChatMessage (4.38.0), Sidebar (5.14.0) and the other names in the table of additions."),
    ("gradio fails with \"cannot import name 'HfFolder' from 'huggingface_hub'\". Is that gradio's fault?",
     "It is the combination: gradio 4.9.0 to 5.7.x import HfFolder, which huggingface_hub 1.0.0 removed. Upgrade gradio to 5.8.0 or "
     "later, or pin huggingface_hub below 1.0.0. The huggingface_hub page on this site has the details."),
    ("Does this page cover gradio.components, gradio.utils and the other modules?",
     "Yes: every module of gradio from %s to %s, %s module-and-name pairs in %d modules." % (R[0][0], LATEST, "{:,}".format(n_pairs), n_mods)),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["Gradio", "ImportError", "Hugging Face Spaces"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "gradio import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the gradio releases in which that name can be imported from that module, the range to pin, and where the name lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from gradio and its modules, by release", "url": URL + "gradio.json", "dateModified": MOD,
     "description": "For %d releases of gradio (%s to %s): the names importable from every module as release ranges and the life of each module. Read from the source of each release." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "gradio.json"}]},
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
EX = [("ImportError: cannot import name 'inputs' from 'gradio' (/usr/local/lib/python3.10/site-packages/gradio/__init__.py)", "4.44.1", "inputs"),
      ("from gradio.components import IOComponent", "", "IOComponent"),
      ("from gradio import ChatInterface", "3.35.2", "ChatInterface"),
      ("ImportError: cannot import name 'make_waveform' from 'gradio'", "5.4.0", "make_waveform"),
      ("with gr.Box():", "", "Box")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/gradio-app/gradio/blob/"
a_rows = "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
    e(("gradio." + a["module"] + "." if a["module"] else "gradio.") + a["name"]), a["release"], "has it" if a["expected"] else "does not") for a in ANC)

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
<p class="lede"><strong>Most of these errors come from gradio 4.0.0 ({d4}), which removed <code>gr.inputs</code>, <code>gr.outputs</code>, <code>Box</code>, <code>Carousel</code>, <code>Variable</code>, <code>StatusTracker</code>, interpretation and {len(G4) - 8} more top-level names, and <code>IOComponent</code> from <code>gradio.components</code>; {l3} is the last release that has them.</strong> Replace <code>gr.inputs.Textbox(...)</code> with <code>gr.Textbox(...)</code> (the same for every input and output class), <code>Variable</code> with <code>State</code> and <code>Carousel</code> with <code>Gallery</code>. To run old code unchanged, pin <code>pip install "gradio&lt;4.0.0"</code>; on a Hugging Face Space the gradio version comes from <code>sdk_version</code> in the Space's README.md. The opposite error, a new name on an old gradio, means upgrading: <code>ChatInterface</code> needs 3.37.0, <code>ChatMessage</code> 4.38.0. For any other name, in any module of gradio, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; gradio {R[0][0]} to {LATEST}, the first release of each of {N} minor versions &middot; read from the source of each release, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'inputs' from 'gradio' (/usr/local/lib/python3.10/site-packages/gradio/__init__.py)"></textarea>
<div class="grid">
<div><label for="v">Your gradio version (optional; <code>pip show gradio</code>)</label><input id="v" inputmode="decimal" placeholder="for example 4.44.1"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="gradio.json">gradio.json</a> ({kb} KB); nothing you paste is sent anywhere. Covers {n_top} top-level names and {"{:,}".format(n_pairs)} module-and-name pairs in {n_mods} modules.</p>
</div>

<h2 id="v4">What did gradio 4.0.0 remove, and what replaces each name?</h2>
<p><strong>These {len(G4)} names left <code>from gradio import ...</code> (and <code>gr.X</code>) in 4.0.0, together with <code>gradio.components.IOComponent</code>.</strong> Where gradio named a replacement, it is quoted from the deprecation messages of {l3}; the lookup shows the same hints.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Removed in 4.0.0</th><th>Use instead</th></tr></thead>
<tbody>
{chr(10).join("<tr><td><code>%s</code></td><td>%s</td></tr>" % (("gradio.components." if k.split(":")[1] else "gr.") + k.split(":")[2], v) for k, v in HINTS.items())}
</tbody></table></div>
<p>gradio 5.0.0 ({d5}) removed <code>make_waveform</code> and <code>HuggingFaceDatasetSaver</code> (and <code>LogoutButton</code>) from the top level; {l4} is the last release with them.</p>

<h2 id="added">Which gradio release added the newer names?</h2>
<p><strong>"cannot import name" for a name that appears in current examples means the installed gradio is too old.</strong> The first release of each minor version that has the name:</p>
<div class="tw"><table>
<thead><tr><th>Name</th><th>First release</th><th>Date (PyPI)</th></tr></thead>
<tbody>
{new_rows}
</tbody></table></div>

<h2 id="removed">What did each gradio release remove from <code>gradio</code> and <code>gradio.components</code>?</h2>
<p><strong>{n_top_gone} of the {n_top} names that <code>from gradio import</code> has ever accepted are gone from {LATEST}.</strong> {n_mods_gone} of the {n_mods} modules that have existed are gone as well; paste <code>No module named 'gradio...'</code> into the lookup for any of them. Names that <code>gradio.components</code> only passed along from other packages (typing names, <code>numpy</code>, <code>PIL</code> and similar) are left out of this table but are in the lookup.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Release</th><th>Date (PyPI)</th><th>Module</th><th>Names</th><th>Removed names</th></tr></thead>
<tbody>
{chr(10).join(gone_rows)}
</tbody></table></div>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>On a Hugging Face Space</strong>, the gradio version is the <code>sdk_version</code> in the Space's README.md, not what <code>requirements.txt</code> says. A Space that stopped working after a rebuild usually got a newer gradio there.</li>
<li><strong>The path in parentheses</strong> is the copy of gradio that was imported. If it points into your project (a file named <code>gradio.py</code>), rename yours.</li>
<li><strong>The module after "from"</strong> decides which table applies: <code>from 'gradio'</code> is the top level, <code>from 'gradio.components'</code> that module. When the import is in another package (an extension or an old app template), upgrade or pin gradio to the range that package was written for.</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release, with Python's <code>ast</code> module; no release was installed or imported.</strong> gradio's git tags (<code>gradio@X.Y.Z</code>) start at 3.41.0; for 3.0 to 3.40 the package files were read from the wheels on PyPI (only the needed parts of each wheel, by HTTP range requests). gradio imports eagerly, so a module's names are everything it binds at module level: classes, functions, assignments, imports, and what <code>from .x import *</code> brings in. Code under <code>if TYPE_CHECKING:</code> is skipped. Dates come from PyPI.</p>
<p>Checks, by a second reading of the same files: (1) each of the {CHK1["CHK_TOP"]} top-level names read from the git tags is found as plain text in <code>__init__.py</code> (or the modules it star-imports) in every release of its range ({"{:,}".format(CHK1["CHK_TOP_PAIRS"] + CHK0["CHK_TOP_PAIRS"])} name-and-release pairs with the wheel part), and is not imported there in the release on either side ({CHK1["CHK_TOP_EDGES"] + CHK0["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {"{:,}".format(CHK1["CHK_DEFS"] + CHK0["CHK_DEFS"])} definitions in {"{:,}".format(CHK1["CHK_DEF_FILES"] + CHK0["CHK_DEF_FILES"])} file versions; all are among the names read. (3) Against a different source, the wheels on PyPI, {len(ANC)} release checks of the facts on this page agree:</p>
<div class="tw"><table>
<thead><tr><th>Name</th><th>Release</th><th>Wheel and data</th></tr></thead>
<tbody>
{a_rows}
</tbody></table></div>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the source.</li>
<li>Only the first release of each minor version was read (and the newest). A name added in a patch release is attributed to the next minor; a name removed in a patch release shows its removal one minor later.</li>
<li>Releases before 3.0.1 are not covered.</li>
<li>Errors that are not about import names, such as a component argument that was renamed (<code>source</code> to <code>sources</code> in 4.0.0), are not covered.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>gradio-app/gradio, release tags gradio@3.41.0 to gradio@{LATEST}: every <code>.py</code> file under <a href="{GH}gradio@{LATEST}/gradio/__init__.py">gradio/</a>; gradio 3.0.1 to 3.40.0 from the wheels on <a href="https://pypi.org/project/gradio/#history">PyPI</a>, which also gives the release dates.</li>
<li>Deprecation messages quoted: <a href="{GH}gradio@{l3}/gradio/inputs.py">inputs.py at {l3}</a>, <a href="{GH}gradio@{l3}/gradio/components/carousel.py">components/carousel.py</a>, <a href="{GH}gradio@{l3}/gradio/components/state.py">components/state.py</a>, <a href="{GH}gradio@{l3}/gradio/layouts.py">layouts.py</a> (Box).</li>
</ul>
<p>The same data as JSON: <a href="gradio.json">gradio.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/huggingface-hub-import-name-version-lookup/">"cannot import name 'HfFolder' from 'huggingface_hub'"</a> (gradio 4.9.0 to 5.7.x) &middot; <a href="/en/transformers-import-name-version-lookup/">"... from 'transformers'"</a> &middot; <a href="/en/diffusers-import-name-version-lookup/">"... from 'diffusers'"</a> &middot; <a href="/en/datasets-import-name-version-lookup/">"... from 'datasets'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["gradio"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "gradio.json", out_dir / "gradio.json")
print("index.html %d bytes | 4.0.0 removed %d | top %d (gone %d) | modules %d (gone %d) | pairs %d | rows %d" % (
    len(page), len(G4), n_top, n_top_gone, n_mods, n_mods_gone, n_pairs, len(gone_rows)), file=sys.stderr)
