#!/usr/bin/env python3
"""Build en/peft-trl-accelerate-import-name-lookup/ (index.html; peft.json, trl.json, accelerate.json are copied next to it).

Usage: python3 -I build_page.py <dir with the three json files> out_dir PUBLISHED MODIFIED chk_peft.json chk_trl.json chk_accelerate.json
ASCII only. Numbers come from the data; the facts the prose names are asserted, so a release that changes one of them
stops the build. style.css is shared with .github/llama-args; tool.js is inlined.
"""
import html, json, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK = {k: json.load(open(f)) for k, f in zip(("peft", "trl", "accelerate"), sys.argv[5:8])}
HERE = Path(__file__).resolve().parent
LIBS = ["peft", "trl", "accelerate"]
D = {l: json.load(open(src / (l + ".json"))) for l in LIBS}
e = html.escape
URL = "https://erimaki-kobo.github.io/en/peft-trl-accelerate-import-name-lookup/"
TITLE = "cannot import name from peft, trl or accelerate: versions"
H1 = "ImportError: cannot import name 'X' from 'peft', 'trl' or 'accelerate' (or their submodules): which releases have it"
DESC = ("DataCollatorForCompletionOnlyLM left trl in 0.20.0, PPOTrainer in 0.29.0; prepare_model_for_int8_training left peft in 0.10.0. "
        "Paste the error for any name.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def pairs(l, ri):
    r = D[l]["ranges"][ri]
    return list(zip(r[::2], r[1::2]))


def rel(l, i):
    return D[l]["releases"][i]


def span(l, m, n):
    a, b = pairs(l, D[l]["names"][m][n])[-1]
    return rel(l, a)[0], (rel(l, b)[0] if b else None)


def date_of(l, v):
    return [r[1] for r in D[l]["releases"] if r[0] == v][0]


def last_before(l, v):
    i = [k for k, r in enumerate(D[l]["releases"]) if r[0] == v][0]
    return rel(l, i - 1)[2]


def idx(l, v):
    return [k for k, r in enumerate(D[l]["releases"]) if r[0] == v][0]


def also_at(l, n, except_m, i):
    out = []
    for m, ns in D[l]["names"].items():
        if m != except_m and n in ns and any(a <= i and (b == 0 or i < b) for a, b in pairs(l, ns[n])):
            out.append(m)
    return sorted(out, key=lambda m: (m.count("."), m))


# ---- facts the prose states ----------------------------------------------------------------------------------------------------
assert span("peft", "", "prepare_model_for_int8_training") == ("0.2.0", "0.10.0") and span("peft", "", "prepare_model_for_kbit_training") == ("0.4.0", None)
assert span("trl", "", "DataCollatorForCompletionOnlyLM") == ("0.5.0", "0.20.0")
assert span("trl", "", "PPOTrainer") == ("0.2.0", "0.29.0") and span("trl", "", "setup_chat_format") == ("0.8.0", "0.26.0")
assert span("trl", "", "clone_chat_template") == ("0.19.0", None) and span("trl", "", "SFTScriptArguments") == ("0.9.3", "0.13.0")
assert span("trl", "", "ScriptArguments")[0] == "0.12.0" and span("trl", "", "SFTTrainer") == ("0.5.0", None)
assert span("accelerate", "utils", "is_npu_available") == ("0.21.0", None) and span("accelerate", "", "PartialState") == ("0.17.0", None)
assert span("accelerate", "utils", "is_tpu_available") == ("0.1.0", "0.28.0") and span("accelerate", "utils", "is_torch_xla_available")[0] == "0.28.0"
assert span("accelerate", "utils", "is_safetensors_available") == ("0.15.0", "0.25.0")
assert "experimental.ppo" in also_at("trl", "PPOTrainer", "", idx("trl", "0.29.0"))
assert span("trl", "experimental.ppo", "PPOTrainer") == ("0.26.0", "1.13.0")
T29 = sorted(n for n, ri in D["trl"]["names"][""].items() if pairs("trl", ri)[-1][1] == idx("trl", "0.29.0"))
assert len(T29) == 33, len(T29)
moved29 = {n: [m for m in also_at("trl", n, "", idx("trl", "0.29.0")) if m.startswith("experimental")] for n in T29}
n_moved29 = sum(1 for v in moved29.values() if v)
L = {l: D[l]["latest"] for l in LIBS}

# replacements quoted from the source of the release before the removal (see Sources)
HINTS = {
    "peft::prepare_model_for_int8_training": "<code>prepare_model_for_kbit_training</code> (from 0.4.0). peft 0.9.0 warned: \"Use prepare_model_for_kbit_training instead.\"",
    "peft:utils:prepare_model_for_int8_training": "<code>from peft import prepare_model_for_kbit_training</code> (from 0.4.0).",
    "trl::DataCollatorForCompletionOnlyLM": "<code>SFTConfig(completion_only_loss=True)</code>. trl 0.19.0 warned: \"To train on completion only, please use the parameter `completion_only_loss` of `SFTConfig` instead.\"",
    "trl:trainer:DataCollatorForCompletionOnlyLM": "<code>SFTConfig(completion_only_loss=True)</code> (see the top-level entry).",
    "trl::setup_chat_format": "<code>clone_chat_template</code> (from 0.19.0). trl 0.25.0 said: \"This function is deprecated and will be removed in version 0.26.0. Please use clone_chat_template instead.\"",
    "trl::SFTScriptArguments": "<code>from trl import ScriptArguments</code> (from 0.12.0). trl 0.12.0 warned: \"Please use `ScriptArguments` instead.\"",
    "trl::DPOScriptArguments": "<code>from trl import ScriptArguments</code> (from 0.12.0).",
    "accelerate:utils:is_tpu_available": "<code>from accelerate.utils import is_torch_xla_available</code> (from 0.28.0). accelerate 0.28.0 warned: \"Please use the `is_torch_xla_available` instead.\"",
    "accelerate:utils:is_safetensors_available": "nothing: from 0.25.0 accelerate requires safetensors, so the check is gone. If the import is in your code, delete it and treat the answer as True.",
}
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(l, D[l]["names"][m][n])[-1][1], k

# ---- tables -------------------------------------------------------------------------------------------------------------------------
vk = lambda v: tuple(int(x) for x in v.split("."))


def gone_table(l, mods):
    rows = []
    by = {}
    for m in mods:
        for n, ri in D[l]["names"][m].items():
            b = pairs(l, ri)[-1][1]
            if b:
                by.setdefault((b, m), []).append(n)
    for (b, m) in sorted(by, key=lambda k: (-k[0], k[1])):
        ns = sorted(by[(b, m)])
        rows.append("<tr><td>%s</td><td>%s</td><td><code>%s</code></td><td>%d</td><td>%s</td></tr>" % (
            rel(l, b)[0], rel(l, b)[1], e(l + ("." + m if m else "")), len(ns), ", ".join("<code>%s</code>" % e(n) for n in ns)))
    return rows, sum(len(v) for v in by.values())


GT = {}
for l, mods in [("trl", [""]), ("peft", ["", "utils"]), ("accelerate", ["", "utils"])]:
    GT[l] = gone_table(l, mods)

exp_rows = []
for n in T29:
    ms = moved29[n]
    exp_rows.append("<tr><td><code>%s</code></td><td>%s</td></tr>" % (n, ", ".join("<code>trl.%s</code>" % m for m in ms) if ms else "not in trl.experimental"))

stale_rows = []
for m, n, key, kind, a, b in sorted(D["trl"]["stale"], key=lambda s: (s[0], s[1])):
    stale_rows.append("<tr><td><code>from %s import %s</code></td><td>%s to %s</td><td>%s</td></tr>" % (
        "trl" + ("." + m if m else ""), n, rel("trl", a)[0], rel("trl", b - 1)[2] if b else L["trl"] + " (still)",
        "the entry points to <code>%s</code>, %s" % (key, "a file that is not there" if kind == "nofile" else "which does not define the name")))
assert len(stale_rows) == 11

stats = {l: (len(D[l]["releases"]), len(D[l]["mods"]), len(D[l]["names"][""]), sum(len(v) for v in D[l]["names"].values()),
             sum(1 for ri in D[l]["names"][""].values() if pairs(l, ri)[-1][1])) for l in LIBS}
cov = "; ".join("%s %s to %s (%d releases)" % (l, rel(l, 0)[0], L[l], stats[l][0]) for l in LIBS)
n_pairs = sum(s[3] for s in stats.values())
kb = sum((src / (l + ".json")).stat().st_size for l in LIBS) // 1024

FAQ = [
    ("How do I fix \"cannot import name 'DataCollatorForCompletionOnlyLM' from 'trl'\"?",
     "trl 0.20.0 (%s) removed it; %s is the last release with it. Either pin pip install \"trl<0.20.0\", or drop the collator and set "
     "SFTConfig(completion_only_loss=True), which is what trl 0.19.0 told you to use." % (date_of("trl", "0.20.0"), last_before("trl", "0.20.0"))),
    ("Where did PPOTrainer, ORPOTrainer and the other trainers go in trl 0.29.0?",
     "trl 0.29.0 (%s) removed %d names from the top level. %d of them were still importable from trl.experimental in 0.29.0, for example "
     "from trl.experimental.ppo import PPOTrainer; the full list is in the table on this page. Later releases removed some of the experimental "
     "modules as well, so the lookup also says whether each one is still there in %s." % (date_of("trl", "0.29.0"), len(T29), n_moved29, L["trl"])),
    ("How do I fix \"cannot import name 'prepare_model_for_int8_training' from 'peft'\"?",
     "Use prepare_model_for_kbit_training, which peft has had since 0.4.0. peft 0.10.0 (%s) removed the int8 name; %s is the last release with it." % (
         date_of("peft", "0.10.0"), last_before("peft", "0.10.0"))),
    ("I import from peft but the error says \"cannot import name 'is_npu_available' from 'accelerate.utils'\". Which package do I upgrade?",
     "accelerate. The library in quotes after \"from\" is the one that lacks the name; the import that fails can sit inside another library. "
     "accelerate.utils has is_npu_available from 0.21.0 (%s), so pip install -U \"accelerate>=0.21.0\"." % date_of("accelerate", "0.21.0")),
    ("Does this page cover names below the top level, like trl.trainer.utils or accelerate.utils?",
     "Yes. Every module of the three libraries is covered: %s module-and-name pairs in all, read from %s." % ("{:,}".format(n_pairs), cov)),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["PEFT", "TRL", "Accelerate", "ImportError", "Hugging Face"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "peft, trl and accelerate import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or an import statement and get the releases of peft, trl or accelerate in which that name can be imported from that module, the range to pin, and where the name lives now.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from peft, trl and accelerate, by release", "url": URL + "trl.json", "dateModified": MOD,
     "description": "For %s: the names importable from every module as release ranges, the life of each module, and the lazy-table entries that cannot resolve. Read from the source of each release tag." % cov,
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + l + ".json"} for l in LIBS]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.pin code{white-space:nowrap}.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\n#res td:first-child{min-width:9em}\n"
js = (HERE / "tool.js").read_text(encoding="ascii")
assert "</script" not in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'DataCollatorForCompletionOnlyLM' from 'trl' (/usr/local/lib/python3.11/site-packages/trl/__init__.py)", "0.20.0", "DataCollatorForCompletionOnlyLM"),
      ("from trl import PPOTrainer, PPOConfig, AutoModelForCausalLMWithValueHead", L["trl"], "PPOTrainer"),
      ("ImportError: cannot import name 'prepare_model_for_int8_training' from 'peft'", "", "prepare_model_for_int8_training"),
      ("ImportError: cannot import name 'is_npu_available' from 'accelerate.utils'", "0.20.3", "is_npu_available"),
      ("cannot import name 'PartialState' from 'accelerate'", "", "PartialState"),
      ("from trl import setup_chat_format", "", "setup_chat_format"),
      ("PPOv2Trainer", "", "a bare name")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/huggingface/"


def gone_section(l, intro):
    rows, n = GT[l]
    return """<div class="tw"><table class="flt">
<thead><tr><th>Release</th><th>Date (PyPI)</th><th>Module</th><th>Names</th><th>Removed names</th></tr></thead>
<tbody>
%s
</tbody></table></div>""" % "\n".join(rows), n


trl_gone, n_trl_gone = gone_section("trl", "")
peft_gone, n_peft_gone = gone_section("peft", "")
acc_gone, n_acc_gone = gone_section("accelerate", "")
chk = lambda k: sum(CHK[l].get(k, 0) for l in LIBS)

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
<p class="lede"><strong>The library named after "from" is too old for the name, or too new because the name was removed.</strong> The common ones: trl removed <code>DataCollatorForCompletionOnlyLM</code> in 0.20.0 (use <code>SFTConfig(completion_only_loss=True)</code>), <code>setup_chat_format</code> in 0.26.0 (use <code>clone_chat_template</code>), and {len(T29)} top-level names in 0.29.0, <code>PPOTrainer</code> and <code>ORPOTrainer</code> among them, most of which were then importable from <code>trl.experimental</code>. peft removed <code>prepare_model_for_int8_training</code> in 0.10.0 (use <code>prepare_model_for_kbit_training</code>). <code>accelerate.utils</code> has <code>is_npu_available</code> only from 0.21.0, which is why an older accelerate breaks <code>import peft</code>. For any other name, in any module of the three libraries, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["trl"]["asof"]} &middot; {cov}, the first release of each minor version &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'DataCollatorForCompletionOnlyLM' from 'trl' (/usr/lib/python3/site-packages/trl/__init__.py)"></textarea>
<div class="grid">
<div><label for="v">Your version of that library (optional; <code>pip show trl</code>)</label><input id="v" inputmode="decimal" placeholder="for example 0.19.1"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="peft.json">peft.json</a>, <a href="trl.json">trl.json</a> and <a href="accelerate.json">accelerate.json</a> ({kb} KB in all, loaded as needed); nothing you paste is sent anywhere. Understands <code>cannot import name</code>, <code>No module named</code>, <code>module ... has no attribute</code>, <code>Failed to import</code> and plain import lines. Covers {"{:,}".format(n_pairs)} module-and-name pairs.</p>
</div>

<h2 id="which">The import is inside another library. Which package do I change?</h2>
<p><strong>The one in quotes after "from".</strong> <code>ImportError: cannot import name 'is_npu_available' from 'accelerate.utils'</code> raised while running <code>from peft import LoraConfig</code> means peft needs a newer accelerate, not that peft is broken: upgrade accelerate to 0.21.0 or later. <code>cannot import name 'PartialState' from 'accelerate'</code> raised from inside transformers means the same for accelerate 0.17.0. Pinning the other library down to match is the other way out, and the lookup gives the range for that too.</p>

<h2 id="trl">What did each trl release remove from <code>from trl import ...</code>?</h2>
<p><strong>{n_trl_gone} of the {stats["trl"][2]} names that <code>from trl import</code> has ever accepted are gone from {L["trl"]}; this is every one, by the release that dropped it.</strong> To keep old code running, pin below that release, for example <code>pip install "trl&lt;0.20.0"</code> for <code>DataCollatorForCompletionOnlyLM</code>.</p>
{trl_gone}

<h2 id="experimental">trl 0.29.0: where did PPOTrainer, ORPOTrainer and the rest go?</h2>
<p><strong>{n_moved29} of the {len(T29)} names removed from the top level in 0.29.0 ({date_of("trl", "0.29.0")}) were importable from a module under <code>trl.experimental</code> in that release.</strong> trl 0.28.0 already pointed there: importing <code>PPOTrainer</code> from the old place warned that it "is now located in <code>trl.experimental</code>". Some experimental modules were removed later (<code>trl.experimental.ppo</code> is gone since 1.13.0); the lookup says which are still there in {L["trl"]}.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Removed from <code>trl</code> in 0.29.0</th><th>Importable in 0.29.0 from</th></tr></thead>
<tbody>
{chr(10).join(exp_rows)}
</tbody></table></div>

<h2 id="peft">What did peft remove?</h2>
<p><strong>peft removes few names: {n_peft_gone} from <code>peft</code> and <code>peft.utils</code> in all.</strong> The one people hit is <code>prepare_model_for_int8_training</code>, gone in 0.10.0 ({date_of("peft", "0.10.0")}).</p>
{peft_gone}

<h2 id="accelerate">What did accelerate remove from <code>accelerate</code> and <code>accelerate.utils</code>?</h2>
<p><strong>{n_acc_gone} names, most of them in 0.8.0, when <code>accelerate.utils</code> became a package and stopped re-exporting what it imported.</strong> The ones that still turn up in errors: <code>is_safetensors_available</code> (gone in 0.25.0) and <code>is_tpu_available</code> (gone from <code>accelerate.utils</code> in 0.28.0; use <code>is_torch_xla_available</code>).</p>
{acc_gone}

<h2 id="stale">Which trl names are listed but cannot be imported?</h2>
<p><strong>{len(stale_rows)} entries of trl's lazy import tables point at a file that is not there or that lacks the name.</strong> The name shows up in <code>dir(trl)</code> and in autocompletion, but importing it fails. For example, <code>trl.trainer</code> in 0.13.0 still lists <code>PPOv2Trainer</code>, but the file behind it was already gone.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Import</th><th>Fails in</th><th>Why</th></tr></thead>
<tbody>
{chr(10).join(stale_rows)}
</tbody></table></div>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong> peft and accelerate import eagerly, so a module's names are everything it binds at module level (classes, functions, assignments, imports). trl replaces its packages with a lazy module from 0.8.0 on; for those, the names are the entries of the lazy table, each followed to the file it names. Code under <code>if TYPE_CHECKING:</code> is skipped. Dates and yanked releases come from PyPI.</p>
<p>Checks, all by a second reading: (1) trl's lazy packages repeat their names as plain imports for type checkers; {chk("CHK_TC_SAME")} of {chk("CHK_TC_MODS")} package-and-release pairs match exactly, and the rest differ by {chk("CHK_TC_DIFF")} names that trl lists in only one of the two places (the lookup follows the table, which is what runs). (2) Each of the {chk("CHK_TOP")} top-level names is found as plain text in <code>__init__.py</code> of every release in its range ({"{:,}".format(chk("CHK_TOP_PAIRS"))} name-and-release pairs), and is not imported there in the release on either side ({chk("CHK_TOP_EDGES")} edges). (3) A regular expression finds {"{:,}".format(chk("CHK_DEFS"))} definitions in {"{:,}".format(chk("CHK_DEF_FILES"))} file versions; all are among the names read. (4) {chk("CHK_ANCHORS")} known facts hold, among them the releases in the public error reports under Sources.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the source, with the optional packages installed.</li>
<li>Only the first release of each minor version was read (and the newest release). A change made in a patch release is attributed to the next minor. Releases on PyPI without a git tag were skipped: trl 0.9.2, so trl's 0.9 line is read at 0.9.3.</li>
<li>The import can still fail for another reason: the file that defines the name imports something your transformers does not have. That shows up as a second <code>cannot import name ... from 'transformers'</code>; see the related page below.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>Release tags of <a href="{GH}peft">huggingface/peft</a> (src/peft), <a href="{GH}trl">huggingface/trl</a> (trl/) and <a href="{GH}accelerate">huggingface/accelerate</a> (src/accelerate); release dates from PyPI.</li>
<li>Messages quoted: <a href="{GH}peft/blob/v0.9.0/src/peft/utils/other.py">peft utils/other.py at 0.9.0</a>, <a href="{GH}trl/blob/v0.19.0/trl/trainer/utils.py">trl trainer/utils.py at 0.19.0</a>, <a href="{GH}trl/blob/v0.25.0/trl/models/utils.py">trl models/utils.py at 0.25.0</a>, <a href="{GH}trl/blob/v0.28.0/trl/trainer/ppo_trainer.py">trl trainer/ppo_trainer.py at 0.28.0</a>, <a href="{GH}trl/blob/v0.12.0/trl/commands/cli_utils.py">trl commands/cli_utils.py at 0.12.0</a>, <a href="{GH}accelerate/blob/v0.28.0/src/accelerate/utils/imports.py">accelerate utils/imports.py at 0.28.0</a>.</li>
<li>Reports of the errors this page answers: <a href="https://discuss.huggingface.co/t/getting-cannot-import-name-is-npu-available-from-accelerate-utils/51177">is_npu_available from accelerate.utils (raised by peft)</a>, <a href="https://discuss.huggingface.co/t/is-safetensors-available-function-can-not-be-imported-from-accelarate-utils/76621">is_safetensors_available from accelerate.utils</a>, <a href="https://discuss.huggingface.co/t/facing-issue-in-importing-pipelines-from-transformers/44605">PartialState from accelerate (raised by transformers)</a>.</li>
</ul>
<p>The same data as JSON: <a href="peft.json">peft.json</a>, <a href="trl.json">trl.json</a>, <a href="accelerate.json">accelerate.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/transformers-import-name-version-lookup/">"cannot import name ... from 'transformers'"</a> &middot; <a href="/en/huggingface-hub-import-name-version-lookup/">"cannot import name ... from 'huggingface_hub'"</a> &middot; <a href="/en/diffusers-import-name-version-lookup/">"cannot import name ... from 'diffusers'"</a> &middot; <a href="/en/peft-trl-args-version-lookup/">"got an unexpected keyword argument": PEFT, TRL and TrainingArguments</a>.</p>
</main>
<script>window.PTA_HINTS = {json.dumps({k: v for k, v in HINTS.items()})};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
for l in LIBS:
    shutil.copyfile(src / (l + ".json"), out_dir / (l + ".json"))
print("index.html %d bytes | trl gone %d (0.29.0: %d, %d to experimental) | peft gone %d | accelerate gone %d | stale %d | pairs %d" % (
    len(page), n_trl_gone, len(T29), n_moved29, n_peft_gone, n_acc_gone, len(stale_rows), n_pairs), file=sys.stderr)
