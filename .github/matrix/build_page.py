#!/usr/bin/env python3
"""Build en/vllm-torch-cuda-driver-matrix/index.html from matrix.json.

Usage: python3 -I build_page.py matrix.json out_dir MODIFIED(YYYY-MM-DD)
Writes out_dir/index.html and out_dir/matrix.json (a copy, published next to the page).
The page is ASCII only; every number in it comes from matrix.json or from the sources
listed at the bottom of the page. style.css and tool.js sit next to this script.
"""
import html, json, re, shutil, sys
from pathlib import Path

src, out_dir, MODIFIED = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
HERE = Path(__file__).resolve().parent
M = json.load(open(src))
R = M["releases"]                      # oldest -> newest
LATEST = R[-1]
AS_OF = M["as_of"]                    # the day the sources were read
PUBLISHED = "2026-11-11"              # first publication
URL = "https://erimaki-kobo.github.io/en/vllm-torch-cuda-driver-matrix/"
LIC = "https://creativecommons.org/licenses/by/4.0/"
TITLE = "vLLM Compatibility Matrix: PyTorch, CUDA, Driver by Release"
H1 = "vLLM compatibility matrix: which PyTorch, CUDA and NVIDIA driver each release needs"
DESC = ("Which PyTorch, CUDA and NVIDIA driver each vLLM release needs (v0.8.0 to v%s), "
        "read from the published wheels, plus a lookup for your driver and GPU." % LATEST["v"])
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))

e = html.escape


def py_range(spec):
    lo = re.search(r">=\s*3\.(\d+)", spec)
    hi = re.search(r"<\s*3\.(\d+)", spec)
    if lo and hi:
        return "3.%s&ndash;3.%d" % (lo.group(1), int(hi.group(1)) - 1)
    return "3.%s+" % lo.group(1)


def driver_floor(major):
    return M["driver_min"][str(major)]


# ---- facts derived from the data (asserted so the prose cannot drift from the table) ----
first_cu13 = next(r for r in R if r["cuda_major"] == 13)
last_cu12_pypi = [r for r in R if r["cuda_major"] == 12][-1]
last_cu12_variant = [r for r in R if any(x["cuda_major"] == 12 and x["torch_index_has"] for x in r["variants"])][-1]
cu12_variant = [x for x in last_cu12_variant["variants"] if x["cuda_major"] == 12][0]
cu13_only = R[R.index(last_cu12_variant) + 1:]          # releases with no CUDA 12 wheel or image at all
first_cu13_only = cu13_only[0]
last_cc70 = [r for r in R if "7.0" in r["archs"]][-1]
first_cc120 = next(r for r in R if "12.0" in r["archs"])
first_cc100 = next(r for r in R if "10.0" in r["archs"])
first_torch_cu128_pypi = next(r for r in R if float(r["torch_pypi_cuda"]) >= 12.8)
last_cu118 = [r for r in R if any(x["name"] == "cu118" for x in r["variants"])][-1]
last_py310 = [r for r in R if ">=3.10" in r["python"] or ">=3.9" in r["python"]][-1]
last_py39 = [r for r in R if ">=3.9" in r["python"]][-1]
docs_mismatch = [r for r in R if r["docs_cuda"] and int(r["docs_cuda"].split(".")[0]) != r["cuda_major"]]
assert first_cu13["v"] == "0.20.0" and last_cu12_pypi["v"] == "0.19.1"
assert last_cu12_variant["v"] == "0.32.0" and cu12_variant["name"] == "cu129" and cu12_variant["torch"] == "2.13.0"
# The prose says the newest release is CUDA 13.0 only with no variant wheels, like every release from first_cu13_only on.
# A release that brings back a CUDA 12 build, or moves to another CUDA, stops here: rewrite the lede and the last bullets.
assert first_cu13_only["v"] == "0.33.0" and [r["v"] for r in cu13_only] == ["0.33.0", "0.34.0"], [r["v"] for r in cu13_only]
for r in cu13_only:
    assert r["torch"] == "2.14.0" and r["cuda_major"] == 13 and r["built_cuda"] == "13.0" and not r["variants"], r["v"]
    assert r["index_variants"] == ["cu130"] and r["docker"] == ["default", "efa"] and r["archs"] == first_cu13_only["archs"], r["v"]
assert last_cc70["v"] == "0.19.1" and first_cc120["v"] == "0.9.2" and first_cc100["v"] == "0.9.0"
assert first_torch_cu128_pypi["v"] == "0.10.2" and last_cu118["v"] == "0.10.1.1"
assert last_py310["v"] == "0.31.0" and last_py39["v"] == "0.11.0"
assert docs_mismatch[0]["v"] == "0.20.0" and docs_mismatch[-1]["v"] == LATEST["v"] and len(docs_mismatch) == len([r for r in R if r["cuda_major"] == 13])
assert "cu129" not in M["torch"]["2.14.0"]["index"] and "cu129" in M["torch"]["2.13.0"]["index"]
assert M["torch"]["2.14.0"]["index"] == ["cu126", "cu130", "cu132"]
assert M["torch"]["2.11.0"]["pypi_cuda"] == "13.0" and M["torch"]["2.10.0"]["pypi_cuda"] == "12.8"
N_REL = len(R)
N_VARIANT_WHEELS = sum(len(r["variants"]) for r in R)

# ---- table rows (newest first) ----
rows = []
for r in reversed(R):
    cu = '<span class="s c%d">CUDA %d</span><br><span class="note">built with %s%s</span>' % (
        r["cuda_major"], r["cuda_major"], e(r["built_cuda"]), "; guide says %s" % e(r["docs_cuda"]) if r in docs_mismatch else "")
    var = []
    for x in r["variants"]:
        s = '<a href="%s">+%s</a> <span class="note">(torch %s, CUDA %d)</span>' % (e(x["url"]), e(x["name"]), e(x["torch"]), x["cuda_major"])
        if not x["torch_index_has"]:
            s += '<br><span class="note">PyTorch has no %s build of %s</span>' % (e(x["name"]), e(x["torch"]))
        var.append(s)
    dock = ", ".join(e(t) for t in r["docker"]) if r["docker"] else "&ndash;"
    rows.append(
        '<tr id="v%s" data-v="%s"><td><strong>%s</strong><br><span class="meta">%s</span></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
        '<td>%s<br><span class="note">%s</span></td><td>%s%s</td><td>%s</td><td class="you">&ndash;</td></tr>' % (
            r["v"].replace(".", "-"), e(r["v"]), e(r["v"]), e(r["date"]), e(r["torch"]), cu, e(driver_floor(r["cuda_major"])),
            e(r["torch_pypi_cuda"]), "<br>".join(var) if var else "&ndash;", py_range(r["python"]), e(r["platform"]),
            " ".join(e(a) for a in r["archs"]), " <span class=\"note\">(+PTX)</span>" if r["ptx"] else "", dock))
ROWS = "\n".join(rows)

# ---- data for the lookup (only the fields the script uses) ----
tool_data = {
    "as_of": AS_OF,
    "dmin": {"11": [450, 80, 2], "12": [525, 60, 13], "13": [580]},
    "torch": {k: v["index"] for k, v in M["torch"].items()},
    "rel": [{"v": r["v"], "torch": r["torch"], "py": r["python"], "cm": r["cuda_major"], "bc": r["built_cuda"],
             "tc": r["torch_pypi_cuda"], "pl": r["platform"], "ar": r["archs"], "dk": r["docker"] or [],
             "var": [{"n": x["name"], "t": x["torch"], "cm": x["cuda_major"], "pl": x["platform"], "u": x["url"]}
                     for x in r["variants"] if x["torch_index_has"]]} for r in R],
}
DATA_JSON = json.dumps(tool_data, separators=(",", ":"))
assert "</" not in DATA_JSON

FAQ = [
    ("Which PyTorch version does vLLM %s need?" % LATEST["v"],
     "<code>torch==%s</code>. The pin is exact (<code>==</code>) in every release from v0.8.0 to v%s; the table above lists each one. "
     "pip and uv will not install a prebuilt vLLM wheel next to any other PyTorch version." % (LATEST["torch"], LATEST["v"])),
    ("Why does vLLM fail with \"libcudart.so.13: cannot open shared object file\"?",
     "The vLLM wheel in the environment is a CUDA 13 build (every PyPI wheel from v%s on), but the installed PyTorch is a CUDA 12 build, "
     "so no CUDA 13 runtime library is present. It happens when <code>--torch-backend=cu129</code>, <code>cu128</code> or <code>cu126</code> "
     "is combined with the default wheel. On driver 580 or newer, install the default PyTorch. On an older driver, use the <code>+cu129</code> "
     "vLLM wheel (v%s to v%s)." % (first_cu13["v"], first_cu13["v"], last_cu12_variant["v"])),
    ("Does --torch-backend=cu129 install a CUDA 12 build of vLLM?",
     "No. The flag tells uv which PyTorch index to use for torch and its companion packages. The vLLM wheel still comes from PyPI, and from "
     "v%s that wheel is a CUDA 13 build. A CUDA 12 build of vLLM is a separate <code>+cu129</code> wheel, published on the GitHub release and "
     "on wheels.vllm.ai for v%s to v%s." % (first_cu13["v"], first_cu13["v"], last_cu12_variant["v"])),
    ("What is the newest vLLM I can install on an NVIDIA driver older than 580?",
     "v%s, using the <code>+cu129</code> wheel with <code>torch==%s+cu129</code>, on a Linux driver from %s up. v%s and v%s have no CUDA 12 wheel "
     "or image. On data center GPUs with an R535 or R570 driver, the CUDA 13 Docker image can also run in NVIDIA's forward-compatibility mode."
     % (last_cu12_variant["v"], cu12_variant["torch"], driver_floor(12), first_cu13_only["v"], LATEST["v"])),
    ("Which vLLM versions support RTX 50-series GPUs (compute capability 12.0)?",
     "The release build lists capability 12.0 from v%s. PyTorch must be a CUDA 12.8 or newer build as well: that is what PyPI serves from "
     "v%s (torch %s). For v%s up to v%s, add the cu128 PyTorch index."
     % (first_cc120["v"], first_torch_cu128_pypi["v"], first_torch_cu128_pypi["torch"], first_cc120["v"], last_cu118["v"])),
    ("Does vLLM still support the Tesla V100 (compute capability 7.0)?",
     "Not after v%s. v%s removed capability 7.0 from the build targets and raised the documented minimum to 7.5, and PyTorch's CUDA 13 builds "
     "start at Turing (7.5)." % (last_cc70["v"], first_cu13["v"])),
    ("Can I use a different PyTorch version than the pinned one?",
     "Not with the prebuilt wheels. vLLM's install guide says that a different CUDA version or an existing PyTorch installation requires "
     "building vLLM from source."),
]


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


FAQ_HTML = "\n".join("<dt>%s</dt>\n<dd>%s</dd>" % (e(q), a) for q, a in FAQ)

ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL,
     "datePublished": PUBLISHED, "dateModified": MODIFIED, "inLanguage": "en",
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
     "about": ["vLLM", "PyTorch", "CUDA", "NVIDIA driver"], "isBasedOn": URL + "matrix.json"},
    {"@type": "WebApplication", "@id": URL + "#tool", "name": "vLLM release lookup by NVIDIA driver and GPU", "url": URL + "#lookup",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (runs in the browser)", "isAccessibleForFree": True,
     "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
     "description": "Enter an NVIDIA driver version and GPU; get the newest vLLM release with a prebuilt wheel for it and the install command."},
    {"@type": "Dataset", "@id": URL + "#data", "name": "vLLM release compatibility data (PyTorch pin, CUDA, driver floor, wheel variants)",
     "description": "One record per stable vLLM release from v0.8.0 to v%s: pinned PyTorch, CUDA major linked by the PyPI wheel, CUDA variant "
                    "wheels, Python range, wheel platform tag, GPU build targets and Docker tags." % LATEST["v"],
     "url": URL, "dateModified": AS_OF, "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "license": LIC,
     "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "matrix.json"}},
    {"@type": "FAQPage", "@id": URL + "#faq",
     "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": "vLLM compatibility matrix", "item": URL}]},
]}
LD_JSON = json.dumps(ld)
assert "</" not in LD_JSON

CSS = (HERE / "style.css").read_text(encoding="ascii")
JS = (HERE / "tool.js").read_text(encoding="ascii")

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<meta name="description" content="@@DESC@@">
<link rel="canonical" href="@@URL@@">
<meta property="og:type" content="article">
<meta property="og:title" content="@@TITLE@@">
<meta property="og:description" content="@@DESC@@">
<meta property="og:url" content="@@URL@@">
<script type="application/ld+json">@@LD@@</script>
<style>@@CSS@@</style>
</head>
<body>
<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>@@H1@@</h1>
<p class="lede"><strong>vLLM v@@LV@@ (released @@LDATE@@) pins <code>torch==@@LTORCH@@</code>, is built for CUDA 13.0 only, and needs NVIDIA Linux driver 580 or newer.</strong> Every PyPI wheel since v@@CU13V@@ loads <code>libcudart.so.13</code>, although the install guide at each of those tags still names CUDA 12.9 as the default. On a driver older than 580, the newest release with a prebuilt CUDA 12 wheel is v@@V12VAR@@ (the <code>+cu129</code> wheel with <code>torch==@@T12VAR@@+cu129</code>), and the newest release where a plain <code>pip install vllm</code> gives a CUDA 12 build is v@@V12PYPI@@. <code>--torch-backend=cu129</code> changes which PyTorch is downloaded. It does not change the vLLM wheel that PyPI serves.</p>
<p class="meta">Published @@PUB@@ &middot; Updated @@MOD@@ &middot; Data as of @@ASOF@@ &middot; @@NREL@@ stable releases, v0.8.0 to v@@LV@@ &middot; Linux x86_64</p>

<h2 id="lookup">Which vLLM release can my driver and GPU run?</h2>
<p>Enter what <code>nvidia-smi</code> reports. The answer is the newest release that has a prebuilt wheel for that combination, with the command to install it. Python and glibc are optional filters.</p>
<div class="card">
<div class="grid">
<div><label for="drv">NVIDIA driver version (Linux)</label><input id="drv" inputmode="decimal" placeholder="570.133.07" autocomplete="off"></div>
<div><label for="gpu">GPU</label><select id="gpu">
<option value="12.0">RTX 50 series, RTX PRO Blackwell (12.0)</option>
<option value="10.0">B200, GB200 (10.0)</option>
<option value="9.0">H100, H200 (9.0)</option>
<option value="8.9" selected>RTX 40 series, L4, L40S, RTX Ada (8.9)</option>
<option value="8.6">RTX 30 series, A10, A40, RTX A-series (8.6)</option>
<option value="8.0">A100, A30 (8.0)</option>
<option value="7.5">T4, RTX 20 series, Quadro RTX (7.5)</option>
<option value="7.0">V100, TITAN V (7.0)</option>
<option value="6.x">GTX 10 series, P40, P100 (6.x)</option>
</select></div>
<div><label for="py">Python (optional)</label><select id="py"><option value="">any</option><option>3.9</option><option>3.10</option><option>3.11</option><option>3.12</option><option>3.13</option><option>3.14</option></select></div>
<div><label for="glibc">glibc (optional, from <code>ldd --version</code>)</label><input id="glibc" inputmode="decimal" placeholder="2.35" autocomplete="off"></div>
</div>
<div class="row"><button id="go" type="button">Find release</button><span id="status" role="status"></span></div>
<div id="res" aria-live="polite"></div>
</div>
<p class="note">Driver version only: <code>nvidia-smi --query-gpu=driver_version --format=csv,noheader</code>. The lookup runs in your browser on the table below; nothing is sent anywhere. It covers Linux x86_64 wheels from PyPI and from the vLLM GitHub releases. The glibc filter compares against the wheel's platform tag, which is what pip checks.</p>

<h2 id="table">Which PyTorch, CUDA and driver does each vLLM release need?</h2>
<p><strong>Each release pins one exact PyTorch version. On PyPI, releases up to v@@V12PYPI@@ are CUDA 12 builds and releases from v@@CU13V@@ are CUDA 13 builds.</strong> One row per stable release, newest first. "PyPI wheel" is what <code>pip install vllm==&lt;version&gt;</code> downloads. The PyTorch pin is exact, the CUDA major of the wheel sets the driver floor, and the "Other CUDA wheels" column shows where a build for another CUDA version exists.</p>
<div class="tw wide"><table id="matrix">
<thead><tr><th>vLLM</th><th>PyTorch pin</th><th>PyPI wheel links</th><th>Driver floor (Linux)</th><th>PyTorch on PyPI: CUDA</th><th>Other CUDA wheels (GitHub release)</th><th>Python / wheel tag</th><th>GPU targets (x86_64 build)</th><th>Docker tag suffixes</th><th>Your system</th></tr></thead>
<tbody>
@@ROWS@@
</tbody></table></div>
<dl>
<dt>PyTorch pin</dt><dd>The <code>torch==</code> requirement in the published wheel's metadata. It equals <code>requirements/cuda.txt</code> at the release tag for all @@NREL@@ releases.</dd>
<dt>PyPI wheel links</dt><dd>The CUDA runtime that the wheel's compiled extensions load: <code>libcudart.so.12</code> or <code>libcudart.so.13</code>, read from the wheel itself. "Built with" is the CUDA version vLLM's build defaulted to at that tag (<code>VLLM_MAIN_CUDA_VERSION</code>). "Guide says" appears where the install guide at that tag names a different default.</dd>
<dt>Driver floor</dt><dd>NVIDIA's minimum Linux driver for that CUDA major: 525.60.13 for CUDA 12.x and 580 for CUDA 13.x (the first R580 release was 580.65.06). A new GPU can need a newer driver than this.</dd>
<dt>PyTorch on PyPI: CUDA</dt><dd>The CUDA version of the pinned PyTorch that PyPI serves. PyTorch's CUDA 12.6 builds stop at Hopper (9.0); CUDA 12.8 and newer builds include Blackwell (10.0, 12.0); CUDA 13 builds start at Turing (7.5).</dd>
<dt>Other CUDA wheels</dt><dd><code>+cuNNN</code> wheels attached to the GitHub release, with the PyTorch they pin. Install one together with the PyTorch index of the same name, for example <code>--extra-index-url https://download.pytorch.org/whl/cu129</code>.</dd>
<dt>GPU targets</dt><dd>The compute capabilities requested for the x86_64 release build. vLLM compiles each kernel for its own subset, so a listed target means the wheel runs on that GPU, not that every kernel has a native build for it.</dd>
<dt>Docker tag suffixes</dt><dd>Suffixes of <code>vllm/vllm-openai:v&lt;version&gt;</code> on Docker Hub: "default" is the bare tag, "cu129" is <code>:v&lt;version&gt;-cu129</code>. The default image follows the PyPI wheel's CUDA major.</dd>
</dl>
<p>The same data as JSON: <a href="matrix.json">matrix.json</a>, licensed <a href="@@LIC@@">CC BY 4.0</a>.</p>

<h2 id="changes">When did vLLM change CUDA, PyTorch and GPU support?</h2>
<ul>
<li><strong>v@@CC100V@@ (@@CC100D@@):</strong> the PyPI wheel is built with CUDA 12.8 and the build targets include Blackwell (10.0). Capability 12.0 (RTX 50 series) is listed from v@@CC120V@@.</li>
<li><strong>v@@T128V@@ (@@T128D@@):</strong> the pin moves to torch @@T128T@@, the first pinned PyTorch whose PyPI build uses CUDA 12.8. Before that (torch 2.7.x, CUDA 12.6 on PyPI) a Blackwell GPU needed the cu128 PyTorch index.</li>
<li><strong>v@@CU118V@@:</strong> the last release with a <code>+cu118</code> wheel (CUDA 11.8).</li>
<li><strong>v@@CU13V@@ (@@CU13D@@):</strong> the default build switches to CUDA 13.0 (<a href="https://github.com/vllm-project/vllm/commit/3ed5231c6a7a9042a6ac4000e569ad2d85a21b9a">commit 3ed5231c6</a>, PR #39878). The PyPI wheel loads <code>libcudart.so.13</code>, torch 2.11.0 on PyPI is a CUDA 13.0 build, capability 7.0 leaves the build targets and the documented minimum becomes 7.5. CUDA 12.9 stays available as the <code>+cu129</code> wheel and the <code>-cu129</code> image.</li>
<li><strong>v@@V12VAR@@ (@@D12VAR@@):</strong> requires Python 3.11 or newer (v@@PY310V@@ is the last release for Python 3.10; v@@PY39V@@ the last for 3.9). It is the last release with a <code>+cu129</code> wheel and <code>-cu129</code> images.</li>
<li><strong>v@@ONLY13V@@ (@@ONLY13D@@):</strong> torch @@ONLY13T@@. CUDA 12.9 is removed from the release pipeline (<a href="https://github.com/vllm-project/vllm/commit/083d61622ba5e883b925481f3a4322a24353af42">commit 083d61622</a>, PR #62575); the release notes say wheels and images are CUDA 13.0 only. PyTorch publishes no cu129 build of @@ONLY13T@@ either: its index has cu126, cu130 and cu132.</li>
<li><strong>v@@LV@@ (@@LDATE@@):</strong> no change to any column: the same torch @@LTORCH@@ pin, CUDA 13.0 only, the same GPU targets, Python range and image tags as v@@ONLY13V@@. The GitHub release carries no <code>+cuNNN</code> wheel. The x86_64 wheel on PyPI is smaller, @@LSIZE@@ MB against @@PSIZE@@ MB for v@@ONLY13V@@.</li>
</ul>
<p class="note">The install guide at the v@@LV@@ tag still shows a command that takes the version from <code>releases/latest</code> and builds the URL of a <code>+cu130</code> wheel on the GitHub release. Neither v@@ONLY13V@@ nor v@@LV@@ has a <code>+cuNNN</code> wheel there, so that URL does not exist: the wheel without a suffix, on PyPI and on the release, is the CUDA 13.0 build. The GitHub release titled v@@ONLY13V@@ is attached to the tag <code>v0.33.0rc3</code> (still so on @@ASOF@@); the v@@LV@@ release is attached to its own tag.</p>

<h2 id="errors">What do the common install errors mean?</h2>
<p>Match the message to its row. The versions involved are the ones in the table above.</p>
<div class="tw"><table>
<thead><tr><th>Message</th><th>Cause</th><th>What to change</th></tr></thead>
<tbody>
<tr><td><code>ImportError: libcudart.so.13: cannot open shared object file</code></td><td>A CUDA 13 build of vLLM (the PyPI wheel from v@@CU13V@@, or a <code>+cu130</code> wheel) next to a CUDA 12 build of PyTorch. Typical trigger: <code>--torch-backend=cu129</code>, <code>cu128</code> or <code>cu126</code> with the default wheel.</td><td>Driver 580 or newer: reinstall without a CUDA 12 backend. Older driver: use the <code>+cu129</code> vLLM wheel of v@@CU13V@@ to v@@V12VAR@@ with the cu129 PyTorch index.</td></tr>
<tr><td><code>ImportError: libcudart.so.12: cannot open shared object file</code></td><td>The reverse: a CUDA 12 build of vLLM (PyPI wheel up to v@@V12PYPI@@, or a <code>+cu129</code> wheel) next to a CUDA 13 PyTorch.</td><td>Install PyTorch from the index that matches the vLLM wheel, or move to a release whose PyPI wheel is CUDA 13.</td></tr>
<tr><td><code>The NVIDIA driver on your system is too old (found version ...)</code></td><td>Raised by PyTorch when the driver is below what its CUDA build needs, for example a CUDA 13 PyTorch on a driver older than 580.</td><td>Update the driver, or pick a release and wheel from the table whose driver floor you meet.</td></tr>
<tr><td><code>... with CUDA capability sm_120 is not compatible with the current PyTorch installation</code></td><td>The installed PyTorch is a CUDA 12.6 or older build, which stops at Hopper. PyPI serves such a build for torch 2.7.x and older.</td><td>Use a release from v@@T128V@@, or add the cu128 PyTorch index for v@@CC120V@@ to v@@CU118V@@.</td></tr>
<tr><td><code>undefined symbol: ...</code> when importing a <code>vllm</code> extension</td><td>The installed PyTorch is not the version the wheel was compiled against. The pin is exact for a reason.</td><td>Install the pinned PyTorch from the table in a fresh environment.</td></tr>
<tr><td><code>No matching distribution found for vllm==...</code> or <code>torch==...</code></td><td>Python outside the release's range, glibc older than the wheel tag, or a PyTorch index that has no build of the pinned version (torch @@LTORCH@@ has no cu128 or cu129 build).</td><td>Check the Python / wheel tag column, and the PyTorch index for the pinned version.</td></tr>
</tbody></table></div>

<h2 id="older-driver">What can I do if my NVIDIA driver is older than 580?</h2>
<p>There are five routes. The first three keep the current driver.</p>
<ol>
<li><strong>Pin v@@V12VAR@@ with the CUDA 12.9 wheel.</strong> It needs driver 525.60.13 or newer:
<pre><code>uv pip install "@@U12VAR@@" --extra-index-url https://download.pytorch.org/whl/cu129</code></pre></li>
<li><strong>Use the matching image:</strong> <code>vllm/vllm-openai:v@@V12VAR@@-cu129</code>.</li>
<li><strong>Data center GPUs on an R535 or R570 driver:</strong> NVIDIA's forward-compatibility package lets a CUDA 13.0 runtime run on those two branches. It applies to data center GPUs, select NGC Server Ready RTX cards and Jetson, not to GeForce cards. The vLLM images carry the compatibility libraries, and from v0.17.0 they are opt-in: the install guide enables them with <code>--env VLLM_ENABLE_CUDA_COMPATIBILITY=1</code> on <code>docker run</code>.</li>
<li><strong>Update the driver to R580 or newer</strong> and install v@@LV@@ normally.</li>
<li><strong>Build from source</strong> against a CUDA 12 PyTorch. The install guide covers it; this page does not.</li>
</ol>

<h2 id="method">How was this table checked?</h2>
<ul>
<li><strong>PyTorch pin, Python range, wheel tag:</strong> PyPI metadata of each release, compared with <code>requirements/cuda.txt</code> and <code>pyproject.toml</code> at the release tag. They agree for all @@NREL@@ releases.</li>
<li><strong>CUDA of each wheel:</strong> the <code>DT_NEEDED</code> entries of the compiled extensions inside every published x86_64 wheel: @@NREL@@ PyPI wheels and @@NVAR@@ <code>+cuNNN</code> wheels from GitHub releases. The linked <code>libcudart</code> major matches the build default in <code>vllm/envs.py</code> or <code>setup.py</code> at every tag.</li>
<li><strong>CUDA of PyTorch on PyPI:</strong> the CUDA runtime packages that each pinned torch release depends on in its PyPI metadata.</li>
<li><strong>PyTorch builds per CUDA version:</strong> the file list of the PyTorch wheel index.</li>
<li><strong>Driver floors:</strong> NVIDIA's CUDA Toolkit release notes (12.x: 525 or newer, 13.x: 580 or newer). uv uses 525.60.13 and 580 for the same decision.</li>
<li><strong>GPU targets:</strong> the architecture list in <code>.buildkite/release-pipeline.yaml</code> or <code>docker/Dockerfile</code> at each tag, and PyTorch's CUDA support matrix in its <code>RELEASE.md</code>.</li>
<li><strong>Variant wheels and images:</strong> the GitHub releases API, the per-version indexes on wheels.vllm.ai and the Docker Hub tag list. Releases up to v@@ONLY13V@@ were read on 2026-11-10, v@@LV@@ on @@ASOF@@.</li>
</ul>

<h2 id="limits">What this page does not cover</h2>
<ul>
<li>Nothing was installed or run on a GPU for this page. The commands are assembled from the facts above and follow the forms in vLLM's install guide.</li>
<li>Linux x86_64 only. aarch64 wheels exist from v0.10.2 but were not inspected. Windows and WSL are not covered.</li>
<li>Docker images were not opened. Their CUDA version is taken from the release pipeline at each tag.</li>
<li>Nightly wheels, ROCm, CPU and XPU builds, and source builds are out of scope.</li>
<li>The table is regenerated when a new release appears; the "as of" date at the top says how current it is.</li>
</ul>

<h2 id="faq">Questions</h2>
<dl>
@@FAQ@@
</dl>

<p class="note">Related: <a href="/en/llm-determinism-test/">vLLM batch invariance: what still breaks determinism, and how to test your endpoint</a>; <a href="/en/gguf-arch-min-build-lookup/">GGUF architecture lookup: minimum llama.cpp build and Ollama release</a>; <a href="/en/triton-ptxas-arch-lookup/">"ptxas fatal: Value 'sm_121a' is not defined": which Triton, PyTorch and vLLM release fixes it</a>; <a href="/en/vllm-removed-flags-lookup/">vLLM arguments and environment variables removed by release</a>.</p>

<h2 id="sources">Sources</h2>
<ul>
<li>vLLM repository at each release tag: <a href="https://github.com/vllm-project/vllm">github.com/vllm-project/vllm</a>; <a href="https://github.com/vllm-project/vllm/releases">releases</a>; <a href="https://docs.vllm.ai/en/latest/getting_started/installation/gpu/">GPU install guide</a></li>
<li>PyPI: <a href="https://pypi.org/project/vllm/">vllm</a>, <a href="https://pypi.org/project/torch/">torch</a></li>
<li>PyTorch wheel index: <a href="https://download.pytorch.org/whl/torch/">download.pytorch.org/whl/torch/</a>; CUDA support matrix in <a href="https://github.com/pytorch/pytorch/blob/v2.14.0/RELEASE.md">RELEASE.md</a></li>
<li>NVIDIA: <a href="https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html">CUDA Toolkit 13.0 release notes</a> (driver tables); <a href="https://docs.nvidia.com/deploy/cuda-compatibility/forward-compatibility.html">forward compatibility</a>; <a href="https://developer.nvidia.com/cuda-gpus">GPU compute capability</a> and <a href="https://developer.nvidia.com/cuda-legacy-gpus">legacy GPUs</a></li>
<li>uv: <a href="https://docs.astral.sh/uv/guides/integration/pytorch/">PyTorch guide</a>; driver table and package list in <a href="https://github.com/astral-sh/uv/blob/main/crates/uv-torch/src/backend.rs">uv-torch/src/backend.rs</a></li>
<li>Variant wheels and images: <a href="https://wheels.vllm.ai/@@V12VAR@@/cu129/vllm/">wheels.vllm.ai</a>; <a href="https://hub.docker.com/r/vllm/vllm-openai/tags">Docker Hub tags</a></li>
<li>Reports of the errors above: vLLM forum <a href="https://discuss.vllm.ai/t/install-using-torch-backend-cu129-but-try-to-import-cu13/2601">2601</a>, <a href="https://discuss.vllm.ai/t/how-can-i-use-vllm-with-cuda-12-9/2765">2765</a>, <a href="https://discuss.vllm.ai/t/how-can-we-use-latest-vllm-if-we-are-using-older-drivers-which-only-support-cuda-12/2665">2665</a>, <a href="https://discuss.vllm.ai/t/cuda-12-8-not-working-vllm/2697">2697</a>, <a href="https://discuss.vllm.ai/t/support-for-v100-sm-70-on-vllm-0-20/2605">2605</a>; GitHub issue <a href="https://github.com/vllm-project/vllm/issues/31128">#31128</a></li>
</ul>
</main>
<script type="application/json" id="matrix-data">@@DATA@@</script>
<script>@@JS@@</script>
</body>
</html>
"""

SZ = M["pypi_x86_64_wheel_bytes"]     # {"0.33.0": bytes, "0.34.0": bytes}: sizes quoted in the last bullet
subs = {
    "TITLE": e(TITLE), "DESC": e(DESC), "URL": URL, "H1": e(H1), "LD": LD_JSON, "CSS": CSS.strip(), "JS": JS.strip(), "LIC": LIC,
    "DATA": DATA_JSON, "ROWS": ROWS, "FAQ": FAQ_HTML, "ASOF": AS_OF, "PUB": PUBLISHED, "MOD": MODIFIED, "NREL": str(N_REL), "NVAR": str(N_VARIANT_WHEELS),
    "LV": LATEST["v"], "LDATE": LATEST["date"], "LTORCH": LATEST["torch"],
    "LSIZE": str(round(SZ[LATEST["v"]] / 1e6)), "PSIZE": str(round(SZ[first_cu13_only["v"]] / 1e6)),
    "ONLY13V": first_cu13_only["v"], "ONLY13D": first_cu13_only["date"], "ONLY13T": first_cu13_only["torch"],
    "CU13V": first_cu13["v"], "CU13D": first_cu13["date"],
    "V12VAR": last_cu12_variant["v"], "D12VAR": last_cu12_variant["date"], "T12VAR": cu12_variant["torch"], "U12VAR": cu12_variant["url"],
    "V12PYPI": last_cu12_pypi["v"],
    "CC100V": first_cc100["v"], "CC100D": first_cc100["date"], "CC120V": first_cc120["v"],
    "T128V": first_torch_cu128_pypi["v"], "T128D": first_torch_cu128_pypi["date"], "T128T": first_torch_cu128_pypi["torch"],
    "CU118V": last_cu118["v"], "PY310V": last_py310["v"], "PY39V": last_py39["v"],
}
page = PAGE
for k, v in subs.items():
    page = page.replace("@@" + k + "@@", v)
left = re.findall(r"@@[A-Z0-9_]+@@", page)
assert not left, left
page.encode("ascii")   # raises if anything non-ASCII slipped in

out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
if (out_dir / "matrix.json").resolve() != src.resolve():
    shutil.copyfile(src, out_dir / "matrix.json")
print("index.html", len(page), "bytes;", N_REL, "releases;", N_VARIANT_WHEELS, "variant wheels")
