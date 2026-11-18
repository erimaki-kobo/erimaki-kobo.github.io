#!/usr/bin/env python3
"""Build en/timm-import-name-version-lookup/ (index.html; timm.json is copied next to it).

Usage: python3 -I build_page.py <dir with timm.json> out_dir PUBLISHED MODIFIED chk.json
Every timm release is read (timm puts real changes in 1.0.x patches). ASCII only; the facts the prose names are asserted.
tool.js is the shared lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["timm"].
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK = json.load(open(sys.argv[5]))
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "timm.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/timm-import-name-version-lookup/"
TITLE = "timm.models.layers, timm.layers: import errors by version"
H1 = "ImportError: cannot import name 'X' from 'timm.models.layers', No module named 'timm.layers' or 'timm.models.layers.norm': which timm versions have it"
DESC = ("timm 0.9.0 moved timm.models.layers to timm.layers and removed 65 modules (timm.models.layers.norm among them). "
        "Paste the error: get the version and the fix.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def pairs(ri):
    r = T[ri]
    return list(zip(r[::2], r[1::2]))


def idx(v):
    return [k for k, r in enumerate(R) if r[0] == v][0]


def mspan(m):
    a, b = pairs(D["mods"][m])[-1]
    return R[a][0], (R[b][0] if b else None)


def span(m, n):
    a, b = pairs(D["names"][m][n])[-1]
    return R[a][0], (R[b][0] if b else None)


date_of = lambda v: R[idx(v)][1]
prev = lambda v: R[idx(v) - 1][0]
now = {m for m, ri in D["mods"].items() if pairs(ri)[-1][1] == 0}

assert mspan("layers") == ("0.9.0", None) and mspan("models.layers") == ("0.2.1", None)
assert mspan("models.layers.norm") == ("0.4.9", "0.9.0") and mspan("models.efficientnet_blocks")[1] == "0.9.0"
assert mspan("models.helpers")[1] is None and mspan("models._helpers") == ("0.9.0", None)
assert span("models.layers", "DropPath")[1] is None and span("layers", "DropPath") == ("0.9.0", None)
assert prev("0.9.0") == "0.6.13"
G09 = sorted(m for m, ri in D["mods"].items() if R[pairs(ri)[-1][1]][0] == "0.9.0" and pairs(ri)[-1][1])
assert len(G09) == 65, len(G09)
NEW_ONLY = sorted(set(D["names"]["layers"]) - set(D["names"]["models.layers"]))
n_new_only = len([n for n in NEW_ONLY if not n.startswith("_")])
d09 = date_of("0.9.0")


def successor(m):
    """the module of the newest release that holds the same file: timm.layers.<leaf>, models._<leaf>, or the same leaf"""
    leaf = m.split(".")[-1]
    parent = m.rsplit(".", 1)[0] if "." in m else ""
    cands = []
    if m.startswith("models.layers."):
        cands.append("layers." + m[len("models.layers."):])
    cands += [parent + "._" + leaf if parent else "_" + leaf, parent + "." + leaf.lstrip("_") if parent else leaf]
    if m.startswith("data.parsers"):
        cands.append(m.replace("data.parsers", "data.readers").replace("parser", "reader"))
    for c in cands:
        if c in now and c != m:
            return c
    same = sorted(k for k in now if k.split(".")[-1] in (leaf, "_" + leaf, leaf.replace("parser", "reader")))
    return same[0] if len(same) == 1 else None


rows09 = []
n_succ = 0
for m in G09:
    s = successor(m)
    n_succ += bool(s)
    rows09.append("<tr><td><code>timm.%s</code></td><td>%s</td></tr>" % (m, "<code>timm.%s</code>" % s if s else "none with the same file name"))
assert successor("models.layers.norm") == "layers.norm" and successor("models.efficientnet_blocks") == "models._efficientnet_blocks"
other_rows = []
for m, ri in sorted(D["mods"].items(), key=lambda kv: (-pairs(kv[1])[-1][1], kv[0])):
    b = pairs(ri)[-1][1]
    if b and R[b][0] != "0.9.0":
        s = successor(m)
        other_rows.append("<tr><td><code>timm.%s</code></td><td>%s</td><td>%s</td></tr>" % (m, R[b][0], "<code>timm.%s</code>" % s if s else "none with the same file name"))
n_mods, n_gone = len(D["mods"]), sum(1 for ri in D["mods"].values() if pairs(ri)[-1][1])
n_pairs = sum(len(v) for v in D["names"].values())
kb = (src / "timm.json").stat().st_size // 1024
HINTS = {}

FAQ = [
    ("How do I fix \"No module named 'timm.models.layers.norm'\"?",
     "timm 0.9.0 (%s) removed the submodules of timm.models.layers; the files moved to timm.layers (timm.layers.norm). The error usually comes "
     "from loading a model that was saved whole with torch.save(model) under timm %s or older: pickle stores the old module path. Either "
     "install pip install \"timm<0.9.0\" to load it, or load it once there and save model.state_dict() instead, which does not depend on module paths." % (d09, prev("0.9.0"))),
    ("How do I fix \"No module named 'timm.layers'\"?",
     "Your timm is older than 0.9.0. Upgrade with pip install -U \"timm>=0.9.0\", or, if you must stay on 0.6, import the same names from timm.models.layers."),
    ("Does \"from timm.models.layers import X\" still work?",
     "For the names that existed when timm.models.layers was moved, yes: timm keeps it as a mapping that warns \"Importing from timm.models.layers is "
     "deprecated, please import via timm.layers\". %d public names added to timm.layers since then are not in the mapping, so for those the old path "
     "fails; import them from timm.layers." % n_new_only),
    ("Why does this page read every timm release and not one per minor version?",
     "timm has stayed at 1.0 since 2024 and ships its changes in patch releases (1.0.3 to %s), so a module or name can appear or go in any of them." % LATEST),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["timm", "PyTorch Image Models", "ImportError", "ModuleNotFoundError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "timm import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError, a ModuleNotFoundError or an import statement and get the timm releases in which that module or name exists, the range to pin, and where it lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from timm and its modules, by release", "url": URL + "timm.json", "dateModified": MOD,
     "description": "For %d releases of timm (%s to %s): the names importable from every module as release ranges and the life of each module. Read from the source of each release tag." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "timm.json"}]},
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
EX = [("ModuleNotFoundError: No module named 'timm.models.layers.norm'", "", "timm.models.layers.norm"),
      ("ModuleNotFoundError: No module named 'timm.layers'", "0.6.13", "timm.layers on 0.6.13"),
      ("from timm.models.layers import DropPath, trunc_normal_, use_fused_attn", LATEST, "from timm.models.layers"),
      ("from timm.models.efficientnet_blocks import SqueezeExcite", "", "efficientnet_blocks"),
      ("ImportError: cannot import name 'resample_abs_pos_embed' from 'timm.layers'", "0.9.0", "resample_abs_pos_embed")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/huggingface/pytorch-image-models/blob/"

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
<p class="lede"><strong>Almost all of these come from timm 0.9.0 ({d09}), which moved <code>timm.models.layers</code> to <code>timm.layers</code> and removed {len(G09)} modules.</strong> <code>No module named 'timm.layers'</code> means your timm is older than 0.9.0: upgrade. <code>No module named 'timm.models.layers.norm'</code> (or <code>.helpers</code>, <code>.drop</code>, ...) means code or a pickled model from timm {prev("0.9.0")} or older: the file is now <code>timm.layers.norm</code>, or pin <code>pip install "timm&lt;0.9.0"</code>. <code>from timm.models.layers import X</code> still works for the names that existed in 0.9.0, with a FutureWarning, but not for the {n_new_only} names added to <code>timm.layers</code> since. For any other module or name, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; every timm release with a git tag, {R[0][0]} to {LATEST} ({N} releases) &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ModuleNotFoundError: No module named 'timm.models.layers.norm'"></textarea>
<div class="grid">
<div><label for="v">Your timm version (optional; <code>pip show timm</code>)</label><input id="v" inputmode="decimal" placeholder="for example 0.6.13"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="timm.json">timm.json</a> ({kb} KB); nothing you paste is sent anywhere. Covers {"{:,}".format(n_pairs)} module-and-name pairs in {n_mods} modules.</p>
</div>

<h2 id="v09">Which modules did timm 0.9.0 remove, and where are they now?</h2>
<p><strong>{len(G09)} modules left in 0.9.0; for {n_succ} of them a module with the same file exists in {LATEST}</strong>, under <code>timm.layers</code> for the old layer files and with a leading underscore for the builders and helpers under <code>timm.models</code>. An import that names one of these modules fails on 0.9.0 and later, and so does loading a model pickled with timm {prev("0.9.0")} or older that used them.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Removed in 0.9.0</th><th>Same file in {LATEST}</th></tr></thead>
<tbody>
{chr(10).join(rows09)}
</tbody></table></div>

<h2 id="other">Modules removed in other releases</h2>
<div class="tw"><table class="flt">
<thead><tr><th>Module</th><th>Gone in</th><th>Same file in {LATEST}</th></tr></thead>
<tbody>
{chr(10).join(other_rows)}
</tbody></table></div>
<p class="note">{n_gone} of the {n_mods} modules that have existed are gone from {LATEST}. Old paths such as <code>timm.models.helpers</code> and <code>timm.models.registry</code> still exist as mapping files that re-export the underscored modules.</p>

<h2 id="pickle">The error appears when I load a saved model. What then?</h2>
<p><strong>A model saved whole with <code>torch.save(model, path)</code> stores the module path of every class, and loading it imports those paths.</strong> A model saved under timm {prev("0.9.0")} or older names modules such as <code>timm.models.layers.norm</code>, so loading it with timm 0.9.0 or later raises <code>ModuleNotFoundError</code> from inside <code>pickle</code> (the traceback shows <code>find_class</code>). Load it once with <code>pip install "timm&lt;0.9.0"</code>, save <code>model.state_dict()</code>, and from then on build the model with <code>timm.create_model</code> and load the state dict.</p>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong> timm imports eagerly, so a module's names are everything it binds at module level, including what <code>from timm.layers.x import *</code> brings in. Dates come from PyPI.</p>
<p>Checks, by a second reading: (1) each of the {CHK["CHK_TOP"]} top-level names is found as plain text in <code>__init__.py</code> (or the modules it star-imports) in every release of its range ({"{:,}".format(CHK["CHK_TOP_PAIRS"])} name-and-release pairs). (2) A regular expression finds {"{:,}".format(CHK["CHK_DEFS"])} definitions in {"{:,}".format(CHK["CHK_DEF_FILES"])} file versions; all are among the names read. (3) <code>timm.models.layers</code> was read a second time with regular expressions in all {CHK["CHK_ML_RELEASES"]} releases where it is a mapping; the names match, apart from <code>torch</code>, <code>nn</code> and <code>F</code>, which a star import without <code>__all__</code> also passes along. (4) {CHK["CHK_ANCHORS"]} known facts hold, among them the reports under Sources.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the source.</li>
<li>Releases on PyPI without a git tag are not read: the early 0.1.x releases with even numbers and 0.3.0 to 0.3.2.</li>
<li>A name that works through the 0.9 mapping also prints a FutureWarning; the lookup does not mark that.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>huggingface/pytorch-image-models, release tags v{R[0][0]} to v{LATEST}: every <code>.py</code> file under <a href="{GH}v{LATEST}/timm/__init__.py">timm/</a>, including the mapping in <a href="{GH}v{LATEST}/timm/models/layers/__init__.py">timm/models/layers/__init__.py</a>; release dates from <a href="https://pypi.org/project/timm/#history">PyPI</a>.</li>
<li>Reports: <a href="https://github.com/huggingface/pytorch-image-models/discussions/1772">No module named 'timm.layers'</a>, <a href="https://forums.fast.ai/t/suddenly-i-get-an-error-on-huggingface/106471">No module named 'timm.models.layers.norm' (fast.ai forums)</a>, <a href="https://huggingface.co/spaces/lowrollr/birds_of_prey_classifier">the same error while unpickling a model</a>.</li>
</ul>
<p>The same data as JSON: <a href="timm.json">timm.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/transformers-import-name-version-lookup/">"cannot import name ... from 'transformers'"</a> &middot; <a href="/en/huggingface-hub-import-name-version-lookup/">"... from 'huggingface_hub'"</a> &middot; <a href="/en/datasets-import-name-version-lookup/">"... from 'datasets'"</a> &middot; <a href="/en/diffusers-import-name-version-lookup/">"... from 'diffusers'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["timm"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
D["every"] = True           # every tagged release was read (--every-release); the lookup says so under its answer
(out_dir / "timm.json").write_text(json.dumps(D, separators=(",", ":"), sort_keys=True), encoding="ascii")
print("index.html %d bytes | 0.9.0 removed %d (successor %d) | other gone %d | new-only %d | pairs %d" % (
    len(page), len(G09), n_succ, len(other_rows), n_new_only, n_pairs), file=sys.stderr)
