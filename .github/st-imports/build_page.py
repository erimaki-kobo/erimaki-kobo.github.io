#!/usr/bin/env python3
"""Build en/sentence-transformers-import-name-version-lookup/ (index.html; sentence_transformers.json next to it).

Usage: python3 -I build_page.py <dir with sentence_transformers.json> out_dir PUBLISHED MODIFIED chk.json names_hist_aliased.json
ASCII only; the facts the prose names are asserted. tool.js is the shared lookup of .github/pta-imports.
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK = json.load(open(sys.argv[5]))
HA = json.load(open(sys.argv[6]))
HERE = Path(__file__).resolve().parent
LIB = "sentence_transformers"
D = json.load(open(src / (LIB + ".json")))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/sentence-transformers-import-name-version-lookup/"
TITLE = "cannot import name from sentence_transformers: versions"
H1 = "ImportError: cannot import name 'X' from 'sentence_transformers' (or .models, .util, .losses, ...): which versions have it"
DESC = ("sentence-transformers 5.4.0 moved its modules but kept the old paths; models.BERT left in 2.0.0, util.snapshot_download "
        "in 5.1.0. Paste the error.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def pairs(ri):
    r = T[ri]
    return list(zip(r[::2], r[1::2]))


def idx(v):
    return [k for k, r in enumerate(R) if r[0] == v][0]


def span(m, n):
    a, b = pairs(D["names"][m][n])[-1]
    return R[a][0], (R[b][0] if b else None)


def mspan(m):
    a, b = pairs(D["mods"][m])[-1]
    return R[a][0], (R[b][0] if b else None)


date_of = lambda v: R[idx(v)][1]
last_before = lambda v: R[idx(v) - 1][2]
AL = HA["aliases"]["v" + LATEST]
assert not HA["aliases"].get("v5.3.0", {}).get("models") and AL["models"] == "sentence_transformer.modules"
FIRST_HOOK = next(t for t in HA["tags"] if len(HA["aliases"][t]) > 100)
assert FIRST_HOOK == "v5.4.0"
for m in ("models", "losses", "evaluation", "readers", "datasets", "trainer", "training_args", "model_card"):
    assert mspan(m)[1] is None and m in AL, m
assert span("models", "BERT") == ("0.1.0", "2.0.0") and span("models", "Transformer") == ("0.3.0", None)
assert span("util", "snapshot_download") == ("2.0.0", "5.1.0") and span("util", "cached_download") == ("2.0.0", "2.3.0")
assert span("", "SparseEncoder") == ("5.0.0", None) and span("", "CrossEncoder") == ("0.4.0", None)
d54, d20, d23, d51 = date_of("5.4.0"), date_of("2.0.0"), date_of("2.3.0"), date_of("5.1.0")

HINTS = {
    "sentence_transformers:util:snapshot_download": "<code>from huggingface_hub import snapshot_download</code>; sentence-transformers itself imports it from there.",
    "sentence_transformers:util:hf_hub_download": "<code>from huggingface_hub import hf_hub_download</code>.",
    "sentence_transformers:util:cached_download": "<code>huggingface_hub.hf_hub_download</code>; see the huggingface_hub page linked below.",
}
for n in ("BERT", "RoBERTa", "DistilBERT", "ALBERT", "CamemBERT", "XLMRoBERTa", "XLNet", "T5"):
    HINTS["sentence_transformers:models:" + n] = "<code>models.Transformer(\"model-name\")</code>, which loads any Hugging Face model (since 0.3.0)."
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(D["names"][m][n])[-1][1], k

mod_alias_rows = []
for old in sorted(o for o in AL if not any(c.isupper() for c in o.split(".")[-1]) and not o.startswith("sentence_transformer.")):
    mod_alias_rows.append("<tr><td><code>%s.%s</code></td><td><code>%s.%s</code></td></tr>" % (LIB, old, LIB, AL[old]))
n_alias = len(AL)

gone_mods = []
for m, ri in sorted(D["mods"].items(), key=lambda kv: (-pairs(kv[1])[-1][1], kv[0])):
    b = pairs(ri)[-1][1]
    if b:
        gone_mods.append("<tr><td><code>%s.%s</code></td><td>%s</td><td>%s</td></tr>" % (LIB, m, R[b][0], R[b][1]))
KEY = [("models", "BERT"), ("models", "RoBERTa"), ("models", "T5"), ("util", "cached_download"), ("util", "hf_hub_url"),
       ("util", "snapshot_download"), ("util", "hf_hub_download")]
key_rows = []
for m, n in KEY:
    a, b = span(m, n)
    key_rows.append("<tr><td><code>from %s.%s import %s</code></td><td>%s to %s</td><td>%s</td><td>%s</td></tr>" % (
        LIB, m, n, a, last_before(b), b, HINTS.get("%s:%s:%s" % (LIB, m, n), "")))
n_pairs = sum(len(v) for v in D["names"].values())
n_mods = len(D["mods"])
kb = (src / (LIB + ".json")).stat().st_size // 1024

FAQ = [
    ("Does \"from sentence_transformers.models import Transformer\" still work after 5.4.0?",
     "Yes. sentence-transformers %s (%s) moved its modules, for example sentence_transformers.models to sentence_transformers.sentence_transformer.modules, "
     "and installs an import hook that serves %d old paths from their new places, with a DeprecationWarning. An old path that fails on 5.4.0 or later "
     "fails for another reason: the name was removed, or it was never in that module." % ("5.4.0", d54, n_alias)),
    ("How do I fix \"cannot import name 'BERT' from 'sentence_transformers.models'\"?",
     "sentence-transformers 2.0.0 (%s) removed the per-architecture modules (BERT, RoBERTa, DistilBERT, XLNet and others). Use "
     "models.Transformer(\"bert-base-uncased\"), which loads any Hugging Face model, or pin pip install \"sentence-transformers<2.0.0\"." % d20),
    ("Importing sentence_transformers fails with \"cannot import name 'cached_download' from 'huggingface_hub'\". What do I upgrade?",
     "sentence-transformers. Releases before 2.3.0 (%s) import cached_download, which huggingface_hub removed in 0.26.0. pip install -U "
     "\"sentence-transformers>=2.3.0\" fixes it; the huggingface_hub page linked below has the details." % d23),
    ("Where did sentence_transformers.util.snapshot_download go?",
     "sentence-transformers 5.1.0 (%s) turned util into a package and stopped passing snapshot_download along. Import it from huggingface_hub, "
     "where it always came from." % d51),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["sentence-transformers", "ImportError", "embeddings"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "sentence-transformers import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the sentence-transformers releases in which that name can be imported from that module, the range to pin, and where it lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from sentence-transformers and its modules, by release", "url": URL + LIB + ".json", "dateModified": MOD,
     "description": "For %d releases of sentence-transformers (%s to %s): the names importable from every module, including the old module paths served by its import hook. Read from the source of each release tag." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + LIB + ".json"}]},
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
assert "</script" not in js and "window.LOOKUP_LIBS" in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'BERT' from 'sentence_transformers.models'", "2.2.2", "models.BERT"),
      ("from sentence_transformers.util import snapshot_download", "5.1.0", "util.snapshot_download"),
      ("from sentence_transformers import SparseEncoder", "4.1.0", "SparseEncoder"),
      ("from sentence_transformers.models import Transformer, Pooling", LATEST, "models after 5.4.0"),
      ("cannot import name 'cached_download' from 'sentence_transformers.util'", "", "util.cached_download")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/huggingface/sentence-transformers/blob/"

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
<p class="lede"><strong>Old import paths still work: sentence-transformers 5.4.0 ({d54}) moved its modules but serves {n_alias} old paths through an import hook, with a DeprecationWarning.</strong> So an import that fails is usually one of these. <code>models.BERT</code>, <code>models.RoBERTa</code> and the other per-architecture modules left in 2.0.0 ({d20}); use <code>models.Transformer</code>. <code>util.snapshot_download</code> left in 5.1.0 ({d51}); import it from <code>huggingface_hub</code>. <code>cannot import name 'cached_download' from 'huggingface_hub'</code> while importing sentence_transformers means your sentence-transformers is older than 2.3.0 ({d23}): upgrade it. Your version can also be older than the name, for example <code>SparseEncoder</code> needs 5.0.0. For any other name, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; sentence-transformers {R[0][0]} to {LATEST}, the first release of each of {N} minor versions &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'BERT' from 'sentence_transformers.models'"></textarea>
<div class="grid">
<div><label for="v">Your sentence-transformers version (optional; <code>pip show sentence-transformers</code>)</label><input id="v" inputmode="decimal" placeholder="for example 2.2.2"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="{LIB}.json">{LIB}.json</a> ({kb} KB); nothing you paste is sent anywhere. Covers {"{:,}".format(n_pairs)} module-and-name pairs in {n_mods} modules, old paths included.</p>
</div>

<h2 id="removed">Which names were really removed?</h2>
<p><strong>These are the removals people hit; the lookup has all of them.</strong></p>
<div class="tw"><table class="flt">
<thead><tr><th>Import</th><th>Works in</th><th>Fails from</th><th>Use instead</th></tr></thead>
<tbody>
{chr(10).join(key_rows)}
</tbody></table></div>

<h2 id="v54">Where did sentence-transformers 5.4.0 move each module?</h2>
<p><strong>The old path keeps working; the new one avoids the warning.</strong> The hook prints "Importing from '...' is deprecated and will be removed in a future version. Please use '...' instead." These are the module-level moves; the hook also serves the old per-class files, such as <code>sentence_transformers.losses.MultipleNegativesRankingLoss</code>.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Old path (still works)</th><th>New path from 5.4.0</th></tr></thead>
<tbody>
{chr(10).join(mod_alias_rows)}
</tbody></table></div>

<h2 id="modules">Which modules are gone for good?</h2>
<div class="tw"><table class="flt">
<thead><tr><th>Module</th><th>Gone in</th><th>Date (PyPI)</th></tr></thead>
<tbody>
{chr(10).join(gone_mods)}
</tbody></table></div>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong> A module's names are everything it binds at module level. The old paths come from the aliases each release installs: the <code>DEPRECATED_MODULE_PATHS</code> table and its import hook (5.4.0 on), and direct <code>sys.modules[...]</code> assignments (4.0.0 on); an old path gets the names of the module it points to. Dates come from PyPI.</p>
<p>Checks, by a second reading: (1) each of the {CHK["CHK_TOP"]} top-level names is found as plain text in <code>__init__.py</code>, or is a module, in every release of its range ({"{:,}".format(CHK["CHK_TOP_PAIRS"])} name-and-release pairs). (2) A regular expression finds {"{:,}".format(CHK["CHK_DEFS"])} definitions in {"{:,}".format(CHK["CHK_DEF_FILES"])} file versions; all are among the names read. (3) A regular expression finds the same {"{:,}".format(CHK["CHK_ALIASES"])} aliases (summed over releases) as the reading. (4) {CHK["CHK_ANCHORS"]} known facts hold.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the source.</li>
<li>Only the first release of each minor version was read (and the newest). A change in a patch release is attributed to the next minor.</li>
<li>The deprecated paths may be removed in a future release; the hook's message says so. The lookup follows the release you give.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>huggingface/sentence-transformers, release tags v{R[0][0]} to v{LATEST}: every <code>.py</code> file under <a href="{GH}v{LATEST}/sentence_transformers/__init__.py">sentence_transformers/</a>; the aliases in <a href="{GH}v{LATEST}/sentence_transformers/util/deprecated_import.py">util/deprecated_import.py</a>; release dates from <a href="https://pypi.org/project/sentence-transformers/#history">PyPI</a>.</li>
<li>Report: <a href="https://www.simplified.guide/sentence-transformers/import-fix-cached-download-error">cached_download error with sentence-transformers 2.2.2 and huggingface_hub 0.26.0</a>.</li>
</ul>
<p>The same data as JSON: <a href="{LIB}.json">{LIB}.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/huggingface-hub-import-name-version-lookup/">"cannot import name 'cached_download' from 'huggingface_hub'"</a> &middot; <a href="/en/transformers-import-name-version-lookup/">"... from 'transformers'"</a> &middot; <a href="/en/datasets-import-name-version-lookup/">"... from 'datasets'"</a> &middot; <a href="/en/peft-trl-accelerate-import-name-lookup/">"... from 'peft', 'trl' or 'accelerate'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["{LIB}"]; window.LOOKUP_PIP = {{"{LIB}": "sentence-transformers"}}; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / (LIB + ".json"), out_dir / (LIB + ".json"))
print("index.html %d bytes | aliases %d (module rows %d) | gone modules %d | pairs %d" % (len(page), n_alias, len(mod_alias_rows), len(gone_mods), n_pairs), file=sys.stderr)
