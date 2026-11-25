#!/usr/bin/env python3
"""Build en/vllm-import-name-version-lookup/ (index.html; vllm.json is copied next to it).

Usage: python3 -I build_page.py <dir with vllm.json> out_dir PUBLISHED MODIFIED chk.json anchors.json hist_ga.json
ASCII only. The facts the prose names are asserted. style.css is shared with .github/llama-args; tool.js is the shared
lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["vllm"].
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK, ANC, GA = json.load(open(sys.argv[5])), json.load(open(sys.argv[6])), json.load(open(sys.argv[7]))
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "vllm.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/vllm-import-name-version-lookup/"
TITLE = "cannot import name from 'vllm': the version that has it"
H1 = "ImportError: cannot import name 'X' from 'vllm...' (GuidedDecodingParams, get_open_port, ChatCompletionRequest, ...): which vLLM releases have it"
DESC = ("vLLM 0.12.0 removed GuidedDecodingParams and moved get_open_port and get_tokenizer; 0.15.0 split entrypoints.openai.protocol. "
        "Paste the error.")
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

for m, n, want in [("sampling_params", "GuidedDecodingParams", ("0.7.0", "0.12.0")), ("sampling_params", "StructuredOutputsParams", ("0.11.0", None)),
                   ("utils", "get_open_port", ("0.3.0", "0.14.0")), ("utils.network_utils", "get_open_port", ("0.12.0", None)),
                   ("utils", "get_ip", ("0.3.0", "0.12.0")), ("utils.network_utils", "get_ip", ("0.12.0", None)),
                   ("utils", "FlexibleArgumentParser", ("0.6.0", "0.12.0")), ("utils.argparse_utils", "FlexibleArgumentParser", ("0.12.0", None)),
                   ("utils", "cdiv", ("0.4.0", "0.12.0")), ("utils.math_utils", "cdiv", ("0.12.0", None)),
                   ("transformers_utils.tokenizer", "get_tokenizer", ("0.2.0", "0.12.0")), ("tokenizers", "get_tokenizer", ("0.12.0", None)),
                   ("entrypoints.openai.protocol", "ChatCompletionRequest", ("0.1.0", "0.15.0")),
                   ("entrypoints.openai.chat_completion.protocol", "ChatCompletionRequest", ("0.15.0", None)),
                   ("entrypoints.openai.protocol", "CompletionRequest", ("0.1.0", "0.15.0")), ("entrypoints.openai.completion.protocol", "CompletionRequest", ("0.15.0", None)),
                   ("entrypoints.openai.engine.protocol", "ErrorResponse", ("0.15.0", "0.29.0")), ("entrypoints.serve.engine.protocol", "ErrorResponse", ("0.29.0", None)),
                   ("worker.worker", "Worker", ("0.1.0", "0.11.0")), ("v1.worker.gpu_worker", "Worker", ("0.7.0", None)),
                   ("", "LLM", ("0.1.0", None)), ("", "SamplingParams", ("0.1.0", None)),
                   ("distributed.utils", "StatelessProcessGroup", ("0.7.0", None)), ("distributed.parallel_state", "get_world_group", ("0.6.0", None)),
                   ("distributed.device_communicators.pynccl", "PyNcclCommunicator", ("0.5.0", None))]:
    assert span(m, n) == want, (m, n, span(m, n))
assert mspan("entrypoints.openai.protocol")[-1][1] == "0.15.0" and mspan("model_executor.guided_decoding")[-1][1] == "0.11.0"
assert mspan("worker")[-1][1] == "0.12.0" and mspan("transformers_utils.tokenizer")[-1][1] == "0.22.0"
assert [t for t in GA["via_getattr"] if "get_open_port" in GA["via_getattr"][t].get("utils", [])] == ["v0.12.0", "v0.13.0"]
assert all(a["wheel"] == a["expected"] == a["data"] for a in ANC) and len(ANC) == 18
d12, d14, d15 = date_of("0.12.0"), date_of("0.14.0"), date_of("0.15.0")
l11, l13, l14 = last_before("0.12.0"), last_before("0.14.0"), last_before("0.15.0")
assert (l11, l13, l14) == ("0.11.2", "0.13.0", "0.14.1"), (l11, l13, l14)

MOVED = [("utils", "get_open_port", "utils.network_utils", "0.14.0 (a deprecated alias in 0.12 and 0.13)"),
         ("utils", "get_ip", "utils.network_utils", "0.12.0"), ("utils", "FlexibleArgumentParser", "utils.argparse_utils", "0.12.0"),
         ("utils", "cdiv", "utils.math_utils", "0.12.0"), ("transformers_utils.tokenizer", "get_tokenizer", "tokenizers", "0.12.0"),
         ("sampling_params", "GuidedDecodingParams", "sampling_params.StructuredOutputsParams (from 0.11.0)", "0.12.0"),
         ("entrypoints.openai.protocol", "ChatCompletionRequest", "entrypoints.openai.chat_completion.protocol", "0.15.0"),
         ("entrypoints.openai.protocol", "CompletionRequest", "entrypoints.openai.completion.protocol", "0.15.0"),
         ("entrypoints.openai.protocol", "ErrorResponse", "entrypoints.serve.engine.protocol (from 0.29.0; entrypoints.openai.engine.protocol in 0.15 to 0.28)", "0.15.0"),
         ("worker.worker", "Worker", "v1.worker.gpu_worker", "0.11.0")]
moved_rows = "\n".join("<tr><td><code>from vllm.%s import %s</code></td><td>%s</td><td><code>vllm.%s</code></td></tr>" % (m, n, gone, e(now)) for m, n, now, gone in MOVED)
HINTS = {
    "vllm:sampling_params:GuidedDecodingParams": "<code>from vllm.sampling_params import StructuredOutputsParams</code> (from 0.11.0) and <code>SamplingParams(structured_outputs=...)</code>. TRL 0.27.0 and later pick the right one by vLLM version.",
    "vllm:utils:get_open_port": "<code>from vllm.utils.network_utils import get_open_port</code> (from 0.12.0). In 0.12 and 0.13 the old import still worked with a DeprecationWarning. TRL 0.28.0 and later pick the right one.",
    "vllm:utils:get_ip": "<code>from vllm.utils.network_utils import get_ip</code> (from 0.12.0).",
    "vllm:utils:FlexibleArgumentParser": "<code>from vllm.utils.argparse_utils import FlexibleArgumentParser</code> (from 0.12.0).",
    "vllm:utils:cdiv": "<code>from vllm.utils.math_utils import cdiv</code> (from 0.12.0).",
    "vllm:transformers_utils.tokenizer:get_tokenizer": "<code>from vllm.tokenizers import get_tokenizer</code> (from 0.12.0).",
    "vllm:entrypoints.openai.protocol:ChatCompletionRequest": "<code>from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest</code> (from 0.15.0).",
    "vllm:entrypoints.openai.protocol:CompletionRequest": "<code>from vllm.entrypoints.openai.completion.protocol import CompletionRequest</code> (from 0.15.0).",
    "vllm:worker.worker:Worker": "the V1 worker, <code>vllm.v1.worker.gpu_worker.Worker</code>; the V0 engine was removed.",
}
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(D["names"][m][n])[-1][1], k
TRL = [("0.16.0 to 0.26.2", "GRPOTrainer, RLOOTrainer, OnlineDPOTrainer and <code>trl vllm-serve</code> import <code>GuidedDecodingParams</code> whenever vLLM is installed", "below 0.12.0"),
       ("0.17.0 to 0.27.2", "<code>trl vllm-serve</code> imports <code>get_open_port</code> from <code>vllm.utils</code>", "below 0.14.0"),
       ("0.27.0 and later", "chooses <code>GuidedDecodingParams</code> or <code>StructuredOutputsParams</code> by vLLM version", "any, for this name"),
       ("0.28.0 and later", "chooses <code>vllm.utils</code> or <code>vllm.utils.network_utils</code> for <code>get_open_port</code>", "any, for this name")]
trl_rows = "\n".join("<tr><td>TRL %s</td><td>%s</td><td>%s</td></tr>" % r for r in TRL)
n_top = len(D["names"][""])
n_top_gone = sum(1 for ri in D["names"][""].values() if pairs(ri)[-1][1])
n_mods = len(D["mods"])
n_mods_gone = sum(1 for ri in D["mods"].values() if pairs(ri)[-1][1])
n_pairs = sum(len(v) for v in D["names"].values())
kb = (src / "vllm.json").stat().st_size // 1024
gone_mod_rows = []
for v in ("0.11.0", "0.12.0", "0.14.0", "0.15.0", "0.22.0"):
    ms = sorted(m for m, ri in D["mods"].items() if pairs(ri)[-1][1] == idx(v) and m.count(".") <= 2 and not m.startswith(("model_executor.models", "_", "benchmarks", "v1.attention.backends", "attention.backends", "model_executor.layers.quantization")))
    gone_mod_rows.append("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td></tr>" % (v, date_of(v), len(ms), ", ".join("<code>vllm.%s</code>" % e(m) for m in ms[:40]) + (" ..." if len(ms) > 40 else "")))

FAQ = [
    ("How do I fix \"cannot import name 'GuidedDecodingParams' from 'vllm.sampling_params'\"?",
     "vLLM 0.12.0 (%s) removed GuidedDecodingParams; %s is the last release with it. Its replacement, StructuredOutputsParams, "
     "exists from 0.11.0. If the import is in TRL (GRPOTrainer, RLOOTrainer, OnlineDPOTrainer or trl vllm-serve), upgrade TRL to "
     "0.27.0 or later, which picks the class by vLLM version, or keep vLLM below 0.12.0." % (d12, l11)),
    ("How do I fix \"cannot import name 'get_open_port' from 'vllm.utils'\"?",
     "Import it from vllm.utils.network_utils (from 0.12.0). vLLM 0.12 and 0.13 still served the old import with a DeprecationWarning; "
     "0.14.0 (%s) removed it. trl vllm-serve before TRL 0.28.0 uses the old import, so upgrade TRL or keep vLLM below 0.14.0." % d14),
    ("Where did vllm.entrypoints.openai.protocol go?",
     "vLLM 0.15.0 (%s) split it by endpoint: ChatCompletionRequest is in vllm.entrypoints.openai.chat_completion.protocol, "
     "CompletionRequest in vllm.entrypoints.openai.completion.protocol, and ErrorResponse in vllm.entrypoints.serve.engine.protocol "
     "from 0.29.0. %s is the last release with the old module." % (d15, l14)),
    ("Why do so many vllm.utils imports fail after upgrading to vLLM 0.12?",
     "0.12.0 split vllm.utils into submodules (network_utils, argparse_utils, math_utils, torch_utils, mem_utils and others) and "
     "moved get_tokenizer to vllm.tokenizers. Only three names kept a deprecated alias. The lookup shows the new module for each name."),
    ("Does this page cover the model and layer modules too?",
     "Yes: every module of vllm from %s to %s, %s module-and-name pairs in %s modules, read at the first release of each minor version." % (R[0][0], LATEST, "{:,}".format(n_pairs), "{:,}".format(n_mods))),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["vLLM", "ImportError", "TRL"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "vLLM import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the vLLM releases in which that name can be imported from that module, the range to pin, and where the name lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from vllm and its modules, by release", "url": URL + "vllm.json", "dateModified": MOD,
     "description": "For %d releases of vLLM (%s to %s): the names importable from every module as release ranges and the life of each module. Read from the source of each release tag." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "vllm.json"}]},
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
EX = [("ImportError: cannot import name 'GuidedDecodingParams' from 'vllm.sampling_params' (/usr/local/lib/python3.12/dist-packages/vllm/sampling_params.py)", "0.12.0", "GuidedDecodingParams"),
      ("from vllm.utils import get_open_port", "0.14.0", "get_open_port"),
      ("from vllm.entrypoints.openai.protocol import ChatCompletionRequest, ErrorResponse", "", "openai.protocol"),
      ("ModuleNotFoundError: No module named 'vllm.model_executor.guided_decoding'", "", "guided_decoding"),
      ("from vllm.utils import FlexibleArgumentParser", "0.12.0", "FlexibleArgumentParser")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/vllm-project/vllm/blob/"
a_rows = "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
    e("vllm." + a["module"] + "." + a["name"]), a["release"], "has it" if a["expected"] else "does not") for a in ANC)

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
<p class="lede"><strong>Most of these errors come from three vLLM releases. 0.12.0 ({d12}) removed <code>GuidedDecodingParams</code> (use <code>StructuredOutputsParams</code>, from 0.11.0) and split <code>vllm.utils</code> into submodules: <code>get_open_port</code> and <code>get_ip</code> are in <code>vllm.utils.network_utils</code>, <code>FlexibleArgumentParser</code> in <code>vllm.utils.argparse_utils</code>, <code>get_tokenizer</code> in <code>vllm.tokenizers</code>. 0.14.0 ({d14}) dropped the last deprecated alias, <code>vllm.utils.get_open_port</code>. 0.15.0 ({d15}) split <code>vllm.entrypoints.openai.protocol</code> by endpoint.</strong> The import is often not in your code but in TRL: TRL before 0.27.0 needs vLLM below 0.12.0, and <code>trl vllm-serve</code> before TRL 0.28.0 needs vLLM below 0.14.0. For any other name, in any module of vLLM, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; vLLM {R[0][0]} to {LATEST}, the first release of each of {N} minor versions &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'GuidedDecodingParams' from 'vllm.sampling_params'"></textarea>
<div class="grid">
<div><label for="v">Your vLLM version (optional; <code>pip show vllm</code>)</label><input id="v" inputmode="decimal" placeholder="for example 0.12.0"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="vllm.json">vllm.json</a> ({kb:,} KB, about a fifth of that over the network); nothing you paste is sent anywhere. Covers {n_top} top-level names and {"{:,}".format(n_pairs)} module-and-name pairs in {"{:,}".format(n_mods)} modules.</p>
</div>

<h2 id="moved">Which vLLM names moved, and where do I import them from now?</h2>
<p><strong>The imports other projects use most, and the release in which the old path stopped working.</strong> The lookup gives the same answer for every other name.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Old import</th><th>Fails from</th><th>Import from now</th></tr></thead>
<tbody>
{moved_rows}
</tbody></table></div>
<p>Names that did not move: <code>from vllm import LLM, SamplingParams</code> (every release), <code>vllm.distributed.utils.StatelessProcessGroup</code> (from 0.7.0), <code>vllm.distributed.parallel_state.get_world_group</code> (from 0.6.0) and <code>vllm.distributed.device_communicators.pynccl.PyNcclCommunicator</code> (from 0.5.0) are importable in {LATEST}.</p>

<h2 id="trl">Which TRL works with which vLLM?</h2>
<p><strong>The TRL release decides which vLLM names are imported. These ranges come from TRL's source at every release from 0.14.0 to 1.18.2.</strong></p>
<div class="tw"><table>
<thead><tr><th>TRL</th><th>What it imports from vLLM</th><th>vLLM that imports</th></tr></thead>
<tbody>
{trl_rows}
</tbody></table></div>
<p>TRL's own <code>vllm</code> extra pins a narrower range (for example <code>vllm==0.10.2</code> in 0.24 and 0.25, <code>&lt;0.12.0</code> in 0.26, <code>&lt;0.34.0</code> in 1.18). A vLLM installed separately, or a newer one in a container image, ignores that pin; then the import fails with the errors on this page.</p>

<h2 id="modules">Which vLLM modules disappeared?</h2>
<p><strong>{n_mods_gone:,} of the {n_mods:,} modules that have existed are gone from {LATEST}; most are model and kernel files.</strong> The modules other code imported most, by release (deeper model, layer and backend files are left out of this table but are in the lookup):</p>
<div class="tw"><table>
<thead><tr><th>Release</th><th>Date (PyPI)</th><th>Modules gone</th><th>Modules</th></tr></thead>
<tbody>
{chr(10).join(gone_mod_rows)}
</tbody></table></div>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>The file in the traceback</strong> tells you whose import it is. <code>trl/trainer/grpo_trainer.py</code> or <code>trl/scripts/vllm_serve.py</code> means TRL; fix it with the TRL table above, not in your code.</li>
<li><strong>A DeprecationWarning</strong> like "vllm.utils.get_open_port is deprecated and will be removed in a future version" (vLLM 0.12 and 0.13) is the last release before the import fails.</li>
<li><strong>Patch releases</strong>: vLLM 0.11.1 and 0.11.2 already shipped some of the 0.12.0 submodules, such as <code>vllm.utils.network_utils</code>. This page reads the first release of each minor version, so it says "from 0.12.0".</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong> A module's names are everything it binds at module level, what <code>from .x import *</code> brings in, and the names a module-level <code>__getattr__</code> serves from a table of strings (the lazy top level of <code>vllm</code>, the deprecated aliases of <code>vllm.utils</code> in 0.12 and 0.13, the lazy config and processor classes of <code>vllm.transformers_utils</code>). Code under <code>if TYPE_CHECKING:</code> is skipped. Dates come from PyPI. The TRL column was read from TRL's release tags the same way.</p>
<p>Checks: (1) each of the {CHK["CHK_TOP"]} top-level names is found as plain text in <code>vllm/__init__.py</code> in every release of its range ({"{:,}".format(CHK["CHK_TOP_PAIRS"])} name-and-release pairs) and not on either side ({CHK["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {"{:,}".format(CHK["CHK_DEFS"])} definitions in {"{:,}".format(CHK["CHK_DEF_FILES"])} file versions; all are among the names read. (3) Against a different source, the wheels on PyPI (read by HTTP range requests), {len(ANC)} release checks agree:</p>
<div class="tw"><table>
<thead><tr><th>Name or module</th><th>Release</th><th>Wheel and data</th></tr></thead>
<tbody>
{a_rows}
</tbody></table></div>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the source; an import can still fail at run time for another reason (a missing CUDA library, a compiled extension built for a different PyTorch).</li>
<li>Only the first release of each minor version was read (and the newest). A change in a patch release is attributed to the next minor.</li>
<li>Names a module serves through a <code>__getattr__</code> that computes them, rather than looking them up in a table, are not counted.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>vllm-project/vllm, release tags v{R[0][0]} to v{LATEST}: every <code>.py</code> file under <a href="{GH}v{LATEST}/vllm/__init__.py">vllm/</a>; deprecated aliases in <a href="{GH}v0.13.0/vllm/utils/__init__.py">vllm/utils/__init__.py at v0.13.0</a>; release dates from <a href="https://pypi.org/project/vllm/#history">PyPI</a>.</li>
<li>huggingface/trl, release tags v0.14.0 to v1.18.2: <a href="https://github.com/huggingface/trl/blob/v0.26.2/trl/trainer/grpo_trainer.py">trainer/grpo_trainer.py</a>, <a href="https://github.com/huggingface/trl/blob/v0.27.2/trl/scripts/vllm_serve.py">scripts/vllm_serve.py</a> and the <code>vllm</code> extra in setup.cfg and pyproject.toml.</li>
<li>Report: <a href="https://github.com/huggingface/trl/issues/4617">TRL issue 4617</a> (GuidedDecodingParams from vllm.sampling_params, TRL 0.25.0).</li>
</ul>
<p>The same data as JSON: <a href="vllm.json">vllm.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/vllm-removed-flags-lookup/">vllm serve "unrecognized arguments"</a> &middot; <a href="/en/vllm-torch-cuda-driver-matrix/">which PyTorch and CUDA each vLLM release needs</a> &middot; <a href="/en/peft-trl-accelerate-import-name-lookup/">"cannot import name ... from 'trl'"</a> &middot; <a href="/en/transformers-import-name-version-lookup/">"... from 'transformers'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["vllm"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "vllm.json", out_dir / "vllm.json")
print("index.html %d bytes | top %d (gone %d) | modules %d (gone %d) | pairs %d" % (len(page), n_top, n_top_gone, n_mods, n_mods_gone, n_pairs), file=sys.stderr)
