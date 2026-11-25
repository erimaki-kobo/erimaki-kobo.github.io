#!/usr/bin/env python3
"""Build en/torchvision-import-name-version-lookup/ (index.html; torchvision.json is copied next to it).

Usage: python3 -I build_page.py <dir with torchvision.json> out_dir PUBLISHED MODIFIED chk.json anchors.json torch_pins.json
ASCII only. The facts the prose names are asserted. style.css is shared with .github/llama-args; tool.js is the shared
lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["torchvision"].
"""
import html, json, re, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK, ANC, PINS = (json.load(open(a)) for a in sys.argv[5:8])
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "torchvision.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/torchvision-import-name-version-lookup/"
TITLE = "No module named torchvision.transforms.functional_tensor and more"
H1 = "No module named 'torchvision.transforms.functional_tensor', cannot import name 'read_video' (or any name) from 'torchvision...': which torchvision releases have it"
DESC = ("torchvision 0.17.0 removed transforms.functional_tensor (basicsr, Real-ESRGAN) and 0.26.0 removed io.read_video. "
        "Paste the error; torch pins too.")
assert len(TITLE) <= 66 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))

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

# facts the prose names (anchors.py checks them against the wheels by plain-text search)
assert mspan("transforms.functional_tensor") == [("0.5.0", "0.17.0")] and mspan("transforms.functional_pil") == [("0.7.0", "0.17.0")]
assert last_before("0.17.0") == "0.16.0" and span("transforms.functional", "rgb_to_grayscale") == ("0.8.0", None)
assert span("transforms.functional_tensor", "rgb_to_grayscale")[1] == "0.17.0"
assert span("io", "read_video") == ("0.4.0", "0.26.0") and span("io", "VideoReader") == ("0.8.0", "0.26.0") and mspan("io.video")[-1] == ("0.4.0", "0.26.0")
assert span("io", "write_video")[1] == "0.26.0" and span("io", "decode_jpeg")[1] is None and span("io", "read_image")[1] is None
assert mspan("models.utils") == [("0.3.0", "0.11.1")] and last_before("0.11.1") == "0.10.0"
assert mspan("datapoints") == [("0.15.1", "0.16.0")] and mspan("tv_tensors") == [("0.16.0", None)] and mspan("transforms.v2") == [("0.15.1", None)]
assert span("transforms", "Scale")[1] == "0.12.0" and span("transforms", "RandomSizedCrop")[1] == "0.12.0" and span("datasets", "Kinetics400")[1] == "0.14.0"
assert span("models", "ResNet50_Weights")[0] == "0.13.0" and span("models", "get_model")[0] == "0.14.0"
assert [(R[a][0], R[b][0]) for a, b in pairs(D["mods"]["prototype"])] == [("0.16.0", "0.17.0"), ("0.22.0", "0.23.0")]
assert all(a["wheel"] == a["expected"] == a["data"] for a in ANC) and len(ANC) == 19
assert CHK.get("CHK_FB_SKIPPED", 0) >= 3
d17, d26, d11, d16 = date_of("0.17.0"), date_of("0.26.0"), date_of("0.11.1"), date_of("0.16.0")
pin = lambda v: PINS[v]["torch"][0].replace("torch", "").replace("(", "").replace(")", "").replace(" ", "")
assert pin("0.16.2") == "==2.1.2" and pin("0.25.0") == "==2.10.0" and pin("0.10.1") == "==1.9.1" and pin("0.29.1") == ">=2.14.0" and pin(LATEST) == ">=2.14.0"
assert all(len(p["torch"]) == 1 for p in PINS.values())

# torch pins, one row per minor
key = lambda v: tuple(int(x) for x in v.split("."))
minors = {}
for v in sorted(PINS, key=key):
    minors.setdefault(key(v)[:2], []).append(v)
pin_rows = []
for k in sorted(minors, reverse=True):
    vs = minors[k]
    pin_rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        "%d.%d" % k, ", ".join("<code>%s</code>" % v for v in vs),
        ", ".join(sorted({"<code>torch%s</code>" % pin(v) for v in vs}, key=lambda s: key(re.search(r"(\d+\.\d+\.\d+)", s).group(1)))) ))
pin_rows = "\n".join(pin_rows)

# hints: the name to import instead
HINTS = {}
F_NOW = {n for n, ri in D["names"]["transforms.functional"].items() if not pairs(ri)[-1][1]}
V2F_NOW = {n for n, ri in D["names"].get("transforms.v2.functional", {}).items() if not pairs(ri)[-1][1]}
TV_NOW = {n for n, ri in D["names"]["tv_tensors"].items() if not pairs(ri)[-1][1]}
for old in ("transforms.functional_tensor", "transforms.functional_pil"):
    for n in D["names"][old]:
        if n.startswith("_") or not n[0].islower() or n in ("torch", "math", "warnings", "np", "numbers", "accimage"):
            continue
        if n in F_NOW:
            HINTS["torchvision:%s:%s" % (old, n)] = "<code>from torchvision.transforms.functional import %s</code> (for a %s it runs the same code as before)." % (n, "tensor" if old.endswith("tensor") else "PIL image")
        elif n in V2F_NOW:
            HINTS["torchvision:%s:%s" % (old, n)] = "<code>from torchvision.transforms.v2.functional import %s</code>." % n
for n in D["names"]["datapoints"]:
    if n in TV_NOW and not n.startswith("_"):
        HINTS["torchvision:datapoints:%s" % n] = "<code>from torchvision.tv_tensors import %s</code> (datapoints was renamed tv_tensors in 0.16.0)." % n
HINTS["torchvision::datapoints"] = "<code>from torchvision import tv_tensors</code> (renamed in 0.16.0)."
HINTS["torchvision:models.utils:load_state_dict_from_url"] = "<code>from torch.hub import load_state_dict_from_url</code>."
TC = ("TorchCodec: <code>pip install torchcodec</code>, then <code>from torchcodec.decoders import VideoDecoder</code>. "
      "To keep the old API, pin <code>torchvision&lt;0.26</code> (0.25.0 needs torch 2.10.0).")
for n in ("read_video", "read_video_timestamps", "VideoReader"):
    HINTS["torchvision:io:%s" % n] = TC
HINTS["torchvision:io:write_video"] = "pin <code>torchvision&lt;0.26</code> (0.25.0 needs torch 2.10.0), or write the frames with PyAV."
for old, new in (("Scale", "Resize"), ("RandomSizedCrop", "RandomResizedCrop")):
    assert new in D["names"]["transforms"]
    HINTS["torchvision:transforms:%s" % old] = "<code>from torchvision.transforms import %s</code> (same class, renamed)." % new
HINTS["torchvision:transforms.functional:scale"] = "<code>from torchvision.transforms.functional import resize</code>."
HINTS["torchvision:datasets:Kinetics400"] = "<code>torchvision.datasets.Kinetics(root, frames_per_clip, num_classes=\"400\")</code>."
for old, new in (("ConvertDtype", "ToDtype"), ("ToImageTensor", "ToImage"), ("ToImagePIL", "ToPILImage"),
                 ("ClampBoundingBox", "ClampBoundingBoxes"), ("SanitizeBoundingBox", "SanitizeBoundingBoxes")):
    assert span("transforms.v2", old)[1] == "0.16.0" and span("transforms.v2", new)[1] is None, old
    HINTS["torchvision:transforms.v2:%s" % old] = "<code>from torchvision.transforms.v2 import %s</code> (renamed in 0.16.0)." % new
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(D["names"][m][n])[-1][1], k
assert len(HINTS) > 20, len(HINTS)
n_mods, n_pairs = len(D["mods"]), sum(len(v) for v in D["names"].values())
n_mods_gone = sum(1 for ri in D["mods"].values() if pairs(ri)[-1][1])
kb = (src / "torchvision.json").stat().st_size // 1024

FAQ = [
    ("How do I fix \"No module named 'torchvision.transforms.functional_tensor'\" (basicsr, Real-ESRGAN, GFPGAN)?",
     "torchvision 0.17.0 (%s) removed the module; 0.16.x warned that it would. basicsr 1.4.2, the latest basicsr on PyPI (2022), "
     "still has from torchvision.transforms.functional_tensor import rgb_to_grayscale in basicsr/data/degradations.py, line 8; "
     "Real-ESRGAN 0.3.0 and GFPGAN 1.3.8 require basicsr>=1.4.2. Change that line to from torchvision.transforms.functional import rgb_to_grayscale "
     "(for a tensor it calls the same code), or pin torchvision<0.17 (0.16.2 needs torch 2.1.2)." % d17),
    ("How do I fix \"cannot import name 'read_video' from 'torchvision.io'\"?",
     "torchvision 0.26.0 (%s) removed video decoding: read_video, read_video_timestamps, write_video and VideoReader are gone from "
     "torchvision.io, and so are the modules torchvision.io.video and torchvision.io.video_reader. From 0.28.0 the wheel has a "
     "torchvision/io/video.py again, but it imports a Meta-internal package and fails. Use TorchCodec (pip install torchcodec; "
     "from torchcodec.decoders import VideoDecoder), or pin torchvision<0.26 (0.25.0 needs torch 2.10.0). Image decoding "
     "(read_image, decode_jpeg) is still there." % d26),
    ("How do I fix \"No module named 'torchvision.models.utils'\"?",
     "torchvision 0.11 (%s) removed it; 0.10.1 is the last release with it. Its one useful name was load_state_dict_from_url: "
     "use from torch.hub import load_state_dict_from_url." % d11),
    ("Which torchvision version goes with my torch?",
     "Each torchvision wheel on PyPI pins one torch release exactly: torchvision 0.16.2 requires torch==2.1.2, 0.25.0 requires "
     "torch==2.10.0. pip install torchvision without a version can therefore up- or downgrade torch. From 0.29.1 the pin is "
     "torch>=2.14.0. The table on this page lists every release."),
    ("Where did torchvision.datapoints go?",
     "torchvision 0.16.0 (%s) renamed it torchvision.tv_tensors, and renamed a few v2 transforms (ToImageTensor to ToImage, "
     "ConvertDtype to ToDtype, ClampBoundingBox to ClampBoundingBoxes, SanitizeBoundingBox to SanitizeBoundingBoxes)." % d16),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["torchvision", "ImportError", "ModuleNotFoundError", "PyTorch"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "torchvision import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError, a ModuleNotFoundError or an import statement and get the torchvision releases in which that name can be imported from that module, the range to pin, and what to import instead.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from torchvision, by release", "url": URL + "torchvision.json", "dateModified": MOD,
     "description": "For %d torchvision releases (%s to %s): the names importable from every module as release ranges. Read from the PyPI wheels." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "torchvision.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.pin code{white-space:nowrap}.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\n#res td:first-child{min-width:9em}td code,p code,li code,h1,h2,h3{overflow-wrap:anywhere}main p,main li{overflow-wrap:break-word}\n"
js = (HERE.parent / "pta-imports" / "tool.js").read_text(encoding="ascii")
assert "</script" not in js and "window.LOOKUP_LIBS" in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ModuleNotFoundError: No module named 'torchvision.transforms.functional_tensor'", "0.17.1", "functional_tensor"),
      ("from torchvision.transforms.functional_tensor import rgb_to_grayscale", "", "rgb_to_grayscale"),
      ("ImportError: cannot import name 'read_video' from 'torchvision.io'", "0.26.0", "read_video"),
      ("from torchvision.models.utils import load_state_dict_from_url", "", "models.utils"),
      ("from torchvision import datapoints", "0.16.0", "datapoints")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/pytorch/vision/blob/"
a_rows = "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
    e("torchvision." + a["module"] + ("." + a["name"] if a["name"] else "")), a["release"], "has it" if a["expected"] else "does not") for a in ANC)
hint_kb = max(1, len(json.dumps(HINTS)) // 1024)

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
<p class="lede"><strong>torchvision 0.17.0 ({d17}) removed <code>torchvision.transforms.functional_tensor</code> (0.16.x is the last with it), and 0.26.0 ({d26}) removed video decoding (<code>torchvision.io.read_video</code>, <code>VideoReader</code>).</strong> The first breaks basicsr, and with it Real-ESRGAN and GFPGAN: change <code>from torchvision.transforms.functional_tensor import rgb_to_grayscale</code> to <code>from torchvision.transforms.functional import rgb_to_grayscale</code>, or pin <code>torchvision&lt;0.17</code>. For video, use TorchCodec or pin <code>torchvision&lt;0.26</code>. Each torchvision pins one torch release, so pinning torchvision pins torch too: <a href="#torch">the table below</a> lists every pair. For any other name, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; the first release of every minor, torchvision {R[0][0]} to {LATEST} ({N} releases) &middot; read from the PyPI wheels, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ModuleNotFoundError: No module named 'torchvision.transforms.functional_tensor'"></textarea>
<div class="grid">
<div><label for="v">Your torchvision (optional; <code>pip show torchvision</code>)</label><input id="v" inputmode="decimal" placeholder="for example 0.17.1"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="torchvision.json">torchvision.json</a> ({kb} KB) and {hint_kb} KB of hints in this page; nothing you paste is sent anywhere. Covers {n_pairs:,} module-and-name pairs in {n_mods} modules ({n_mods_gone} of them gone).</p>
</div>

<h2 id="fixes">What do I import instead?</h2>
<div class="tw"><table class="flt">
<thead><tr><th>Fails</th><th>Gone in</th><th>Instead</th></tr></thead>
<tbody>
<tr><td><code>torchvision.transforms.functional_tensor</code>, <code>functional_pil</code></td><td>0.17.0</td><td><code>torchvision.transforms.functional</code> (or <code>transforms.v2.functional</code>)</td></tr>
<tr><td><code>torchvision.io.read_video</code>, <code>read_video_timestamps</code>, <code>write_video</code>, <code>VideoReader</code></td><td>0.26.0</td><td>TorchCodec (<code>torchcodec.decoders.VideoDecoder</code>), or pin <code>torchvision&lt;0.26</code></td></tr>
<tr><td><code>torchvision.models.utils.load_state_dict_from_url</code></td><td>0.11</td><td><code>torch.hub.load_state_dict_from_url</code></td></tr>
<tr><td><code>torchvision.datapoints</code></td><td>0.16.0</td><td><code>torchvision.tv_tensors</code></td></tr>
<tr><td><code>transforms.v2.ToImageTensor</code>, <code>ConvertDtype</code></td><td>0.16.0</td><td><code>ToImage</code>, <code>ToDtype</code></td></tr>
<tr><td><code>transforms.Scale</code>, <code>RandomSizedCrop</code></td><td>0.12.0</td><td><code>Resize</code>, <code>RandomResizedCrop</code></td></tr>
<tr><td><code>datasets.Kinetics400</code></td><td>0.14.0</td><td><code>datasets.Kinetics(..., num_classes="400")</code></td></tr>
</tbody></table></div>
<p>torchvision 0.11.0 and 0.15.0 were yanked from PyPI, so the first releases of those minors here are 0.11.1 and 0.15.1. The 0.16.0 and 0.22.0 wheels also carry a <code>torchvision.prototype</code> package that the other releases do not.</p>

<h2 id="torch">Which torchvision goes with my torch?</h2>
<p><strong>Every torchvision wheel on PyPI requires one exact torch release, so <code>pip install torchvision</code> without a version can change your torch. From 0.29.1 the requirement is <code>torch&gt;=2.14.0</code>.</strong> Read from the <code>Requires-Dist</code> line of each wheel's metadata (Linux x86_64):</p>
<div class="tw"><table>
<thead><tr><th>Minor</th><th>torchvision releases</th><th>Requires</th></tr></thead>
<tbody>
{pin_rows}
</tbody></table></div>
<p>To pin both, write the pair from the table, for example <code>pip install "torch==2.1.2" "torchvision==0.16.2"</code>.</p>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the Python files of the first release of every minor on PyPI, plus the latest, read from the Linux x86_64 wheels by HTTP range requests and parsed with Python's <code>ast</code> module.</strong> The wheels and the git tags of pytorch/vision agree except for the generated <code>version.py</code> and the <code>prototype</code> package noted above. A module's names are everything it binds at module level and what <code>from .x import *</code> brings in. From 0.26.0, <code>torchvision/io/__init__.py</code> imports the video API from <code>pytorch.vision.fb</code>, a Meta-internal package, inside <code>try: ... except ImportError: pass</code>; that package is not on PyPI, so those names are counted as absent, and <code>torchvision.io.video</code> from 0.28.0, which imports it unconditionally, is counted as not importable.</p>
<p>Checks: (1) the top-level names are found as plain text in <code>torchvision/__init__.py</code> in every release of their range ({CHK["CHK_TOP_PAIRS"]:,} name-and-release pairs) and are not bound on either side ({CHK["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {CHK["CHK_DEFS"]:,} definitions in {CHK["CHK_DEF_FILES"]:,} file versions; all are among the names read. (3) {len(ANC)} release checks against the wheels by plain-text search agree:</p>
<div class="tw"><table>
<thead><tr><th>Module or name</th><th>Release</th><th>Wheel and data</th></tr></thead>
<tbody>
{a_rows}
</tbody></table></div>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the Python files of the wheel; an operator that needs the compiled extension (<code>torchvision.ops.nms</code> on a build without it) can still fail at call time.</li>
<li>Patch releases are not read: a name added or removed in x.y.1 shows up at the next minor. torchvision before {R[0][0]} is not covered.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The torchvision wheels on <a href="https://pypi.org/project/torchvision/#history">PyPI</a> (file names and sha256 in the build notes), which also give the release dates and the torch requirements.</li>
<li>pytorch/vision: <a href="{GH}v0.16.0/torchvision/transforms/functional_tensor.py">transforms/functional_tensor.py at v0.16.0</a> (the removal warning), <a href="{GH}v0.25.0/torchvision/io/video.py">io/video.py at v0.25.0</a> (the TorchCodec notice), <a href="{GH}v0.26.0/torchvision/io/__init__.py">io/__init__.py at v0.26.0</a>.</li>
<li><a href="https://pypi.org/project/basicsr/1.4.2/#files">basicsr 1.4.2</a> on PyPI (basicsr/data/degradations.py in the sdist) and <a href="https://github.com/pytorch/torchcodec">pytorch/torchcodec</a>.</li>
</ul>
<p>The same data as JSON: <a href="torchvision.json">torchvision.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/triton-import-name-version-lookup/">"No module named 'triton.ops'"</a> &middot; <a href="/en/flash-attn-import-name-version-lookup/">"... from 'flash_attn'"</a> &middot; <a href="/en/transformers-import-name-version-lookup/">"... from 'transformers'"</a> &middot; <a href="/en/timm-import-name-version-lookup/">"... from 'timm.models.layers'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["torchvision"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "torchvision.json", out_dir / "torchvision.json")
print("index.html %d bytes | hints %d | modules %d (gone %d) | pairs %d" % (len(page), len(HINTS), n_mods, n_mods_gone, n_pairs), file=sys.stderr)
