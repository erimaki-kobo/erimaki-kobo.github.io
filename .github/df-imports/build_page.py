#!/usr/bin/env python3
"""Build en/diffusers-import-name-version-lookup/ (index.html; the JSON files are copied next to it).

Usage: python3 -I build_page.py <dir with data.json and the names files> out_dir PUBLISHED MODIFIED checks.json
ASCII only. Numbers come from the data; the facts the prose names are asserted, so a release that changes one of them
stops the build. style.css is shared with .github/llama-args; tool.js is inlined.
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
checks = json.load(open(sys.argv[5]))
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "data.json"))
CH = {k: json.load(open(src / D["files"][k])) for k in ("core", "pipelines", "modular")}
W = json.load(open(src / D["files"]["where"]))
R, T, N = D["releases"], D["ranges"], len(D["releases"])
LATEST = D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/diffusers-import-name-version-lookup/"
TITLE = "cannot import name from 'diffusers': the version that has it"
H1 = "ImportError: cannot import name 'X' from 'diffusers' (or diffusers.utils, diffusers.models ...): which releases have it"
DESC = ("FluxPipeline needs diffusers 0.30.0; randn_tensor left diffusers.utils in 0.21.0; ONNX pipelines left in 0.43.0. "
        "Paste the error: get the releases and the pin.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def chunk(m):
    head = m.split(".")[0]
    return "pipelines" if head == "pipelines" else "modular" if head == "modular_pipelines" else "core"


def names_of(m):
    return D["top"] if m == "" else CH[chunk(m)].get(m, {})


def pairs(ri):
    r = T[ri]
    return list(zip(r[::2], r[1::2]))


def span(m, n):
    """(first release, release that dropped it or None) of the last range"""
    a, b = pairs(names_of(m)[n])[-1]
    return R[a][0], (R[b][0] if b else None)


def mspan(m):
    a, b = pairs(D["mods"][m])[-1]
    return R[a][0], (R[b][0] if b else None)


def label(m):
    return "diffusers." + m if m else "diffusers"


def date_of(v):
    return [r[1] for r in R if r[0] == v][0]


def last_before(v):
    i = [k for k in range(N) if R[k][0] == v][0]
    return R[i - 1][2]


def range_text(p):
    if p[1] == 0:
        return "from <strong>%s</strong> (%s), still in %s" % (R[p[0]][0], R[p[0]][1], LATEST)
    return "<strong>%s</strong> through <strong>%s</strong>; gone in %s (%s)" % (R[p[0]][0], R[p[1] - 1][2], R[p[1]][0], R[p[1]][1])


def defined_now(n, except_m=None):
    w = W["names"].get(n)
    if not w or w[0] < 0:
        return []
    return [W["modules"][i] for i in w if W["modules"][i] != except_m]


# ---- facts the prose states -------------------------------------------------------------------------------------------
assert span("", "FluxPipeline") == ("0.30.0", None) and span("", "WanPipeline") == ("0.33.0", None)
assert span("", "StableDiffusion3Pipeline") == ("0.29.0", None) and span("", "StableAudioPipeline") == ("0.30.0", None)
assert span("", "StableDiffusionDepth2ImgPipeline") == ("0.10.0", None)
assert span("utils", "randn_tensor") == ("0.12.0", "0.21.0") and span("utils.torch_utils", "randn_tensor")[1] is None
assert span("utils", "HF_HUB_OFFLINE") == ("0.12.0", "0.25.0") and span("utils", "DIFFUSERS_CACHE")[1] == "0.25.0"
for n in ("torch_device", "floats_tensor", "slow"):
    assert span("utils", n)[1] == "0.21.0" and span("utils.testing_utils", n)[1] is None, n
ONNX = sorted(n for n in D["top"] if span("", n)[1] == "0.43.0")
assert ONNX == ["OnnxRuntimeModel", "OnnxStableDiffusionImg2ImgPipeline", "OnnxStableDiffusionInpaintPipeline", "OnnxStableDiffusionPipeline",
                "OnnxStableDiffusionUpscalePipeline", "StableDiffusionOnnxPipeline"], ONNX
FLAX = sorted(n for n in D["top"] if span("", n)[1] == "0.40.0")
assert len(FLAX) == 20 and all(n.startswith("Flax") or n == "is_flax_available" for n in FLAX), FLAX
KD = sorted(n for n in D["top"] if span("", n)[1] == "0.37.0")
assert {"StableDiffusionKDiffusionPipeline", "StableDiffusionXLKDiffusionPipeline", "is_k_diffusion_available"} <= set(KD), KD
assert span("models.embeddings", "PositionNet") == ("0.20.0", "0.26.0") and span("models.embeddings", "GLIGENTextBoundingboxProjection") == ("0.26.0", None)
assert mspan("models.cross_attention") == ("0.12.0", "0.20.0") and span("models.attention_processor", "Attention")[1] is None
assert mspan("pipeline_utils") == ("0.0.2", "0.22.0") and mspan("pipelines.pipeline_utils")[1] is None
assert mspan("modeling_utils")[1] == "0.12.0" and mspan("models.modeling_utils")[1] is None
assert R[D["lazy_from"]][0] == "0.21.0"
st_top = [s for s in D["stale"] if s[0] == "" and s[1] == "OnnxStableDiffusionInpaintPipelineLegacy"]
assert len(st_top) == 1 and (R[st_top[0][4]][0], R[st_top[0][5]][0]) == ("0.25.0", "0.43.0")
assert span("", "OnnxStableDiffusionInpaintPipelineLegacy") == ("0.8.0", "0.25.0")
d43, d40, d37, d21, d25 = date_of("0.43.0"), date_of("0.40.0"), date_of("0.37.0"), date_of("0.21.0"), date_of("0.25.0")
l42, l39, l36, l20 = last_before("0.43.0"), last_before("0.40.0"), last_before("0.37.0"), last_before("0.21.0")

# replacements, each quoted from the source of the last release that had the name (see Sources)
HINTS = {
    "utils:randn_tensor": "<code>from diffusers.utils.torch_utils import randn_tensor</code> (same function; that import works in every release from 0.12.0).",
    "utils:torch_device": "<code>from diffusers.utils.testing_utils import torch_device</code>, or write <code>\"cuda\" if torch.cuda.is_available() else \"cpu\"</code>: it is a test helper.",
    "utils:floats_tensor": "<code>from diffusers.utils.testing_utils import floats_tensor</code> (a test helper).",
    "utils:slow": "<code>from diffusers.utils.testing_utils import slow</code> (a test helper).",
    "utils:HF_HUB_OFFLINE": "<code>from huggingface_hub.constants import HF_HUB_OFFLINE</code>: from 0.25.0 diffusers reads the constant from huggingface_hub.",
    "utils:DIFFUSERS_CACHE": "<code>from huggingface_hub.constants import HF_HUB_CACHE</code>: from 0.25.0 diffusers uses the cache directory of huggingface_hub.",
    "models.embeddings:PositionNet": "<code>GLIGENTextBoundingboxProjection</code> in the same module: the class was renamed in 0.26.0.",
}
GROUPS = [
    ["0.43.0", "^Onnx|^StableDiffusionOnnxPipeline$", "ONNX Runtime support moved out of diffusers. The message in %s: \"Please use Optimum for ONNX Runtime support.\"" % l42],
    ["0.40.0", "^Flax|^is_flax_available$", "nothing in diffusers. The message in %s: \"Flax classes are deprecated and will be removed in Diffusers v0.40.0. We recommend migrating to PyTorch classes or pinning your version of Diffusers.\"" % l39],
    ["0.37.0", "KDiffusion|^is_k_diffusion", "the built-in schedulers, used with the regular Stable Diffusion pipelines. The k-diffusion pipelines carried <code>_last_supported_version = \"0.33.1\"</code> before they were removed."],
]

# ---- table 1: the release that added the names people import most ---------------------------------------------------------
ADDED = """StableDiffusionPipeline StableDiffusionImg2ImgPipeline StableDiffusionInpaintPipeline DPMSolverMultistepScheduler
EulerDiscreteScheduler EulerAncestralDiscreteScheduler StableDiffusionDepth2ImgPipeline UniPCMultistepScheduler ControlNetModel
StableDiffusionControlNetPipeline TextToVideoSDPipeline IFPipeline StableDiffusionXLPipeline KandinskyV22Pipeline AutoPipelineForText2Image
T2IAdapter LCMScheduler AnimateDiffPipeline MotionAdapter PixArtAlphaPipeline StableVideoDiffusionPipeline I2VGenXLPipeline
StableDiffusion3Pipeline SD3Transformer2DModel FlowMatchEulerDiscreteScheduler FluxPipeline FluxTransformer2DModel CogVideoXPipeline
StableAudioPipeline AuraFlowPipeline FluxControlNetPipeline BitsAndBytesConfig FluxFillPipeline HunyuanVideoPipeline SanaPipeline LTXPipeline
GGUFQuantizationConfig TorchAoConfig WanPipeline AutoModel Lumina2Pipeline QuantoConfig HiDreamImagePipeline ChromaPipeline
FluxKontextPipeline QwenImagePipeline ModularPipeline Flux2Pipeline ZImagePipeline""".split()
by_rel = {}
for n in ADDED:
    a, b = span("", n)
    assert b is None and len(pairs(D["top"][n])) == 1, n
    by_rel.setdefault(a, []).append(n)
vk = lambda v: tuple(int(x) for x in v.split("."))
added_rows = "\n".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (v, date_of(v), ", ".join("<code>%s</code>" % n for n in by_rel[v]))
                       for v in sorted(by_rel, key=vk, reverse=True))

# ---- table 2: what each release removed from the top level ------------------------------------------------------------------
GONE = {}
for n in D["top"]:
    ps = pairs(D["top"][n])
    if ps[-1][1]:
        GONE.setdefault(ps[-1][1], []).append(n)
n_top = len(D["top"])
n_now = sum(1 for n in D["top"] if pairs(D["top"][n])[-1][1] == 0)
n_gone = n_top - n_now
assert n_gone == sum(len(v) for v in GONE.values())
NOTES = {"0.43.0": "the ONNX Runtime pipelines and <code>OnnxRuntimeModel</code>. " + GROUPS[0][2].split(". ", 1)[1],
         "0.40.0": "every Flax class. " + GROUPS[1][2].split(". ", 1)[1],
         "0.37.0": "the k-diffusion pipelines and their availability checks",
         "0.25.0": "the name stayed in the lazy table until %s, but the file behind it was removed here (see <a href=\"#stale\">below</a>)" % l42,
         "0.22.0": "the old module <code>diffusers.pipeline_utils</code>; use <code>diffusers.pipelines.pipeline_utils</code>, or import <code>DiffusionPipeline</code> from <code>diffusers</code>",
         "0.12.0": "old top-level modules; the same files live under <code>diffusers.models</code>, <code>diffusers.pipelines</code> and <code>diffusers.utils</code>"}
rows_gone = []
for i in sorted(GONE, reverse=True):
    ns = sorted(GONE[i])
    rows_gone.append("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s%s</td></tr>" % (
        R[i][0], R[i][1], len(ns), ", ".join("<code>%s</code>" % e(n) for n in ns),
        ("<br><span class=\"note\">%s</span>" % NOTES[R[i][0]]) if R[i][0] in NOTES else ""))
back = sorted(n for n in D["top"] if len(pairs(D["top"][n])) > 1 and pairs(D["top"][n])[-1][1] == 0)

# ---- table 3: names and modules that moved -------------------------------------------------------------------------------------
MOVED_NAMES = [("utils", "randn_tensor"), ("utils", "torch_device"), ("utils", "floats_tensor"), ("utils", "HF_HUB_OFFLINE"), ("utils", "DIFFUSERS_CACHE"),
               ("models.embeddings", "PositionNet")]
MOVED_MODS = ["pipeline_utils", "modeling_utils", "models.cross_attention", "models.unet_2d_condition", "models.unet_2d_blocks", "models.transformer_2d",
              "models.autoencoder_kl", "models.vae", "models.controlnet", "models.controlnet_flux", "models.controlnet_sd3",
              "pipelines.controlnet.multicontrolnet", "schedulers.scheduling_karras_ve"]
MOD_NOW = {"pipeline_utils": "<code>diffusers.pipelines.pipeline_utils</code> (the old module said: \"Please import from diffusers.pipelines.pipeline_utils instead.\"), or simply <code>from diffusers import DiffusionPipeline</code>",
           "models.cross_attention": "diffusers.models.attention_processor (<code>CrossAttention</code> is <code>Attention</code> there; the old module said: \"Importing from cross_attention is deprecated. Please import from diffusers.models.attention_processor instead.\")"}
last_i = N - 1


def same_leaf(m):
    """modules of the newest release with the same file name (pipeline packages only for a pipeline module)"""
    leaf = m.split(".")[-1]
    return sorted(k for k in D["mods"] if k != m and k.split(".")[-1] == leaf and pairs(D["mods"][k])[-1][1] == 0
                  and (m.startswith("pipelines.") or not k.startswith("pipelines.")))


moved_rows = []
for m, n in MOVED_NAMES:
    a, b = span(m, n)
    assert b, (m, n)
    moved_rows.append("<tr><td><code>from %s import %s</code></td><td>%s to %s</td><td>%s (%s)</td><td>%s</td></tr>" % (
        label(m), n, a, last_before(b), b, date_of(b), HINTS["%s:%s" % (m, n)]))
for m in MOVED_MODS:
    a, b = mspan(m)
    assert b, m
    if m in MOD_NOW:
        now = MOD_NOW[m]
    else:
        cands = same_leaf(m)
        assert len(cands) == 1, (m, cands)
        now = "<code>%s</code>" % label(cands[0])
    moved_rows.append("<tr><td><code>%s</code> <span class=\"note\">(module)</span></td><td>%s to %s</td><td>%s (%s)</td><td>%s</td></tr>" % (
        label(m), a, last_before(b), b, date_of(b), now))
n_mods_ever = len(D["mods"])
n_mods_now = sum(1 for m in D["mods"] if pairs(D["mods"][m])[-1][1] == 0)
n_mods_gone = n_mods_ever - n_mods_now
gone_by = {}
for m in D["mods"]:
    b = pairs(D["mods"][m])[-1][1]
    if b:
        gone_by[R[b][0]] = gone_by.get(R[b][0], 0) + 1
big = sorted(gone_by.items(), key=lambda kv: -kv[1])[:4]
big_text = ", ".join("%s (%d)" % (v, c) for v, c in sorted(big, key=lambda kv: vk(kv[0])))

# ---- table 4: listed but not importable ------------------------------------------------------------------------------------------
stale_rows = []
for m, n, key, kind, a, b in sorted(D["stale"], key=lambda s: (s[0] != "", s[0], s[1])):
    stale_rows.append("<tr><td><code>from %s import %s</code></td><td>%s to %s</td><td>%s</td></tr>" % (
        label(m), e(n), R[a][0], (R[b - 1][2] if b else LATEST + " (still)"),
        ("the entry goes through <code>%s</code>, which no longer has it" % label(key) if m == "" else
         "the entry points to <code>%s.py</code>, which is not there" % key if kind == "nofile" else
         "<code>%s.py</code> is there but does not provide that name" % key)))
n_stale = len(D["stale"])
n_stale_now = sum(1 for s in D["stale"] if s[5] == 0)

n_pairs = n_top + sum(len(v) for c in CH.values() for v in c.values())
kb = sum((src / f).stat().st_size for f in D["files"].values()) // 1024 + (src / "data.json").stat().st_size // 1024

FAQ = [
    ("Which diffusers version has FluxPipeline?",
     "diffusers 0.30.0 (%s) and every release after it. On an older release, or on a 0.30.0.dev0 build made before the pipeline was merged, "
     "\"from diffusers import FluxPipeline\" fails with ImportError. Upgrade: pip install -U \"diffusers>=0.30.0\"." % date_of("0.30.0")),
    ("How do I fix \"cannot import name 'randn_tensor' from 'diffusers.utils'\"?",
     "Change the import to \"from diffusers.utils.torch_utils import randn_tensor\". diffusers.utils exported randn_tensor from 0.12.0 through %s "
     "and stopped in 0.21.0 (%s); diffusers.utils.torch_utils has had it since 0.12.0, so the new import works on old and new releases. "
     "If the import is inside a package you do not maintain, pin instead: pip install \"diffusers<0.21.0\"." % (l20, d21)),
    ("Why can't I import OnnxStableDiffusionPipeline from diffusers any more?",
     "diffusers 0.43.0 (%s) removed the ONNX Runtime pipelines and OnnxRuntimeModel; %s is the last release that has them. The deprecation "
     "message in %s says: \"Please use Optimum for ONNX Runtime support.\" To keep the old code running: pip install \"diffusers<0.43.0\"." % (d43, l42, l42)),
    ("Which diffusers version removed the Flax classes?",
     "diffusers 0.40.0 (%s) removed all %d Flax names from the top level, FlaxStableDiffusionPipeline and FlaxUNet2DConditionModel included; "
     "%s is the last release that has them. Its message recommends migrating to the PyTorch classes or pinning the version." % (d40, len(FLAX), l39)),
    ("My diffusers is newer than the version the name needs, and the import still fails. Why?",
     "Three usual reasons. Another copy of diffusers is being imported: print diffusers.__version__ and diffusers.__file__ in the same "
     "interpreter. The install is a development build (for example 0.30.0.dev0) made before the name was merged. Or the error names another "
     "package: \"Failed to import diffusers.pipelines... because of the following error: cannot import name ... from 'transformers'\" is about "
     "transformers or huggingface_hub, not diffusers."),
    ("The name in my error is not a pipeline. Does this page cover it?",
     "Yes. The lookup covers every name that every module of diffusers binds, from %s to %s: %d top-level names (%d gone from the newest "
     "release) and %d module-and-name pairs across %d modules, %d of which no longer exist." % (R[0][0], LATEST, n_top, n_gone, n_pairs, n_mods_ever, n_mods_gone)),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["diffusers", "ImportError", "Stable Diffusion", "FLUX"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "mainEntityOfPage": URL, "isBasedOn": URL + "data.json"},
    {"@type": "WebApplication", "name": "diffusers import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the diffusers releases in which that name can be imported from that module, the range to pin, and where the name lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from diffusers and its modules, by release", "url": URL + "data.json", "dateModified": MOD,
     "description": "For %d releases of diffusers (%s to %s): the names importable from diffusers and from each of its %d modules as release "
                    "ranges, the life of each module, and the lazy-table entries that cannot resolve. Read from the source of each release tag." % (N, R[0][0], LATEST, n_mods_ever),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + f} for f in ["data.json"] + sorted(D["files"].values())]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.s.p{color:var(--warn)}.pin code{white-space:nowrap}.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\n#res td:first-child{min-width:9em}\n"
js = (HERE / "tool.js").read_text(encoding="ascii")
assert "</script" not in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'FluxPipeline' from 'diffusers' (/usr/local/lib/python3.11/site-packages/diffusers/__init__.py)", "0.29.2", "FluxPipeline on 0.29.2"),
      ("ImportError: cannot import name 'randn_tensor' from 'diffusers.utils'", "", "randn_tensor"),
      ("from diffusers import OnnxStableDiffusionPipeline, FlaxStableDiffusionPipeline, StableDiffusionKDiffusionPipeline", LATEST, "removed families"),
      ("ModuleNotFoundError: No module named 'diffusers.models.unet_2d_condition'", "", "a module that moved"),
      ("from diffusers.models.embeddings import PositionNet", "", "PositionNet"),
      ("cannot import name 'OnnxStableDiffusionInpaintPipelineLegacy' from 'diffusers'", "0.31.0", "listed but broken"),
      ("retrieve_timesteps", "", "a bare name")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(l)) for q, v, l in EX)
G = "https://github.com/huggingface/diffusers/blob/"

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
<p class="lede"><strong>The error has one of three causes: your diffusers is older than the release that added the name, the name was removed, or it moved to another module.</strong> Added: <code>FluxPipeline</code> needs diffusers 0.30.0, <code>WanPipeline</code> 0.33.0, <code>StableDiffusion3Pipeline</code> 0.29.0. Removed: the ONNX pipelines in 0.43.0 ({d43}; last release with them {l42}), the Flax classes in 0.40.0 ({d40}; last {l39}), the k-diffusion pipelines in 0.37.0 ({d37}; last {l36}). Moved: <code>randn_tensor</code> left <code>diffusers.utils</code> in 0.21.0 ({d21}) and imports from <code>diffusers.utils.torch_utils</code> in every release since 0.12.0. For any other name, in any module of diffusers, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; diffusers {R[0][0]} to {LATEST}, the first release of each of {N} minor versions &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'FluxPipeline' from 'diffusers' (/usr/lib/python3/site-packages/diffusers/__init__.py)"></textarea>
<div class="grid">
<div><label for="v">Your diffusers version (optional; <code>pip show diffusers</code>)</label><input id="v" inputmode="decimal" placeholder="for example 0.31.0"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="data.json">data.json</a> and four more files it loads when needed ({kb} KB in all); nothing you paste is sent anywhere. Understands <code>cannot import name</code>, <code>No module named 'diffusers...'</code>, <code>module diffusers has no attribute</code>, <code>Failed to import diffusers...</code> and plain <code>from diffusers... import ...</code> lines. Covers {n_top} top-level names and {n_pairs} module-and-name pairs in {n_mods_ever} modules.</p>
</div>

<h2 id="added">Which diffusers version added the pipeline, model or scheduler I am importing?</h2>
<p><strong>The table gives the first release that exports each name from the top level; with an older diffusers, <code>from diffusers import &lt;name&gt;</code> raises this ImportError, and upgrading to that release or later fixes it.</strong> All of these are still in {LATEST}.</p>
<div class="tw"><table class="flt">
<thead><tr><th>First release</th><th>Date (PyPI)</th><th>Top-level names it added (a selection)</th></tr></thead>
<tbody>
{added_rows}
</tbody></table></div>
<p class="note">A selection of {len(ADDED)} of the {n_now} names in {LATEST}; the lookup has all of them. A development install such as <code>0.30.0.dev0</code> has only what was merged when it was built, so it can lack a name that the final 0.30.0 has.</p>

<h2 id="removed">What did each diffusers release remove from the top level?</h2>
<p><strong>{n_gone} of the {n_top} names that <code>from diffusers import ...</code> has ever accepted are gone from {LATEST}; this is every one of them, by the release that dropped it.</strong> To keep old code running, pin below that release, for example <code>pip install "diffusers&lt;0.43.0"</code> for the ONNX pipelines.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Release</th><th>Date (PyPI)</th><th>Names</th><th>Gone from the top level</th></tr></thead>
<tbody>
{chr(10).join(rows_gone)}
</tbody></table></div>
<p class="note">Lower-case entries such as <code>pipeline_utils</code> and <code>hub_utils</code> are modules that used to sit directly under <code>diffusers</code>. {("Names that left and came back, and are in " + LATEST + ": " + ", ".join("<code>%s</code>" % n for n in back) + ".") if back else ""}</p>

<h2 id="moved">The name is still in diffusers but my import path fails. Where did it go?</h2>
<p><strong>diffusers has moved files several times, and an import that names the old module fails even though the class still exists.</strong> {n_mods_gone} of the {n_mods_ever} modules that have existed are gone from {LATEST}; the releases that removed or moved the most are {big_text}. The safest import is the shortest one that works: <code>from diffusers import UNet2DConditionModel</code> has worked in every release since 0.2.0, while <code>from diffusers.models.unet_2d_condition import UNet2DConditionModel</code> stopped in 0.29.0.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Old import</th><th>Works in</th><th>Stops in</th><th>Use instead</th></tr></thead>
<tbody>
{chr(10).join(moved_rows)}
</tbody></table></div>
<p class="note">For a module, "use instead" is the module with the same file name in {LATEST}. The lookup does this for any module or name: paste <code>No module named 'diffusers...'</code> or the import line.</p>

<h2 id="stale">Which names does diffusers list but fail to import?</h2>
<p><strong>{n_stale} entries of the lazy import tables point at a file that is gone or at a file that does not define the name; the import fails although the name is in the table, in <code>dir()</code> and in autocompletion.</strong> {n_stale_now} of them are still there in {LATEST}. The best-known one: <code>from diffusers import OnnxStableDiffusionInpaintPipelineLegacy</code> stopped working in 0.25.0, when its file was removed, but the top-level table kept the name until {l42}. With <code>onnxruntime</code> installed the import raises; without it, diffusers hands back a placeholder class that raises when used.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Import</th><th>Fails in</th><th>Why</th></tr></thead>
<tbody>
{chr(10).join(stale_rows)}
</tbody></table></div>
<p class="note">Found by following every table entry to the file it names, in every release. The error is <code>ImportError: cannot import name ...</code> when the file exists, and <code>RuntimeError: Failed to import diffusers... because of the following error (look up to see its traceback)</code> when it does not.</p>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>The module after "from"</strong> matters as much as the name. <code>from 'diffusers'</code> is the top level; <code>from 'diffusers.utils'</code> or a longer path is a module whose contents change more often. Paste the whole line so the lookup uses the right module.</li>
<li><strong>The path in parentheses</strong> is the copy of diffusers that was imported. Check that it is the version you expect: <code>python -c "import diffusers as d; print(d.__version__, d.__file__)"</code>. In a notebook, restart the kernel after upgrading.</li>
<li><strong>"Failed to import diffusers.pipelines... because of the following error"</strong> wraps a second error. If that one names <code>transformers</code> or <code>huggingface_hub</code> (<code>cannot import name 'cached_download' from 'huggingface_hub'</code> is the common one), diffusers is fine and the other package is too new or too old: see the pages linked at the bottom.</li>
<li><strong>No error on import, then "requires the torch library"</strong> (or transformers, onnxruntime, ...) when the class is used: the name exists, and diffusers gave you a placeholder because that backend is not installed. Install the backend; the diffusers version is not the problem.</li>
<li><strong>"Did you mean: ...?"</strong> at the end is Python's spelling suggestion, not advice from diffusers.</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong></p>
<ul>
<li>Up to 0.20.x, <code>diffusers/__init__.py</code> imports its names eagerly, and the names are the ones those import statements bind. From 0.21.0 ({d21}) the top level and most packages below it replace themselves with a lazy module that serves the names of one table (<code>_import_structure</code>). The table is read along the path taken when the optional backends are installed; each entry is then followed to the file it names, down to the definition.</li>
<li>For any other module, the names are everything it binds at module level: classes, functions, assignments and imports. Code under <code>if TYPE_CHECKING:</code> is skipped, because it does not run.</li>
<li>The lazy module's own lookup code (<code>_LazyModule.__getattr__</code>) is checked in every release for rules that look at the spelling of a name; it has none, and the build stops if one appears.</li>
<li>Dates and yanked releases come from PyPI.</li>
</ul>
<p>Checks, all by a second reading: (1) every lazy package repeats its names as plain imports for type checkers; in {checks["CHK_TC_SAME"]} of {checks["CHK_TC_MODS"]} package-and-release pairs that block and our reading are identical, and the other pairs differ by {checks["CHK_TC_DIFF"]} names that upstream lists in only one of the two places (the lookup follows the table, which is what runs). (2) Each of the {checks["CHK_TOP"]} top-level names is found as plain text in <code>__init__.py</code> of every release in its range ({checks["CHK_TOP_PAIRS"]} name-and-release pairs), and is absent from the release on either side of the range ({checks["CHK_TOP_EDGES"]} edges). (3) A regular expression finds {checks["CHK_DEFS"]} class, function and variable definitions in {checks["CHK_DEF_FILES"]} file versions; all are among the names read. (4) The placeholders the top level hands out when a backend is missing are the same names as the real ones, except for the stale entry above. (5) {checks["CHK_ANCHORS"]} known facts hold, among them the releases named in the public error reports under Sources.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the source; it does not mean the class works with your versions of torch or transformers.</li>
<li>Only the first release of each minor version was read. A change made in a patch release is attributed to the next minor.</li>
<li>The answer assumes the optional backends are installed. Without one, a top-level import of a name that needs it still succeeds and returns a placeholder; a few packages below the top level then hand out more placeholders than they have real names.</li>
<li>Importing a name can still fail for another reason: the file that defines it imports something your transformers or huggingface_hub does not have. That shows up as "Failed to import ..." with a second error underneath.</li>
<li>"Instead" is given only where the source of the last release with the name states it, or where the same name is defined elsewhere in {LATEST}. Community pipelines (<code>custom_pipeline=...</code>) and forks are not covered.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>huggingface/diffusers, release tags v{R[0][0]} to v{LATEST}: every <code>.py</code> file under <a href="{G}v{LATEST}/src/diffusers/__init__.py">src/diffusers</a>; the lazy module is in <a href="{G}v{LATEST}/src/diffusers/utils/import_utils.py">utils/import_utils.py</a>.</li>
<li>Messages quoted for replacements: <a href="{G}v{l42}/src/diffusers/pipelines/onnx_utils.py">pipelines/onnx_utils.py at {l42}</a> (ONNX), <a href="{G}v0.39.0/src/diffusers/pipelines/pipeline_flax_utils.py">pipelines/pipeline_flax_utils.py at 0.39.0</a> (Flax), <a href="{G}v0.36.0/src/diffusers/pipelines/stable_diffusion_k_diffusion/pipeline_stable_diffusion_k_diffusion.py">pipeline_stable_diffusion_k_diffusion.py at 0.36.0</a>, <a href="{G}v0.19.0/src/diffusers/models/cross_attention.py">models/cross_attention.py at 0.19.0</a>, <a href="{G}v0.21.0/src/diffusers/pipeline_utils.py">pipeline_utils.py at 0.21.0</a>, <a href="{G}v0.26.0/src/diffusers/models/embeddings.py">models/embeddings.py at 0.26.0</a> (<code>GLIGENTextBoundingboxProjection</code>).</li>
<li>Reports of the error this page answers: <a href="https://huggingface.co/black-forest-labs/FLUX.1-dev/discussions/41">FluxPipeline on a 0.30.0.dev0 build</a>, <a href="https://huggingface.co/stabilityai/stable-diffusion-2-depth/discussions/6">StableDiffusionDepth2ImgPipeline on 0.9.0</a>, <a href="https://huggingface.co/stabilityai/stable-audio-open-1.0/discussions/40">StableAudioPipeline</a>, <a href="https://discuss.huggingface.co/t/cannot-import-wan-pipeline/145370">WanPipeline</a>, <a href="https://discuss.huggingface.co/t/getting-a-peculiar-error-importerror-cannot-import-name-hf-hub-offline-from-diffusers-utils/40262">HF_HUB_OFFLINE from diffusers.utils</a>.</li>
<li>Release dates: <a href="https://pypi.org/project/diffusers/#history">PyPI</a>.</li>
</ul>
<p>The same data as JSON: <a href="data.json">data.json</a>, <a href="names-core.json">names-core.json</a>, <a href="names-pipelines.json">names-pipelines.json</a>, <a href="names-modular.json">names-modular.json</a>, <a href="where.json">where.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/transformers-import-name-version-lookup/">"cannot import name ... from 'transformers'": the releases that have each name</a> &middot; <a href="/en/huggingface-hub-import-name-version-lookup/">"cannot import name 'cached_download' from 'huggingface_hub'"</a> &middot; <a href="/en/peft-trl-args-version-lookup/">"got an unexpected keyword argument": PEFT, TRL and TrainingArguments by version</a>.</p>
</main>
<script>window.DF_HINTS = {json.dumps(HINTS)}; window.DF_GROUPS = {json.dumps(GROUPS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
for f in ["data.json"] + sorted(D["files"].values()):
    if (out_dir / f).resolve() != (src / f).resolve():
        shutil.copyfile(src / f, out_dir / f)
print("index.html %d bytes | top %d, now %d, gone %d | modules %d (gone %d) | pairs %d | stale %d | rows %d + %d + %d + %d" % (
    len(page), n_top, n_now, n_gone, n_mods_ever, n_mods_gone, n_pairs, n_stale, len(by_rel), len(rows_gone), len(moved_rows), len(stale_rows)), file=sys.stderr)
