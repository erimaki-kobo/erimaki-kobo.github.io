#!/usr/bin/env python3
"""Build en/flash-attn-import-name-version-lookup/ (index.html; flash_attn.json is copied next to it).

Usage: python3 -I build_page.py <dir with flash_attn.json> out_dir PUBLISHED MODIFIED chk.json anchors.json det.json
ASCII only. The facts the prose names are asserted. style.css is shared with .github/llama-args; tool.js is the shared
lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["flash_attn"].
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK, ANC = json.load(open(sys.argv[5])), json.load(open(sys.argv[6]))
DET = json.load(open(sys.argv[7]))   # does flash_attn_varlen_func take deterministic= (det.py)
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "flash_attn.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/flash-attn-import-name-version-lookup/"
TITLE = "cannot import name from 'flash_attn': the version that has it"
H1 = "ImportError: cannot import name 'flash_attn_unpadded_func' (or FlashMHA, flash_attn_varlen_func, any name) from 'flash_attn...': which flash-attn releases have it"
DESC = ("flash-attn 2.0 renamed flash_attn_unpadded_* to flash_attn_varlen_* and removed flash_attn.flash_attention (FlashMHA). Paste the "
        "error for any name.")
assert len(TITLE) <= 62 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


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

REN = [("flash_attn_unpadded_func", "flash_attn_varlen_func"), ("flash_attn_unpadded_kvpacked_func", "flash_attn_varlen_kvpacked_func"),
       ("flash_attn_unpadded_qkvpacked_func", "flash_attn_varlen_qkvpacked_func")]
for old, new in REN:
    assert span("flash_attn_interface", old) == ("0.2.1", "2.0.1"), old
    assert span("flash_attn_interface", new) == ("2.0.1", None) and span("", new) == ("2.0.1", None), new
assert span("flash_attn_interface", "flash_attn_unpadded_qkvpacked_split_func") == ("0.2.1", "2.0.1")
assert span("flash_attention", "FlashMHA") == ("0.2.1", "2.0.1") and span("flash_attention", "FlashAttention") == ("0.2.1", "2.0.1")
assert mspan("flash_attention")[-1] == ("0.2.1", "2.0.1")
assert span("", "flash_attn_func") == ("2.0.1", None) and span("", "flash_attn_with_kvcache") == ("2.2.0", None)
assert span("flash_attn_interface", "flash_attn_cuda") == ("0.2.1", "2.7.3") and span("flash_attn_interface", "flash_attn_gpu") == ("2.7.3", None)
assert span("modules.mha", "MHA")[0] == "0.2.1" and span("bert_padding", "unpad_input")[0] == "0.2.1"
assert all(a["git"] == a["expected"] == a["data"] for a in ANC) and len(ANC) == 10
assert DET == {"2.0.1": False, "2.2.0": False, "2.3.0": False, "2.4.1": True, "2.8.3": True}
d20, l1 = date_of("2.0.1"), last_before("2.0.1")
assert l1 == "1.0.9"
HINTS = {
    "flash_attn:flash_attn_interface:flash_attn_unpadded_func": "<code>flash_attn_varlen_func</code>, from 2.0. The first seven arguments are the same (q, k, v, cu_seqlens_q, cu_seqlens_k, max_seqlen_q, max_seqlen_k); <code>deterministic</code> is back from the 2.4 series.",
    "flash_attn:flash_attn_interface:flash_attn_unpadded_kvpacked_func": "<code>flash_attn_varlen_kvpacked_func</code>, from 2.0.",
    "flash_attn:flash_attn_interface:flash_attn_unpadded_qkvpacked_func": "<code>flash_attn_varlen_qkvpacked_func</code>, from 2.0.",
    "flash_attn:flash_attention:FlashMHA": "<code>flash_attn.modules.mha.MHA</code>, or call <code>flash_attn_func</code> directly.",
    "flash_attn:flash_attention:FlashAttention": "the functions in <code>flash_attn</code> (<code>flash_attn_func</code>, <code>flash_attn_varlen_func</code>), from 2.0.",
}
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(D["names"][m][n])[-1][1], k
ren_rows = "\n".join("<tr><td><code>%s</code></td><td><code>%s</code></td></tr>" % r for r in REN) + \
    "\n<tr><td><code>flash_attn.flash_attention.FlashAttention</code>, <code>FlashMHA</code></td><td><code>flash_attn.modules.mha.MHA</code> or the functions above</td></tr>"
n_top = len(D["names"][""])
n_mods = len(D["mods"])
n_mods_gone = sum(1 for ri in D["mods"].values() if pairs(ri)[-1][1])
n_pairs = sum(len(v) for v in D["names"].values())
kb = (src / "flash_attn.json").stat().st_size // 1024
NEW = [("flash_attn_func", "2.0.1"), ("flash_attn_varlen_func", "2.0.1"), ("flash_attn_with_kvcache", "2.2.0")]
new_rows = "\n".join("<tr><td><code>from flash_attn import %s</code></td><td>%s</td><td>%s</td></tr>" % (n, v, date_of(v)) for n, v in NEW)

FAQ = [
    ("How do I fix \"cannot import name 'flash_attn_unpadded_func' from 'flash_attn.flash_attn_interface'\"?",
     "flash-attn 2.0 renamed it to flash_attn_varlen_func (and the kvpacked and qkvpacked variants the same way); %s is the last "
     "1.x release with the old names. Change the import, or pin pip install \"flash-attn<2.0\" for code you cannot change. The first seven "
     "arguments are the same; 2.0 to 2.3 have no deterministic argument (the 2.4 series has it again)." % l1),
    ("Where did FlashMHA and flash_attn.flash_attention go?",
     "flash-attn 2.0 removed the flash_attn.flash_attention module with FlashAttention and FlashMHA. flash_attn.modules.mha.MHA "
     "is the module that remains, or call flash_attn_func directly."),
    ("Why does \"from flash_attn import flash_attn_func\" fail?",
     "The installed flash-attn is 1.x, which did not export it at the top level (the first release read that does is 2.0.1). "
     "If the error is an undefined symbol in flash_attn_2_cuda instead, the build does not match your PyTorch; that is not an "
     "import-name problem and reinstalling flash-attn against your PyTorch fixes it."),
    ("Does this page cover flash_attn.modules, flash_attn.ops and the AMD Triton backend?",
     "Yes: every module of flash-attn from %s to %s, %s module-and-name pairs in %d modules." % (R[0][0], LATEST, "{:,}".format(n_pairs), n_mods)),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["FlashAttention", "flash-attn", "ImportError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "flash-attn import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the flash-attn releases in which that name can be imported from that module, the range to pin, and where the name lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from flash_attn and its modules, by release", "url": URL + "flash_attn.json", "dateModified": MOD,
     "description": "For %d releases of flash-attn (%s to %s): the names importable from every module as release ranges and the life of each module. Read from the source of each release tag." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "flash_attn.json"}]},
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
EX = [("ImportError: cannot import name 'flash_attn_unpadded_func' from 'flash_attn.flash_attn_interface' (/usr/local/lib/python3.10/site-packages/flash_attn/flash_attn_interface.py)", "2.5.8", "flash_attn_unpadded_func"),
      ("from flash_attn.flash_attention import FlashMHA", "", "FlashMHA"),
      ("from flash_attn import flash_attn_func", "1.0.9", "flash_attn_func"),
      ("from flash_attn import flash_attn_with_kvcache", "2.1.1", "flash_attn_with_kvcache")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/Dao-AILab/flash-attention/blob/"
a_rows = "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
    e("flash_attn." + (a["module"] + "." if a["module"] else "") + a["name"]), a["release"], "has it" if a["expected"] else "does not") for a in ANC)

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
<p class="lede"><strong>flash-attn 2.0 ({d20} for 2.0.1, the first 2.x release on PyPI) renamed <code>flash_attn_unpadded_func</code>, <code>flash_attn_unpadded_kvpacked_func</code> and <code>flash_attn_unpadded_qkvpacked_func</code> to <code>flash_attn_varlen_func</code>, <code>flash_attn_varlen_kvpacked_func</code> and <code>flash_attn_varlen_qkvpacked_func</code>, and removed <code>flash_attn.flash_attention</code> (<code>FlashAttention</code>, <code>FlashMHA</code>); {l1} is the last release with the old names.</strong> The first seven arguments are the same, so renaming the import is usually the whole fix; only <code>deterministic</code> is missing in 2.0 to 2.3. The opposite error, <code>from flash_attn import flash_attn_func</code> failing, means a 1.x install. For any other name, in any module of flash-attn, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; flash-attn {R[0][0]} to {LATEST}, the first release of each of {N} minor versions &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'flash_attn_unpadded_func' from 'flash_attn.flash_attn_interface'"></textarea>
<div class="grid">
<div><label for="v">Your flash-attn version (optional; <code>pip show flash-attn</code>)</label><input id="v" inputmode="decimal" placeholder="for example 2.5.8"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="flash_attn.json">flash_attn.json</a> ({kb} KB); nothing you paste is sent anywhere. Covers {n_top} top-level names and {"{:,}".format(n_pairs)} module-and-name pairs in {n_mods} modules.</p>
</div>

<h2 id="v2">What did flash-attn 2.0 rename?</h2>
<p><strong>The 1.x names and their 2.x replacements; the new functions are also importable from <code>flash_attn</code> itself.</strong></p>
<div class="tw"><table class="flt">
<thead><tr><th>1.x (to {l1})</th><th>2.0 and later</th></tr></thead>
<tbody>
{ren_rows}
</tbody></table></div>
<p>Names that need a newer 2.x (the first release of each minor version that has them):</p>
<div class="tw"><table>
<thead><tr><th>Import</th><th>From</th><th>Date (PyPI)</th></tr></thead>
<tbody>
{new_rows}
</tbody></table></div>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>"cannot import name"</strong> is a version mismatch between the code and flash-attn; this page answers it.</li>
<li><strong>"undefined symbol" in <code>flash_attn_2_cuda</code></strong> is a different problem: the compiled extension was built for another PyTorch or CUDA. Reinstall flash-attn against the PyTorch you have (or use a prebuilt wheel that names your PyTorch and CUDA versions).</li>
<li>From 2.7.3 the extension module is imported as <code>flash_attn_gpu</code> inside <code>flash_attn_interface</code> (it was <code>flash_attn_cuda</code>); code that imported that internal name breaks there.</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag of Dao-AILab/flash-attention, with Python's <code>ast</code> module; no release was installed, imported or compiled.</strong> A module's names are everything it binds at module level and what <code>from .x import *</code> brings in; code under <code>if TYPE_CHECKING:</code> is skipped. Dates come from PyPI.</p>
<p>Checks: (1) each of the {CHK["CHK_TOP"]} top-level names is found as plain text in <code>flash_attn/__init__.py</code> in every release of its range ({CHK["CHK_TOP_PAIRS"]} name-and-release pairs) and not on either side ({CHK["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {"{:,}".format(CHK["CHK_DEFS"])} definitions in {CHK["CHK_DEF_FILES"]} file versions; all are among the names read. (3) {len(ANC)} release checks by plain-text search in the tags agree:</p>
<div class="tw"><table>
<thead><tr><th>Name</th><th>Release</th><th>Text and data</th></tr></thead>
<tbody>
{a_rows}
</tbody></table></div>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed, compiled or run. "Has it" means the import statement resolves in the Python source; whether the CUDA extension builds for your GPU is not covered.</li>
<li>Only the first release of each minor version on PyPI was read (and the newest). A change in a patch release is attributed to the next minor.</li>
<li>FlashAttention-3 (the <code>hopper/</code> directory of the repository) is built and installed separately and is not covered.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>Dao-AILab/flash-attention, release tags v{R[0][0]} to v{LATEST}: every <code>.py</code> file under <a href="{GH}v{LATEST}/flash_attn/__init__.py">flash_attn/</a>, for example <a href="{GH}v{l1}/flash_attn/flash_attn_interface.py">flash_attn_interface.py at v{l1}</a> and <a href="{GH}v2.0.1/flash_attn/flash_attn_interface.py">at v2.0.1</a>; release dates from <a href="https://pypi.org/project/flash-attn/#history">PyPI</a>.</li>
</ul>
<p>The same data as JSON: <a href="flash_attn.json">flash_attn.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/triton-import-name-version-lookup/">"No module named 'triton.ops'"</a> &middot; <a href="/en/vllm-import-name-version-lookup/">"cannot import name ... from 'vllm'"</a> &middot; <a href="/en/transformers-import-name-version-lookup/">"... from 'transformers'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["flash_attn"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "flash_attn.json", out_dir / "flash_attn.json")
print("index.html %d bytes | top %d | modules %d (gone %d) | pairs %d" % (len(page), n_top, n_mods, n_mods_gone, n_pairs), file=sys.stderr)
