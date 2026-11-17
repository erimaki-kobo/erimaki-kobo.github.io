#!/usr/bin/env python3
"""Build en/transformers-import-name-version-lookup/ (index.html; data.json is copied next to it).

Usage: python3 -I build_page.py data.json out_dir PUBLISHED MODIFIED checks.json
ASCII only. Numbers in the prose are computed from data.json; the facts the prose names are asserted, so a
release that changes one of them stops the build instead of leaving stale prose. style.css (shared with
.github/llama-args) and tool.js are inlined.
"""
import html, json, re, shutil, sys
from pathlib import Path

data_p, out_dir, PUB, MOD = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]
HERE = Path(__file__).resolve().parent
D = json.load(open(data_p))
R, N = D["releases"], len(D["releases"])
e = html.escape
URL = "https://erimaki-kobo.github.io/en/transformers-import-name-version-lookup/"
TITLE = '"cannot import name" from transformers: Version Lookup'
H1 = "ImportError: cannot import name 'X' from 'transformers': which releases have each name"
DESC = ("Paste the ImportError and see which transformers releases export that name, the release that dropped it, "
        "the version range to pin and what replaced it.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))
LABEL = {"top": "transformers", "utils": "transformers.utils", "file_utils": "transformers.file_utils"}


def pairs(kind, name):
    r = D[kind][name]
    r = r[1:] if kind == "top" else r
    return [(r[i], r[i + 1]) for i in range(0, len(r), 2)]


def alias_at(name, i):
    for s, en, tg in D["alias"].get(name, []):
        if s <= i and (en == 0 or i < en):
            return tg
    return None


def rd(i):
    return "%s (%s)" % (R[i][0], R[i][1])


def range_text(p):
    if p[1] == 0:
        return "from <strong>%s</strong> (%s), still in %s" % (R[p[0]][0], R[p[0]][1], D["latest"])
    return "<strong>%s</strong> through <strong>%s</strong>; gone in %s" % (R[p[0]][0], R[p[1] - 1][2], rd(p[1]))


def span(kind, name):
    """(first release, release it is gone in or None) for a name with one range."""
    ps = pairs(kind, name)
    assert len(ps) == 1, (name, ps)
    return R[ps[0][0]][0], (R[ps[0][1]][0] if ps[0][1] else None)


# ---- replacements, each read from the deprecation message of the last release that had the name ----
HINTS = {
    "top:AdamW": "<code>torch.optim.AdamW</code> (the class's own warning: \"Use the PyTorch implementation torch.optim.AdamW instead\").",
    "top:AutoModelWithLMHead": "<code>AutoModelForCausalLM</code> for causal language models, <code>AutoModelForMaskedLM</code> for masked ones, <code>AutoModelForSeq2SeqLM</code> for encoder-decoder models (the class's own warning).",
    "top:top_k_top_p_filtering": "<code>TopKLogitsWarper</code> and <code>TopPLogitsWarper</code> (its warning: \"scheduled for deletion in v4.39\").",
    "top:Conversation": "the <code>text-generation</code> pipeline with a list of message dicts (the warning of <code>ConversationalPipeline</code>).",
    "top:ConversationalPipeline": "the <code>text-generation</code> pipeline, which accepts lists of message dicts (its own warning).",
    "top:LogitsWarper": "inherit from <code>LogitsProcessor</code>, \"which has the same properties and interface\" (its own warning).",
    "top:OffloadedCache": "<code>DynamicCache(offloading=True)</code> (its own warning).",
    "utils:is_torch_tpu_available": "<code>is_torch_xla_available</code> (its own warning).",
    "top:is_torch_tpu_available": "<code>is_torch_xla_available</code> (its own warning).",
}
assert span("top", "AdamW") == ("2.0.0", "4.50.0") and span("top", "AutoModelWithLMHead") == ("2.0.0", "5.0.0")
assert span("top", "top_k_top_p_filtering")[1] == "4.39.0" and span("top", "Conversation")[1] == "4.42.0"
assert span("top", "LogitsWarper")[1] == "4.49.0" and span("top", "OffloadedCache")[1] == "5.0.0"
AGENTS = ["Agent", "CodeAgent", "ReactAgent", "ReactCodeAgent", "ReactJsonAgent", "Tool", "ToolCollection", "Toolbox", "PipelineTool",
          "load_tool", "tool", "HfApiEngine", "TransformersEngine", "ManagedAgent", "stream_to_gradio", "launch_gradio_demo"]
for n in AGENTS:
    assert span("top", n)[1] == "4.52.1", n
    HINTS["top:" + n] = "the <code>smolagents</code> package (the agents' deprecation message: \"Switch to smolagents instead, with the same functionalities and similar API\")."
GLUE = [n for n in D["top"] if pairs("top", n)[-1][1] and R[pairs("top", n)[-1][1]][0] == "5.20.0"]
assert len(GLUE) == 24 and "glue_convert_examples_to_features" in GLUE and "SquadDataset" in GLUE
# [kind, release the name is gone in, regex on the name, text]
GROUPS = [
    ["top", "5.0.0", "^TF[A-Z_]", "nothing in transformers: v5 removed TensorFlow support, so every <code>TF...</code> name is gone. Use the PyTorch class of the same model, or stay below 5.0."],
    ["top", "5.0.0", "^(Flax[A-Z]|FLAX_)", "nothing in transformers: v5 removed Flax/JAX support, so every <code>Flax...</code> name is gone. Use the PyTorch class of the same model, or stay below 5.0."],
    ["top", "5.0.0", "FeatureExtractor$", "the image processor of the same model (<code>...ImageProcessor</code>); the vision <code>...FeatureExtractor</code> classes were deprecated aliases of them."],
    ["top", "4.41.0", "_ARCHIVE_(LIST|MAP)$", "nothing: the lists of checkpoint names per model were deleted. Code that only printed or iterated them can drop the import; checkpoints are found on the Hub."],
    ["top", "5.20.0", ".", "the Hugging Face Datasets library (the deprecation message: \"preprocessing should be handled with the Hugging Face Datasets library\", pointing to examples/pytorch/text-classification/run_glue.py)."],
]


def gone_list(kind):
    out = {}
    for n in D[kind]:
        for a, b in pairs(kind, n):
            if b and not (kind == "top" and alias_at(n, b)):
                out.setdefault(b, []).append(n)
    return out


GONE = gone_list("top")
five = [i for i in range(N) if R[i][0] == "5.0.0"][0]
g5 = GONE[five]
tf5 = sum(1 for n in g5 if re.match("TF[A-Z_]", n))
flax5 = sum(1 for n in g5 if re.match("Flax[A-Z]|FLAX_", n))
fe5 = sum(1 for n in g5 if n.endswith("FeatureExtractor"))
onnx5 = sum(1 for n in g5 if n.endswith("OnnxConfig"))
assert tf5 > 400 and flax5 > 150 and fe5 >= 25 and onnx5 > 50, (tf5, flax5, fe5, onnx5)
i441 = [i for i in range(N) if R[i][0] == "4.41.0"][0]
arch441 = sum(1 for n in GONE[i441] if re.search("_ARCHIVE_(LIST|MAP)$", n))
assert arch441 > 400
tokfast = sorted(n for n, a in D["alias"].items() if n.endswith("TokenizerFast") and a[-1][1] == 0)
imgfast = sorted(n for n, a in D["alias"].items() if n.endswith("ImageProcessorFast") and a[-1][1] == 0)
assert "BertTokenizerFast" in tokfast and alias_at("BertTokenizerFast", N - 1) == "BertTokenizer"
assert len(imgfast) > 60 and all(R[D["alias"][n][0][0]][0] >= "5" for n in imgfast)
NOTES = {
    "5.0.0": "TensorFlow and Flax support removed: %d <code>TF...</code> and %d <code>Flax...</code> names. Also %d vision <code>...FeatureExtractor</code> classes (use <code>...ImageProcessor</code>), %d <code>...OnnxConfig</code> classes, <code>AutoModelWithLMHead</code>, the summarization, translation and text2text pipelines classes, <code>TRANSFORMERS_CACHE</code>, and deprecated models such as TransfoXL, Deta and EfficientFormer" % (tf5, flax5, fe5, onnx5),
    "4.41.0": "%d constants named <code>..._PRETRAINED_MODEL_ARCHIVE_LIST</code> or <code>..._PRETRAINED_CONFIG_ARCHIVE_MAP</code>; the first agents (<code>HfAgent</code>, <code>LocalAgent</code>, <code>OpenAiAgent</code>)" % arch441,
    "4.45.0": "internal layer classes that had been exported by accident (<code>BertLayer</code>, <code>LongformerSelfAttention</code>, <code>ReformerLayer</code> and others), <code>ForceTokensLogitsProcessor</code>, <code>HfEngine</code>",
    "5.20.0": "the GLUE, SQuAD and XNLI helpers (<code>glue_convert_examples_to_features</code>, <code>SquadDataset</code>, <code>InputExample</code>, <code>DataProcessor</code> ...), <code>DataCollatorForWholeWordMask</code>, <code>DataCollatorForSOP</code>",
    "4.52.1": "the agents framework (<code>Tool</code>, <code>ReactCodeAgent</code>, <code>load_tool</code> ...), moved to the smolagents package",
    "2.11.0": "the first archive-map constants, memory-tracing helpers of the benchmark utilities, some early TF classes",
    "2.2.0": "the scheduler classes (<code>WarmupLinearSchedule</code> and others, replaced by <code>get_linear_schedule_with_warmup</code> and its siblings), per-model <code>load_..._pt_weights_in_tf2</code>",
    "4.56.0": "cache configuration classes (<code>CacheConfig</code>, <code>QuantizedCacheConfig</code> and the cache processors)",
    "4.49.0": "<code>LogitsWarper</code> and the benchmark classes (<code>PyTorchBenchmark</code>, <code>TensorFlowBenchmark</code> and their arguments)",
}
assert "WarmupLinearSchedule" in GONE[[i for i in range(N) if R[i][0] == "2.2.0"][0]] and "get_linear_schedule_with_warmup" in D["top"]
rows_gone = []
for i in sorted(GONE):
    if len(GONE[i]) < 5:
        continue
    note = NOTES.get(R[i][0])
    if note is None:
        note = ", ".join("<code>%s</code>" % e(n) for n in sorted(GONE[i])[:8]) + (" ..." if len(GONE[i]) > 8 else "")
    rows_gone.append("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td></tr>" % (R[i][0], R[i][1], len(GONE[i]), note))
assert {"5.0.0", "4.41.0", "5.20.0", "4.52.1"} <= {R[i][0] for i in GONE if len(GONE[i]) >= 5}
n_small = sum(1 for i in GONE if len(GONE[i]) < 5)
n_small_names = sum(len(GONE[i]) for i in GONE if len(GONE[i]) < 5)

# ---- the names people paste into search engines ----
COMMON = [("top", n) for n in """AdamW AutoModelWithLMHead top_k_top_p_filtering Conversation TFAutoModel TFBertModel FlaxAutoModel
BertTokenizerFast ViTFeatureExtractor SummarizationPipeline TranslationPipeline glue_convert_examples_to_features Tool HfAgent LogitsWarper
HybridCache OffloadedCache MambaCache TRANSFORMERS_CACHE is_torch_tpu_available BERT_PRETRAINED_MODEL_ARCHIVE_LIST WarmupLinearSchedule
pipeline AutoModelForSeq2SeqLM AutoModelForCausalLM Trainer get_scheduler BitsAndBytesConfig LlamaTokenizer TextStreamer
TextIteratorStreamer GenerationMixin AutoImageProcessor AutoProcessor StaticCache EncoderDecoderCache QuantoConfig
AutoModelForImageTextToText""".split()]
COMMON += [("utils", n) for n in "is_tokenizers_available FLAX_WEIGHTS_NAME SAFE_WEIGHTS_NAME torch_int".split() if n in D["utils"]]
COMMON += [("file_utils", n) for n in "_LazyModule cached_path is_torch_available ModelOutput".split() if n in D["file_utils"]]


def hint_for(kind, name, p):
    if not p[1]:
        return ""
    h = HINTS.get("%s:%s" % (kind, name))
    if h:
        return h
    for k, rel, rx, text in GROUPS:
        if k == kind and rel == R[p[1]][0] and re.search(rx, name):
            return text
    return ""


def common_row(kind, name):
    assert name in D[kind], (kind, name)
    ps = pairs(kind, name)
    cell = "; ".join(range_text(p) for p in ps)
    al = alias_at(name, N - 1) if kind == "top" else None
    if al:
        cell += "; from %s on it is in no list but still imports (returns <code>%s</code>)" % (R[D["alias"][name][-1][0]][0], e(al))
    now = ps[-1][1] == 0 or al
    h = hint_for(kind, name, ps[-1]) if not now else ""
    return "<tr><td><code>%s</code><br><span class=\"note\">%s</span></td><td><span class=\"s %s\">%s</span></td><td>%s%s</td></tr>" % (
        e(name), LABEL[kind], "y" if now else "n", "imports" if now else "gone", cell, ("<br>Instead: " + h) if h else "")


common_rows = "\n".join(common_row(k, n) for k, n in COMMON)
assert span("top", "pipeline")[0] == "2.3.0" and span("top", "LlamaTokenizer") == ("4.28.0", None) and span("top", "BitsAndBytesConfig")[0] == "4.27.0"

n_top, n_top_now = len(D["top"]), sum(1 for n in D["top"] if pairs("top", n)[-1][1] == 0)
n_gone = sum(1 for n in D["top"] if pairs("top", n)[-1][1] and not alias_at(n, N - 1))
fu = D["file_utils"]
i418 = [i for i in range(N) if R[i][0] == "4.18.0"][0]
fu_gone_418 = sum(1 for n in fu if any(b == i418 for a, b in pairs("file_utils", n)))
fu_now = sum(1 for n in fu if pairs("file_utils", n)[-1][1] == 0)
ut_now = sum(1 for n in D["utils"] if pairs("utils", n)[-1][1] == 0)
ut_gone5 = sum(1 for n in D["utils"] if any(b == five for a, b in pairs("utils", n)))
assert fu_gone_418 > 100 and D["file_utils_until"] == 0 and D["utils_until"] == 0
lazy, scan, ut_since = R[D["lazy_since"]][0], R[D["scan_since"]][0], R[D["utils_since"]][0]
assert lazy == "4.2.0" and scan == "4.52.1"

FAQ = [
    ("Why do I get \"ImportError: cannot import name ... from 'transformers'\"?",
     "The installed transformers release does not export that name. Either the release is older than the one that added the name, or it is "
     "newer than the last one that had it. The name usually comes from your own code, a tutorial, or another package that was written for a "
     "different transformers release. Install a release inside the range that has the name, or change the import to its replacement."),
    ("Which transformers version removed AdamW?",
     "transformers 4.50.0 (%s). AdamW is importable from transformers 2.0.0 through %s. The class's own deprecation warning names the "
     "replacement: torch.optim.AdamW." % (R[pairs("top", "AdamW")[0][1]][1], R[pairs("top", "AdamW")[0][1] - 1][2])),
    ("Why did TFBertModel, TFAutoModel and the Flax classes disappear?",
     "transformers 5.0.0 (%s) removed TensorFlow and Flax support. %d names starting with TF and %d starting with Flax stopped being "
     "exported in that release. They are importable through %s; with 5.x use the PyTorch class of the same model."
     % (R[five][1], tf5, flax5, R[five - 1][2])),
    ("Does BertTokenizerFast still import in transformers 5?",
     "Yes. From 5.0.0 the name is not in the import lists any more, but the lazy module resolves a name ending in TokenizerFast to the class "
     "without the suffix, so the import returns BertTokenizer. %d tokenizer names and, from 5.4.0, %d image processor names ending in "
     "ImageProcessorFast keep importing this way in %s." % (len(tokfast), len(imgfast), D["latest"])),
    ("Another package fails with this ImportError. What do I pin?",
     "Pin transformers to the range that has the name: at least the first release that exports it and below the release that dropped it, "
     "for example pip install \"transformers>=4.29.0,<4.52.1\" for the agents classes. Then look for a newer release of the other package; "
     "a pin that old also holds back every model added since."),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL, "datePublished": PUB,
     "dateModified": MOD, "inLanguage": "en", "about": ["Hugging Face Transformers", "ImportError", "Python packaging"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "mainEntityOfPage": URL, "isBasedOn": URL + "data.json"},
    {"@type": "WebApplication", "name": "transformers import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or a name and get the transformers releases that export it, the release that dropped it and the range to pin.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from transformers by release", "url": URL + "data.json", "dateModified": MOD,
     "description": "For %d releases of Hugging Face transformers (%s to %s): the names importable from transformers, transformers.utils and "
                    "transformers.file_utils, as release ranges, read from the source of each release tag." % (N, R[0][0], D["latest"]),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "data.json"}},
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
EX = [("ImportError: cannot import name 'AdamW' from 'transformers' (/usr/local/lib/python3.11/dist-packages/transformers/__init__.py)", "", "AdamW error"),
      ("from transformers import TFBertModel, BertTokenizerFast, AutoModelWithLMHead", "5.23.0", "old tutorial on 5.23.0"),
      ("cannot import name 'is_torch_tpu_available' from 'transformers.utils'", "", "transformers.utils"),
      ("from transformers import ReactCodeAgent, Tool, load_tool", "", "agents"),
      ("AutoModelForImageTextToText", "4.44.2", "newer name on an old install")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(l)) for q, v, l in EX)
G = "https://github.com/huggingface/transformers/blob/"

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
<p class="lede"><strong>The installed transformers release does not export that name: it is either older than the release that added it or newer than the last release that had it.</strong> The fix is to install a release inside the range that has the name, or to import the replacement. Paste the error below to get the range for any of the {n_top:,} names that <code>from transformers import ...</code> has resolved between {R[0][0]} and {D["latest"]}: {n_top_now:,} import in {D["latest"]}, and {n_gone:,} are gone ({tf5 + flax5:,} of them are the TensorFlow and Flax classes that 5.0.0 removed).</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; transformers {R[0][0]} to {D["latest"]}, the first release of each of {N} minor versions &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The ImportError line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'AdamW' from 'transformers' (/usr/lib/python3/site-packages/transformers/__init__.py)"></textarea>
<div class="grid">
<div><label for="v">Your transformers version (optional; <code>pip show transformers</code>)</label><input id="v" inputmode="decimal" placeholder="for example 4.57.1"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="data.json">data.json</a> ({Path(data_p).stat().st_size // 1024} KB); nothing you paste is sent anywhere. Covers <code>transformers</code>, <code>transformers.utils</code> and <code>transformers.file_utils</code>.</p>
</div>

<h2 id="common">Which release has the names people ask about most?</h2>
<p><strong>The table gives the releases that export each name and, for the ones that are gone, the replacement named by the library's own deprecation message.</strong> "Through" is the last patch release before the name disappeared.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>In {D["latest"]}</th><th>Releases that have it</th></tr></thead>
<tbody>
{common_rows}
</tbody></table></div>

<h2 id="removed">Which releases removed the most names?</h2>
<p><strong>Two releases account for most of it: 5.0.0 dropped TensorFlow and Flax, and 4.41.0 deleted the per-model lists of checkpoint names.</strong> Counts are names that <code>from transformers import</code> stopped resolving in that release; names that still import through an alias are not counted. {n_small} other releases removed fewer than five names each ({n_small_names} names in total); the lookup above knows them.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Release</th><th>Date (PyPI)</th><th>Names gone</th><th>What they were</th></tr></thead>
<tbody>
{chr(10).join(rows_gone)}
</tbody></table></div>

<h2 id="aliases">Why do BertTokenizerFast and ...ImageProcessorFast still import in 5.x?</h2>
<p><strong>Because the lazy module answers for them even though no list has them.</strong> From 5.0.0, <code>_LazyModule.__getattr__</code> (<a href="{G}v{D["latest"]}/src/transformers/utils/import_utils.py">utils/import_utils.py</a>) resolves a missing name ending in <code>TokenizerFast</code> to the class without the suffix, and tries the table <code>SLOW_TO_FAST_CONVERTERS</code> for tokenizer names whose class was merged into another one. From 5.4.0 it does the same for names ending in <code>ImageProcessorFast</code>, with a deprecation warning. In {D["latest"]}, {len(tokfast)} names ending in <code>TokenizerFast</code> and {len(imgfast)} ending in <code>ImageProcessorFast</code> import this way, and the object you get is the class without the suffix. The lookup reports these as "imports", with the class that is returned. A <code>...TokenizerFast</code> name whose model lost its tokenizer class altogether is not rescued and raises the ImportError.</p>

<h2 id="modules">What about transformers.utils and transformers.file_utils?</h2>
<p><strong><code>transformers.file_utils</code> has been a compatibility shim since 4.18.0, and both modules lost their TensorFlow and Flax helpers in 5.0.0.</strong> Up to 4.17.0, <code>file_utils.py</code> held the helpers themselves; 4.18.0 moved them into <code>transformers/utils/</code> and left a module that re-exports part of them, so {fu_gone_418} names stopped being importable from <code>transformers.file_utils</code> in that one release (most of them are in <code>transformers.utils</code> from then on). {fu_now} names are left in {D["latest"]}. <code>transformers.utils</code> exists as a package from {ut_since} and binds {ut_now} names in {D["latest"]}; 5.0.0 removed {ut_gone5} (the <code>is_tf_available</code> and <code>is_flax_available</code> families, <code>TF2_WEIGHTS_NAME</code>, <code>FLAX_WEIGHTS_NAME</code> and similar). Other packages often import private helpers from these two modules, which is why diffusers, sentence-transformers or a model's remote code can fail right after a transformers upgrade.</p>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>The module after "from"</strong> tells you which table to look in. <code>from 'transformers'</code> is the top level; <code>from 'transformers.utils'</code> and <code>from 'transformers.file_utils'</code> are the two helper modules this page also covers.</li>
<li><strong>The path in parentheses</strong> is the copy of transformers that was imported. If the version there is not the one you thought you installed (a second environment, a user-site copy, a notebook kernel that was not restarted), fix that first: <code>python -c "import transformers; print(transformers.__version__, transformers.__file__)"</code>.</li>
<li><strong>The traceback</strong> tells you who asked for the name. If it is another package, upgrading that package is the lasting fix and pinning transformers is the quick one.</li>
<li><strong>"(unknown location)"</strong> instead of a path, or an error that names a file in your own project, usually means a local file or folder called <code>transformers</code> shadows the library.</li>
<li>A name that <em>does</em> import but fails when used, with a message that asks you to install PyTorch, sentencepiece or another backend, is a different case: the name exists, its backend is missing.</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong></p>
<ul>
<li>{R[0][0]} to {R[D["lazy_since"] - 1][2]}: <code>__init__.py</code> imports everything eagerly, so the names are its <code>from .module import ...</code> statements.</li>
<li>{lazy} and later: the top level is a lazy module that serves the names listed in <code>_import_structure</code>. Those lists are read, without the <code>utils.dummy_*</code> placeholders.</li>
<li>{scan} and later: <code>__init__.py</code> builds the model part of the lists with <code>define_import_structure</code>, from the <code>__all__</code> of every file under <code>models/</code>. Those are read too.</li>
<li>5.x: the three alias rules of <code>_LazyModule.__getattr__</code> described above are applied; which rules a release has is read from that method's code, and the build stops if the method starts looking at name endings it did not look at before.</li>
<li><code>transformers.utils</code> and <code>transformers.file_utils</code>: every name the module binds at module level.</li>
<li>Release dates and the list of yanked releases come from PyPI. Where the <code>.0</code> release of a minor version was yanked (4.14, 4.25, 4.46, 4.52, 4.57, 5.10) the first release that pip installs is used.</li>
</ul>
<p>Checks, all by a second reading rather than by running the library: (1) lazy releases keep a static copy of the lists for type checkers, the imports under <code>if TYPE_CHECKING:</code>; in all CHK_LAZY lazy releases every name of that copy is in our reading, and CHK_SAME of them are identical (the rest have up to CHK_MOST runtime names that upstream forgot to mirror; those do import). (2) <code>__all__</code> was read a second time line by line, the way the library's own <code>fetch__all__</code> does, for CHK_FILES model files of three releases, with no difference. (3) CHK_ANCHORS known facts from release notes and forum threads (for example AdamW gone in 4.50.0, LlamaTokenizer new in 4.28.0, TF classes gone in 5.0.0) all hold.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed. A name that the lists promise but whose module fails to import in some environment would still raise; a name added by a package's own patching is not seen.</li>
<li>Only the first release of each minor version was read. A name that changed in a patch release is attributed to the next minor.</li>
<li>Submodule paths are not covered: <code>from transformers.models.bert import ...</code>, <code>transformers.generation</code>, <code>transformers.modeling_utils</code> and so on. A name that left the top level can still be importable from its submodule.</li>
<li>Releases before 2.0.0 (pytorch-transformers, pytorch-pretrained-bert) are not covered.</li>
<li>"Instead" is given only where the library's own deprecation message names a replacement, or for the whole groups described above. For other names the release notes of the release that dropped it are the place to look.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>huggingface/transformers, release tags v{R[0][0]} to v{D["latest"]}: <a href="{G}v{D["latest"]}/src/transformers/__init__.py">src/transformers/__init__.py</a>, <a href="{G}v{D["latest"]}/src/transformers/utils/__init__.py">utils/__init__.py</a>, <a href="{G}v{D["latest"]}/src/transformers/utils/import_utils.py">utils/import_utils.py</a> (<code>_LazyModule</code>, <code>define_import_structure</code>, <code>fetch__all__</code>), <a href="{G}v{D["latest"]}/src/transformers/convert_slow_tokenizer.py">convert_slow_tokenizer.py</a> (<code>SLOW_TO_FAST_CONVERTERS</code>), <a href="{G}v4.17.0/src/transformers/file_utils.py">file_utils.py at 4.17.0</a> and <a href="{G}v4.18.0/src/transformers/file_utils.py">at 4.18.0</a>.</li>
<li>Deprecation messages quoted for replacements: <a href="{G}v4.49.0/src/transformers/optimization.py">optimization.py at 4.49.0</a> (AdamW), <a href="{G}v4.57.1/src/transformers/models/auto/modeling_auto.py">modeling_auto.py at 4.57.1</a> (AutoModelWithLMHead), <a href="{G}v4.38.0/src/transformers/generation/utils.py">generation/utils.py at 4.38.0</a> (top_k_top_p_filtering), <a href="{G}v4.41.0/src/transformers/pipelines/conversational.py">pipelines/conversational.py at 4.41.0</a>, <a href="{G}v4.51.0/src/transformers/agents/agents.py">agents/agents.py at 4.51.0</a>, <a href="{G}v4.57.1/src/transformers/cache_utils.py">cache_utils.py at 4.57.1</a>, <a href="{G}v5.19.0/src/transformers/data/processors/glue.py">data/processors/glue.py at 5.19.0</a>.</li>
<li><a href="https://pypi.org/project/transformers/#history">PyPI release history of transformers</a> (dates, yanked releases).</li>
<li>Threads with the question this page answers: Hugging Face forum, <a href="https://discuss.huggingface.co/t/how-to-resolve-the-hugging-face-error-importerror-cannot-import-name-is-tokenizers-available-from-transformers-utils/23957">cannot import name 'is_tokenizers_available' from 'transformers.utils'</a>, <a href="https://discuss.huggingface.co/t/importerror-cannot-import-name-get-scheduler-from-transformers/15615">cannot import name 'get_scheduler' from 'transformers'</a>, <a href="https://discuss.huggingface.co/t/getting-errors-while-running-google-collabs-code-attached-to-chapter-3/160340">AdamW in the course notebooks</a>.</li>
</ul>
<p>The same data as JSON: <a href="data.json">data.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/model-arch-min-version/">"does not recognize this architecture": the Transformers, vLLM and llama.cpp version each model needs</a> &middot; <a href="/en/peft-trl-args-version-lookup/">"got an unexpected keyword argument": PEFT, TRL and TrainingArguments by version</a> &middot; <a href="/en/huggingface-hub-import-name-version-lookup/">"cannot import name 'cached_download' from 'huggingface_hub'": the hub releases that have each name</a>.</p>
</main>
<script>window.TF_HINTS = {json.dumps(HINTS)}; window.TF_GROUPS = {json.dumps(GROUPS)};</script>
<script>
{js}</script>
</body>
</html>
"""
checks = json.load(open(sys.argv[5]))       # written by test_data.py
for k in ("CHK_LAZY", "CHK_SAME", "CHK_MOST", "CHK_FILES", "CHK_ANCHORS"):
    assert page.count(k) == 1, k
    page = page.replace(k, format(checks[k], ","))
assert "</script" not in json.dumps(HINTS) + json.dumps(GROUPS)
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
if (out_dir / "data.json").resolve() != Path(data_p).resolve():
    shutil.copyfile(data_p, out_dir / "data.json")
print("index.html %d bytes | names %d, now %d, gone %d | TF %d Flax %d | alias tok %d img %d | rows %d + %d" % (
    len(page), n_top, n_top_now, n_gone, tf5, flax5, len(tokfast), len(imgfast), len(COMMON), len(rows_gone)), file=sys.stderr)
