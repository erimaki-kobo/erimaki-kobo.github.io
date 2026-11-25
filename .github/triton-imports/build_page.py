#!/usr/bin/env python3
"""Build en/triton-import-name-version-lookup/ (index.html; triton.json is copied next to it).

Usage: python3 -I build_page.py <dir with triton.json> out_dir PUBLISHED MODIFIED chk.json anchors.json torch_pins.json
ASCII only. The facts the prose names are asserted. style.css is shared with .github/llama-args; tool.js is the shared
lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["triton"].
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK, ANC, PINS = json.load(open(sys.argv[5])), json.load(open(sys.argv[6])), json.load(open(sys.argv[7]))
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "triton.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/triton-import-name-version-lookup/"
TITLE = "cannot import name from 'triton': the version that has it"
H1 = "No module named 'triton.ops', cannot import name 'libdevice' or 'triton_key' from 'triton...': which Triton releases have it"
DESC = ("Triton 3.2.0 removed triton.ops (bitsandbytes 0.45.0 and older import it); libdevice is in triton.language.extra.cuda from "
        "3.0.0. Paste the error.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


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

for m, n, want in [("ops", "matmul", ("2.0.0", "3.2.0")), ("language", "libdevice", ("2.0.0", "2.1.0")), ("language", "math", ("2.1.0", None)),
                   ("language.extra.cuda", "libdevice", ("3.0.0", None)), ("language.extra", "libdevice", ("3.0.0", None)),
                   ("compiler.compiler", "triton_key", ("3.0.0", "3.5.0")), ("runtime.autotuner", "PTXASError", ("3.3.0", None)),
                   ("backends.compiler", "GPUTarget", ("3.0.0", None)), ("compiler.compiler", "ASTSource", ("2.3.0", None)),
                   ("language.extra.cuda", "experimental_device_tensormap_create1d", ("3.2.0", "3.4.0")),
                   ("tools.tensor_descriptor", "TensorDescriptor", ("3.4.0", None)), ("language", "make_tensor_descriptor", ("3.4.0", None)),
                   ("", "jit", ("2.0.0", None)), ("", "Config", ("2.0.0", None)), ("", "autotune", ("2.0.0", None)), ("", "cdiv", ("2.0.0", None))]:
    assert span(m, n) == want, (m, n, span(m, n))
assert mspan("ops")[-1] == ("2.0.0", "3.2.0") and mspan("ops.matmul_perf_model")[-1] == ("2.0.0", "3.2.0") and mspan("ops.flash_attention")[-1][1] == "3.2.0"
assert mspan("language.libdevice")[-1][1] == "2.1.0" and mspan("common")[-1][1] == "3.0.0"
assert all(a["git"] == a["expected"] == a["data"] for a in ANC) and len(ANC) == 12
assert PINS["2.6.0"] == "3.2.0" and PINS["2.4.0"] == "3.0.0" and PINS["2.9.0"] == "3.5.0"
assert set(PINS["triton_key"]) == {"2.6.0", "2.7.0", "2.8.0"} and PINS["no_triton_key"] == ["2.9.0"]
d32, d30, d35, d21 = date_of("3.2.0"), date_of("3.0.0"), date_of("3.5.0"), date_of("2.1.0")
l31, l34 = last_before("3.2.0"), last_before("3.5.0")
assert (l31, l34) == ("3.1.0", "3.4.0")

HINTS = {
    "triton::ops": "nothing in Triton; the kernels in triton.ops (matmul, flash_attention, blocksparse, matmul_perf_model) were removed. bitsandbytes 0.45.1 and later ship their own copy of matmul_perf_model.",
    "triton:ops:matmul": "nothing in Triton. The tutorials in the Triton repository (python/tutorials/03-matrix-multiplication.py) show the kernel.",
    "triton:language:libdevice": "<code>triton.language.math</code> (2.1 to 2.3) or <code>from triton.language.extra.cuda import libdevice</code> (from 3.0.0).",
    "triton:compiler.compiler:triton_key": "nothing; PyTorch 2.6 to 2.8 look for it to decide whether Triton works. Install the Triton that PyTorch pins (the table on this page).",
    "triton:language.extra.cuda:experimental_device_tensormap_create1d": "the tensor descriptor API: <code>triton.language.make_tensor_descriptor</code> or <code>triton.tools.tensor_descriptor.TensorDescriptor</code> (from 3.4.0).",
}
for k in HINTS:
    l, m, n = k.split(":")
    assert (pairs(D["names"][m][n])[-1][1] if n else True), k
pin_rows = "\n".join("<tr><td>%s</td><td>%s</td></tr>" % (t, PINS[t]) for t in PINS["order"])
n_top = len(D["names"][""])
n_mods = len(D["mods"])
n_mods_gone = sum(1 for ri in D["mods"].values() if pairs(ri)[-1][1])
n_pairs = sum(len(v) for v in D["names"].values())
kb = (src / "triton.json").stat().st_size // 1024
gone_mod_rows = []
for i in range(1, N):
    ms = sorted(m for m, ri in D["mods"].items() if pairs(ri)[-1][1] == i and not m.startswith("experimental.gluon.language.amd"))
    if ms:
        gone_mod_rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (R[i][0], R[i][1], ", ".join("<code>triton.%s</code>" % e(m) for m in ms)))

FAQ = [
    ("How do I fix \"No module named 'triton.ops'\"?",
     "Triton 3.2.0 (%s) removed triton.ops; %s is the last release with it. The import is usually in bitsandbytes: 0.45.0 and older "
     "import triton.ops.matmul_perf_model when Triton is installed, so import bitsandbytes fails on PyTorch 2.6 and later, which "
     "install Triton 3.2 or newer. Upgrade bitsandbytes to 0.45.1 or later. Pinning Triton below 3.2 would break PyTorch's own pin." % (d32, l31)),
    ("How do I fix \"cannot import name 'libdevice' from 'triton.language.extra.cuda'\"?",
     "That path exists from Triton 3.0.0 (%s). The installed Triton is 2.x, usually because PyTorch is older than 2.4 (PyTorch 2.4.0 "
     "pins Triton 3.0.0). Upgrade PyTorch, which brings the matching Triton. In Triton 2.1 to 2.3 the same functions are in triton.language.math." % d30),
    ("Why does PyTorch say \"Cannot find a working triton installation\" when Triton is installed?",
     "PyTorch 2.6 to 2.8 check for Triton by importing triton_key from triton.compiler.compiler, which Triton 3.5.0 (%s) removed. "
     "With Triton 3.5 or newer next to PyTorch 2.8 or older, torch.compile thinks Triton is missing. Install the Triton that your "
     "PyTorch pins, or upgrade PyTorch (2.9.0 only imports triton)." % d35),
    ("Which Triton does my PyTorch need?",
     "Each PyTorch wheel on PyPI pins one Triton release on Linux: 2.4.0 needs 3.0.0, 2.6.0 needs 3.2.0, 2.9.0 needs 3.5.0, and so on. "
     "The table on this page lists them from the PyPI metadata."),
    ("Does this page cover the backends and experimental modules too?",
     "Yes: every module that the Triton wheel installs, %s to %s, %s module-and-name pairs in %d modules, including triton.backends "
     "and triton.language.extra, which are copied in at build time and are not under python/triton in the repository." % (R[0][0], LATEST, "{:,}".format(n_pairs), n_mods)),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["Triton", "ImportError", "PyTorch", "bitsandbytes"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "Triton import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the Triton releases in which that name can be imported from that module, the range to pin, and where the name lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from triton and its modules, by release", "url": URL + "triton.json", "dateModified": MOD,
     "description": "For %d releases of Triton (%s to %s): the names importable from every installed module as release ranges and the life of each module. Read from the Python files of the PyPI wheels." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "triton.json"}]},
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
EX = [("ModuleNotFoundError: No module named 'triton.ops'", "3.2.0", "triton.ops"),
      ("ImportError: cannot import name 'libdevice' from 'triton.language.extra.cuda' (/usr/local/lib/python3.10/site-packages/triton/language/extra/cuda/__init__.py)", "2.3.1", "libdevice"),
      ("from triton.compiler.compiler import triton_key", "3.5.0", "triton_key"),
      ("from triton.ops.matmul_perf_model import early_config_prune, estimate_matmul_time", "", "matmul_perf_model"),
      ("from triton.language.extra.cuda import experimental_device_tensormap_create1d", "3.4.0", "tensormap")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/triton-lang/triton/blob/"
a_rows = "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
    e("triton." + a["module"] + "." + a["name"]), a["release"], "has it" if a["expected"] else "does not") for a in ANC)

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
<p class="lede"><strong>Triton 3.2.0 ({d32}) removed <code>triton.ops</code> (<code>matmul</code>, <code>flash_attention</code>, <code>blocksparse</code>, <code>matmul_perf_model</code>); {l31} is the last release with it. Most "No module named 'triton.ops'" errors come from bitsandbytes 0.45.0 and older, which import it as soon as Triton is installed; PyTorch 2.6.0 and later install Triton 3.2 or newer. Upgrade bitsandbytes to 0.45.1 or later.</strong> The other common ones: <code>from triton.language.extra.cuda import libdevice</code> needs Triton 3.0.0 or newer (PyTorch 2.4.0 or newer), and PyTorch 2.6 to 2.8 report "Cannot find a working triton installation" with Triton 3.5.0 or newer, because they look for <code>triton_key</code>, which 3.5.0 removed. Install the Triton your PyTorch pins (table below). For any other name, in any module of Triton, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; Triton {R[0][0]} to {LATEST}, the first release of each of {N} minor versions &middot; read from the Python files of the PyPI wheels, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ModuleNotFoundError: No module named 'triton.ops'"></textarea>
<div class="grid">
<div><label for="v">Your Triton version (optional; <code>pip show triton</code>)</label><input id="v" inputmode="decimal" placeholder="for example 3.2.0"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="triton.json">triton.json</a> ({kb} KB); nothing you paste is sent anywhere. Covers {n_top} top-level names and {"{:,}".format(n_pairs)} module-and-name pairs in {n_mods} modules.</p>
</div>

<h2 id="pins">Which Triton does each PyTorch release install?</h2>
<p><strong>Each PyTorch wheel on PyPI pins one Triton release on Linux; a different Triton next to it is where most of these errors start.</strong> From the <code>Requires-Dist</code> of each PyTorch release on PyPI:</p>
<div class="tw"><table>
<thead><tr><th>PyTorch</th><th>Triton</th></tr></thead>
<tbody>
{pin_rows}
</tbody></table></div>
<p>PyTorch 2.1.0 lists no Triton requirement in its PyPI metadata and is left out. <code>pip show triton</code> and <code>python -c "import torch; print(torch.__version__)"</code> tell you which pair you have.</p>

<h2 id="removed">Which Triton modules disappeared, and in which release?</h2>
<p><strong>{n_mods_gone} of the {n_mods} modules that a Triton wheel has installed are gone from {LATEST}.</strong> Experimental Gluon modules for AMD gfx1250 are left out of this table but are in the lookup.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Gone in</th><th>Date (PyPI)</th><th>Modules</th></tr></thead>
<tbody>
{chr(10).join(gone_mod_rows)}
</tbody></table></div>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>The file in the traceback</strong> tells you whose import it is. <code>bitsandbytes/triton/...</code> means bitsandbytes (upgrade it); <code>torch/utils/_triton.py</code> or <code>torch/_inductor/...</code> means a PyTorch and Triton pair that do not match.</li>
<li><strong>Windows</strong>: the <code>triton</code> package on PyPI has Linux wheels only. Community builds such as <code>triton-windows</code> have their own version numbers; compare by the Triton version they report.</li>
<li><strong>The NVIDIA parts</strong> (<code>triton.backends.nvidia</code>, <code>triton.language.extra.cuda</code>) are copied into the wheel at build time from <code>third_party/nvidia</code>; in the repository they are not under <code>python/triton</code>. Reading the repository alone misses them, which is why this page reads the wheels.</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the Python files that <code>pip install triton</code> puts on disk: for the first release of each minor version, the <code>triton/**/*.py</code> of the Linux x86_64 wheel on PyPI were read (by HTTP range requests, without downloading the whole wheel) and parsed with Python's <code>ast</code> module.</strong> A module's names are everything it binds at module level and what <code>from .x import *</code> brings in; code under <code>if TYPE_CHECKING:</code> is skipped. Dates come from PyPI. The PyTorch pins and PyTorch's <code>has_triton_package()</code> were read from the PyTorch wheels and metadata on PyPI; the bitsandbytes imports from its release tags.</p>
<p>Checks: (1) each of the {CHK["CHK_TOP"]} top-level names is found as plain text in <code>triton/__init__.py</code> in every release of its range ({CHK["CHK_TOP_PAIRS"]} name-and-release pairs) and not on either side ({CHK["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {"{:,}".format(CHK["CHK_DEFS"])} definitions in {CHK["CHK_DEF_FILES"]} file versions; all are among the names read. (3) Against a different source, the triton git tags, {len(ANC)} release checks agree:</p>
<div class="tw"><table>
<thead><tr><th>Name or module</th><th>Release</th><th>Git and data</th></tr></thead>
<tbody>
{a_rows}
</tbody></table></div>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the Python files; Triton's compiled extension (<code>triton._C</code>) is not read.</li>
<li>Only the first release of each minor version was read (and the newest). A change in a patch release is attributed to the next minor.</li>
<li>Only the Linux x86_64 wheel (CPython 3.12, or 3.11 for older releases) was read. Other wheels of the same release should carry the same Python files.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The triton wheels on <a href="https://pypi.org/project/triton/#history">PyPI</a>, {R[0][0]} to {LATEST} (file names and sha256 in the build notes); triton-lang/triton release tags for the checks, for example <a href="{GH}v{l31}/python/triton/ops/__init__.py">python/triton/ops at v{l31}</a> and <a href="{GH}v{l34}/python/triton/compiler/compiler.py">compiler.py at v{l34}</a>.</li>
<li>PyTorch: the <code>Requires-Dist</code> of each release on <a href="https://pypi.org/project/torch/#history">PyPI</a>; <code>torch/utils/_triton.py</code> in the 2.6.0 to 2.9.0 wheels.</li>
<li>bitsandbytes: <a href="https://github.com/bitsandbytes-foundation/bitsandbytes/blob/0.45.0/bitsandbytes/triton/int8_matmul_mixed_dequantize.py">bitsandbytes/triton/int8_matmul_mixed_dequantize.py at 0.45.0</a> (imports <code>triton.ops.matmul_perf_model</code>) and <a href="https://github.com/bitsandbytes-foundation/bitsandbytes/blob/0.45.1/bitsandbytes/triton/int8_matmul_mixed_dequantize.py">at 0.45.1</a> (its own copy).</li>
</ul>
<p>The same data as JSON: <a href="triton.json">triton.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/triton-ptxas-arch-lookup/">"ptxas fatal: Value 'sm_121a' is not defined"</a> (which Triton and PyTorch support a GPU) &middot; <a href="/en/vllm-torch-cuda-driver-matrix/">which PyTorch and CUDA each vLLM release needs</a> &middot; <a href="/en/vllm-import-name-version-lookup/">"cannot import name ... from 'vllm'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["triton"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "triton.json", out_dir / "triton.json")
print("index.html %d bytes | top %d | modules %d (gone %d) | pairs %d" % (len(page), n_top, n_mods, n_mods_gone, n_pairs), file=sys.stderr)
