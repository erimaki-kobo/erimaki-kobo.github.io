#!/usr/bin/env python3
"""Build /en/peft-trl-args-version-lookup/index.html.
usage: python3 -I build_page.py args_hist.json OUT_DIR PUBLISHED MODIFIED
Every release number in the prose is taken from args_hist.json or asserted against it."""
import html, json, os, re, sys

D = json.load(open(sys.argv[1]))
OUT, PUB, MOD = sys.argv[2:5]
HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://erimaki-kobo.github.io/en/peft-trl-args-version-lookup/"
LIBS = {k: D[k] for k in ("peft", "transformers", "trl")}
NAME = {"peft": "PEFT", "transformers": "Transformers", "trl": "TRL"}
e = lambda s: html.escape(str(s), quote=True)
c = lambda s: "<code>%s</code>" % e(s)


def rng(lib, cls, arg):
    L = LIBS[lib]
    return [(L["tags"][a], L["tags"][b]) for a, b in L["classes"][cls]["p"][arg]]
def first(lib, cls, arg): return rng(lib, cls, arg)[0][0]
def last(lib, cls, arg): return rng(lib, cls, arg)[-1][1]
def date(lib, tag): return LIBS[lib]["dates"][LIBS[lib]["tags"].index(tag)]
def nxt(lib, tag): return LIBS[lib]["tags"][LIBS[lib]["tags"].index(tag) + 1]
def latest(lib): return LIBS[lib]["tags"][-1]
def bare(tag): return tag[1:]
def alias(lib, cls, arg):
    L = LIBS[lib]
    for k, r in L["classes"][cls]["alias"].items():
        old, new = k.split(">")
        if old == arg:
            return new, L["tags"][r[0][0]], L["tags"][r[-1][1]]
    return None

# ---- curated replacements. (library, classes, arguments, claimed last release, html, [(lib, class, arg, claimed first release)]) ----
HV = [
 ("peft", ["LoraConfig"], ["enable_lora", "merge_weights"], "v0.2.0", "Delete the key; no later PEFT has it.", []),
 ("transformers", ["TrainingArguments"], ["evaluation_strategy"], "v4.50.3", "Rename it to <code>eval_strategy</code> (from v4.41.0).", [("transformers", "TrainingArguments", "eval_strategy", "v4.41.0")]),
 ("transformers", ["TrainingArguments"], ["dispatch_batches", "split_batches"], "v4.50.3", "Pass it inside <code>accelerator_config</code>, e.g. <code>accelerator_config={\"split_batches\": True}</code> (from v4.38.0).", [("transformers", "TrainingArguments", "accelerator_config", "v4.38.0")]),
 ("transformers", ["TrainingArguments"], ["no_cuda"], "v4.57.6", "Use <code>use_cpu</code> (from v4.32.0).", [("transformers", "TrainingArguments", "use_cpu", "v4.32.0")]),
 ("transformers", ["TrainingArguments"], ["use_mps_device"], "v4.57.6", "Delete it; the <code>mps</code> device is used automatically when available.", []),
 ("transformers", ["TrainingArguments"], ["per_gpu_train_batch_size", "per_gpu_eval_batch_size"], "v4.57.6", "Use <code>per_device_train_batch_size</code> / <code>per_device_eval_batch_size</code>.", [("transformers", "TrainingArguments", "per_device_train_batch_size", "v4.0.0")]),
 ("transformers", ["TrainingArguments"], ["push_to_hub_model_id", "push_to_hub_organization"], "v4.57.6", "Use <code>hub_model_id</code> with the full repository name (from v4.11.0).", [("transformers", "TrainingArguments", "hub_model_id", "v4.11.0")]),
 ("transformers", ["TrainingArguments"], ["push_to_hub_token"], "v4.57.6", "Use <code>hub_token</code> (from v4.11.0).", [("transformers", "TrainingArguments", "hub_token", "v4.11.0")]),
 ("transformers", ["TrainingArguments"], ["torchdynamo"], "v4.57.6", "Use <code>torch_compile_backend</code> (from v4.26.0).", [("transformers", "TrainingArguments", "torch_compile_backend", "v4.26.0")]),
 ("transformers", ["TrainingArguments"], ["fsdp_min_num_params", "fsdp_transformer_layer_cls_to_wrap"], "v4.57.6", "Put it in <code>fsdp_config</code> (from v4.27.0).", [("transformers", "TrainingArguments", "fsdp_config", "v4.27.0")]),
 ("transformers", ["TrainingArguments"], ["adafactor"], "v4.57.6", "Use <code>optim=\"adafactor\"</code> (<code>optim</code> from v4.16.0).", [("transformers", "TrainingArguments", "optim", "v4.16.0")]),
 ("transformers", ["TrainingArguments"], ["include_inputs_for_metrics"], "v4.57.6", "Use <code>include_for_metrics=[\"inputs\"]</code> (from v4.46.0).", [("transformers", "TrainingArguments", "include_for_metrics", "v4.46.0")]),
 ("transformers", ["TrainingArguments"], ["fp16_backend", "half_precision_backend"], "v4.57.6", "<code>fp16_backend</code> was first renamed to <code>half_precision_backend</code> (v4.13.0); v5.0.0 removed both. Delete it.", []),
 ("transformers", ["TrainingArguments"], ["group_by_length"], "v5.1.0", "Use <code>train_sampling_strategy=\"group_by_length\"</code> (from v5.2.0).", [("transformers", "TrainingArguments", "train_sampling_strategy", "v5.2.0")]),
 ("transformers", ["TrainingArguments"], ["warmup_ratio"], "v5.14.1", "Use <code>warmup_steps</code> with a float below 1, which is read as a ratio of the total steps.", [("transformers", "TrainingArguments", "warmup_steps", "v4.0.0")]),
 ("transformers", ["TrainingArguments"], ["logging_dir"], "v5.14.1", "Set the environment variable <code>TENSORBOARD_LOGGING_DIR</code> instead.", []),
 ("transformers", ["Trainer", "Seq2SeqTrainer"], ["tokenizer"], "v4.45.2", "Use <code>processing_class</code> (from v4.46.0).", [("transformers", "Trainer", "processing_class", "v4.46.0")]),
 ("trl", ["SFTTrainer", "DPOTrainer"], ["tokenizer"], "v0.11.4", "Use <code>processing_class</code> (from v0.12.0).", [("trl", "SFTTrainer", "processing_class", "v0.12.0"), ("trl", "DPOTrainer", "processing_class", "v0.12.0")]),
 ("trl", ["SFTTrainer"], ["dataset_text_field", "max_seq_length", "packing", "dataset_num_proc", "dataset_batch_size", "neftune_noise_alpha", "eval_packing", "dataset_kwargs"], "v0.12.2",
  "It is no longer a trainer argument. Set it on <code>SFTConfig</code> and pass that as <code>args</code> (<code>SFTConfig</code> exists from v0.9.3).", [("trl", "SFTConfig", "dataset_text_field", "v0.9.3"), ("trl", "SFTConfig", "packing", "v0.9.3")]),
 ("trl", ["SFTConfig"], ["max_seq_length"], "v0.19.1", "Rename it to <code>max_length</code> (from v0.16.0).", [("trl", "SFTConfig", "max_length", "v0.16.0")]),
 ("trl", ["DPOTrainer"], ["beta", "max_length", "max_prompt_length", "max_target_length", "loss_type", "label_smoothing", "generate_during_eval", "precompute_ref_log_probs"], "v0.12.2",
  "It is no longer a trainer argument. Set it on <code>DPOConfig</code> (from v0.9.3) if that release still has it.", [("trl", "DPOConfig", "beta", "v0.9.3")]),
 ("trl", ["DPOConfig"], ["max_prompt_length", "max_completion_length"], "v0.28.0", "Removed in v0.29.0. <code>max_length</code> still limits the whole tokenized sequence; filter or shorten long prompts in the dataset.", [("trl", "DPOConfig", "max_length", "v0.9.3")]),
 ("trl", ["DPOConfig"], ["max_target_length"], "v0.13.0", "It became <code>max_completion_length</code> (v0.11.0), which was removed after v0.28.0.", [("trl", "DPOConfig", "max_completion_length", "v0.11.0")]),
]
hints = {}
for lib, classes, args, lst, txt, deps in HV:
    for cl in classes:
        for a in args:
            got = last(lib, cl, a)
            assert got == lst, (lib, cl, a, got, lst)
            assert got != latest(lib), (cl, a, "is still current")
            hints.setdefault(cl, {})[a] = txt
    for dl, dc, da, since in deps:
        assert first(dl, dc, da) == since, (dc, da, first(dl, dc, da), since)
        assert last(dl, dc, da) == latest(dl) or (dc, da) == ("DPOConfig", "max_completion_length"), (dc, da, "replacement is gone too")
# aliases quoted in the prose
assert alias("transformers", "Trainer", "tokenizer") == ("processing_class", "v4.46.0", "v4.57.6")
assert alias("trl", "SFTTrainer", "tokenizer") == ("processing_class", "v0.12.0", "v0.15.2")
FWD = D["peft_forward"]
assert FWD == "v0.14.0", FWD
PREV_FWD = LIBS["peft"]["tags"][LIBS["peft"]["tags"].index(FWD) - 1]
assert first("peft", "LoraConfig", "peft_version") == "v0.18.0"

LC = LIBS["peft"]["classes"]["LoraConfig"]["p"]
PT, TT, RT = (LIBS[k]["tags"] for k in ("peft", "transformers", "trl"))
MAIN = ["LoraConfig", "TrainingArguments", "SFTConfig", "SFTTrainer", "Trainer", "DPOConfig", "GRPOConfig", "DPOTrainer", "Seq2SeqTrainingArguments", "PeftConfig"]
for m in MAIN: assert any(m in LIBS[k]["classes"] for k in LIBS), m


TA_NOW = {n for n, r in LIBS["transformers"]["classes"]["TrainingArguments"]["p"].items() if r[-1][1] == len(TT) - 1}


def gone(lib, cls):
    L = LIBS[lib]; lastI = len(L["tags"]) - 1
    C = L["classes"][cls]
    out = []
    for n, r in C["p"].items():
        end = r[-1][1]
        for k, ar in C["alias"].items():
            if k.split(">")[0] == n: end = max(end, ar[-1][1])
        if end != lastI and not n.startswith("_"):
            # a TRL config that stopped re-declaring a TrainingArguments field still inherits it: not removed
            if "TrainingArguments" in C["ext"] and n in TA_NOW:
                continue
            out.append((n, r, end))
    out.sort(key=lambda x: (x[2], x[0]))
    return out


def gone_rows(lib, cls, label=False):
    L = LIBS[lib]; rows = []
    for n, r, end in gone(lib, cls):
        al = alias(lib, cls, n)
        lastcell = L["tags"][r[-1][1]] + (" <span class=\"note\">(alias until %s)</span>" % al[2] if al else "")
        h = hints.get(cls, {}).get(n, "")
        rows.append("<tr><td>%s%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            (e(cls) + " " if label else ""), c(n), L["tags"][r[0][0]], lastcell, L["tags"][end + 1], h or "&ndash;"))
    return "\n".join(rows)


# PEFT: every LoraConfig key, newest first
lora_rows = []
for n, r in sorted(LC.items(), key=lambda kv: (-kv[1][0][0], kv[0])):
    a, b = PT[r[0][0]], PT[r[-1][1]]
    cur = b == PT[-1]
    lora_rows.append("<tr><td>%s</td><td><strong>%s</strong> <span class=\"note\">%s</span></td><td>%s</td></tr>" % (
        c(n), bare(a) if r[0][0] > 0 else bare(a) + " or earlier", date("peft", a), "current" if cur else "removed after %s" % bare(b)))
LORA_ROWS = "\n".join(lora_rows)
N_LORA = sum(1 for r in LC.values() if r[-1][1] == len(PT) - 1)

def lf(arg):
    return bare(first("peft", "LoraConfig", arg))

TITLE = "LoraConfig, SFTTrainer: Unexpected Keyword Argument Lookup"
DESC = ("Paste a LoraConfig, SFTTrainer or TrainingArguments TypeError, or an adapter_config.json: "
        "see which release added or removed each argument and what replaces it.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))
H1 = "\"__init__() got an unexpected keyword argument\": the PEFT, TRL or Transformers release each argument needs"

FAQ = [
 ("What does \"LoraConfig.__init__() got an unexpected keyword argument\" mean?",
  "The adapter was saved with a newer PEFT than the one loading it: its adapter_config.json has a key your PEFT does not know. Each key has a first release, for example use_rslora %s, use_dora %s, layer_replication %s, lora_bias %s and alora_invocation_tokens %s. Install at least the release of the newest key in the file. PEFT %s and later no longer raise this error on load; they warn and ignore the unknown keys."
  % (lf("use_rslora"), lf("use_dora"), lf("layer_replication"), lf("lora_bias"), lf("alora_invocation_tokens"), bare(FWD))),
 ("Is it safe to delete the unknown key from adapter_config.json?",
  "Only if the key holds its default value, so that removing it changes nothing. A key such as use_dora set to true describes how the weights were trained; deleting it, or loading with PEFT %s or later where it is ignored with a warning, loads a different model than the one that was saved. Upgrading PEFT is the safe fix." % bare(FWD)),
 ("Why does TrainingArguments reject evaluation_strategy?",
  "evaluation_strategy was renamed to eval_strategy in Transformers %s. The old name kept working with a warning until %s and is gone from %s. Write eval_strategy."
  % (bare(first("transformers", "TrainingArguments", "eval_strategy")), bare(last("transformers", "TrainingArguments", "evaluation_strategy")), bare(nxt("transformers", last("transformers", "TrainingArguments", "evaluation_strategy"))))),
 ("Why does SFTTrainer reject tokenizer, dataset_text_field or max_seq_length?",
  "TRL moved them. tokenizer became processing_class in TRL %s; the old name was accepted with a warning until %s. dataset_text_field, max_seq_length and packing stopped being SFTTrainer arguments after %s and belong on SFTConfig. On SFTConfig, max_seq_length was renamed to max_length in %s and removed after %s."
  % (bare(first("trl", "SFTTrainer", "processing_class")), bare(alias("trl", "SFTTrainer", "tokenizer")[2]), bare(last("trl", "SFTTrainer", "dataset_text_field")),
     bare(first("trl", "SFTConfig", "max_length")), bare(last("trl", "SFTConfig", "max_seq_length")))),
 ("Why does Trainer reject tokenizer?",
  "Transformers %s renamed the Trainer argument tokenizer to processing_class. The old name was accepted with a deprecation warning through %s and removed in %s."
  % (bare(alias("transformers", "Trainer", "tokenizer")[1]), bare(alias("transformers", "Trainer", "tokenizer")[2]), bare(nxt("transformers", alias("transformers", "Trainer", "tokenizer")[2])))),
 ("How do I find which PEFT version saved an adapter?",
  "From PEFT %s the file adapter_config.json records it in the key peft_version. Older files do not say; the newest key in the file gives a lower bound, which the lookup on this page computes." % bare(first("peft", "LoraConfig", "peft_version"))),
]
ORG = {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"}
LD = {"@context": "https://schema.org", "@graph": [
 {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD, "inLanguage": "en",
  "author": ORG, "publisher": ORG, "about": ["PEFT", "LoRA", "TRL", "Hugging Face Transformers", "TrainingArguments", "SFTTrainer"]},
 {"@type": "WebApplication", "@id": URL + "#tool", "name": "Unexpected keyword argument lookup for PEFT, TRL and Transformers", "url": URL + "#lookup",
  "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (runs in the browser)", "isAccessibleForFree": True,
  "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
  "description": "Paste a TypeError line, an adapter_config.json or a Config(...) call; get the releases that accept each argument and what replaces removed ones."},
 {"@type": "Dataset", "@id": URL + "#data", "name": "Constructor arguments of PEFT configs, TRL configs and trainers, and Transformers TrainingArguments by release",
  "description": "Release ranges of every constructor argument of %d PEFT config classes (%s to %s), %d TRL config and trainer classes (%s to %s) and Transformers TrainingArguments, Seq2SeqTrainingArguments, Trainer and Seq2SeqTrainer (%s to %s)."
  % (len(LIBS["peft"]["classes"]), PT[0], PT[-1], len(LIBS["trl"]["classes"]), RT[0], RT[-1], TT[0], TT[-1]),
  "url": URL, "dateModified": MOD, "creator": ORG, "license": "https://creativecommons.org/licenses/by/4.0/"},
 {"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
 {"@type": "BreadcrumbList", "itemListElement": [
  {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
  {"@type": "ListItem", "position": 2, "name": "Unexpected keyword argument lookup", "item": URL}]}]}

ES_LAST = last("transformers", "TrainingArguments", "evaluation_strategy")
BODY = """<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>@@H1@@</h1>
<p class="lede"><strong>"X.__init__() got an unexpected keyword argument 'y'" means the installed library does not have <code>y</code> on that class: it is older than the release that added it, or newer than the release that removed it.</strong> For a LoRA adapter the cause is almost always an older PEFT: <code>use_rslora</code> needs PEFT @@L_RSLORA@@, <code>use_dora</code> @@L_DORA@@, <code>layer_replication</code> @@L_LAYERREP@@, <code>lora_bias</code> @@L_BIAS@@. For training scripts it is usually a removed name: <code>evaluation_strategy</code> is gone after Transformers @@ES_LAST@@ (write <code>eval_strategy</code>), and TRL's <code>SFTTrainer</code> stopped taking <code>dataset_text_field</code> and <code>max_seq_length</code> after @@SFT_LAST@@. Paste the error or the adapter's config below.</p>
<p class="meta">Published @@PUB@@ &middot; PEFT @@P0@@ to @@P1@@ (@@PN@@ releases) &middot; TRL @@R0@@ to @@R1@@ (@@RN@@) &middot; Transformers @@T0@@ to @@T1@@ (@@TN@@) &middot; read from each release's source, nothing was run &middot; dates are tag dates</p>

<h2 id="lookup">Which release has this argument?</h2>
<p>Paste a <code>TypeError</code> line, the contents of <code>adapter_config.json</code>, or a call such as <code>SFTConfig(max_seq_length=512)</code>. Versions are optional; with them you get a yes or no for your install.</p>
<div class="card">
<label for="q">Error, adapter_config.json or code</label>
<textarea id="q" spellcheck="false" placeholder="TypeError: LoraConfig.__init__() got an unexpected keyword argument 'use_dora'"></textarea>
<div class="grid3">
<div><label for="vp">Your peft (optional)</label><input id="vp" placeholder="0.8.2" autocomplete="off"></div>
<div><label for="vt">Your transformers (optional)</label><input id="vt" placeholder="4.44.0" autocomplete="off"></div>
<div><label for="vr">Your trl (optional)</label><input id="vr" placeholder="0.11.4" autocomplete="off"></div>
</div>
<div class="row"><button id="go" type="button">Check</button><span id="status" role="status"></span></div>
<div id="res" aria-live="polite"></div>
</div>
<p class="note">Runs in your browser; nothing is sent anywhere. Versions: <code>pip show peft transformers trl</code>. The lookup knows @@NPC@@ PEFT config classes, @@NRC@@ TRL config and trainer classes, and Transformers <code>TrainingArguments</code>, <code>Seq2SeqTrainingArguments</code>, <code>Trainer</code> and <code>Seq2SeqTrainer</code>.</p>

<h2 id="common">What do the most common of these errors mean?</h2>
<div class="tw"><table class="full">
<thead><tr><th>Error names</th><th>Cause</th><th>Fix</th></tr></thead>
<tbody>
@@COMMON_ROWS@@
</tbody></table></div>

<h2 id="peft">Which PEFT release does each adapter_config.json key need?</h2>
<p><strong>A LoRA adapter loads without loss on any PEFT at or above the first release of its newest key.</strong> The table has every key <code>LoraConfig</code> has accepted (its own fields and those of its base classes), newest first; @@NLORA@@ are current in @@P1@@.</p>
<div class="tw"><table class="full">
<thead><tr><th>Key</th><th>First PEFT release</th><th>Status in @@P1B@@</th></tr></thead>
<tbody>
@@LORA_ROWS@@
</tbody></table></div>
<p class="note">From PEFT @@PV@@ the file also records the saving version in <code>peft_version</code>. The other @@NPC1@@ config classes (AdaLoRA, IA3, LoHa, LoKr, VeRA, OFT, prompt tuning and the rest) are in the lookup above but not in this table.</p>

<h2 id="forward">Why does the same adapter raise TypeError on one machine and only a warning on another?</h2>
<p><strong>PEFT changed what it does with unknown keys in @@FWD@@.</strong> Up to @@PREV_FWD@@, loading a config with a key the installed PEFT does not know fails with <code>TypeError: LoraConfig.__init__() got an unexpected keyword argument</code>. From @@FWD@@ the loader catches that error, removes the unknown keys and continues with a warning. PEFT @@FWD@@ loading an adapter saved with @@EX_VER@@ prints:</p>
<pre><code>UserWarning: Unexpected keyword arguments @@EX_KEYS@@ for class LoraConfig, these are ignored. This probably means that you're loading a configuration file that was saved using a higher version of the library and additional parameters have been introduced since. It is highly recommended to upgrade the PEFT version before continuing (e.g. by running `pip install -U peft`).</code></pre>
<p>The warning is easy to miss, and the adapter then runs without the dropped settings. That is harmless when every dropped key held its default and wrong when one did not, for example a config saved with a newer variant switched on. Constructing a config in your own code, <code>LoraConfig(use_dora=True)</code>, still raises <code>TypeError</code> on every release that lacks the argument; only loading from a file is lenient.</p>
<ul>
<li><strong>Fix that always works:</strong> upgrade PEFT to the release in the table, or newer.</li>
<li><strong>Deleting the key by hand</strong> is the same as what @@FWD@@ and later do automatically. PEFT's own troubleshooting page allows it only when the key is at its default value.</li>
<li><strong>A key that was removed</strong> (<code>enable_lora</code>, <code>merge_weights</code>, last in @@ENL@@) means the opposite direction: a very old adapter on a new PEFT.</li>
</ul>

<h2 id="transformers">Which TrainingArguments and Trainer arguments were removed from Transformers?</h2>
<p><strong>Transformers @@V5@@ removed most long-deprecated <code>TrainingArguments</code> names at once; a few went earlier or later.</strong> <code>evaluation_strategy</code> was last accepted in @@ES_LAST@@. <code>Trainer(tokenizer=...)</code> became <code>processing_class</code> in @@TK_FROM@@, stayed as a warned alias until @@TK_TO@@ and is rejected from @@TK_GONE@@.</p>
<div class="tw"><table class="full">
<thead><tr><th>TrainingArguments argument</th><th>From</th><th>Last release</th><th>Gone in</th><th>What to use</th></tr></thead>
<tbody>
@@TA_ROWS@@
</tbody></table></div>
<p class="note">"From" v4.0.0 means v4.0.0 or earlier; older releases were not read. <code>Seq2SeqTrainingArguments</code> inherits all of these.</p>

<h2 id="trl">Which SFTTrainer, SFTConfig and DPOConfig arguments did TRL remove?</h2>
<p><strong>TRL @@SFT_GONE@@ removed the dataset and length arguments from the trainers; they are set on the config classes (which exist from @@CFG_FROM@@), and several were renamed there later.</strong> An old fine-tuning script can therefore fail three times in a row on a current release: on <code>tokenizer</code>, then <code>dataset_text_field</code>, then <code>max_seq_length</code>.</p>
<div class="tw"><table class="full">
<thead><tr><th>Argument</th><th>From</th><th>Last release</th><th>Gone in</th><th>What to use</th></tr></thead>
<tbody>
@@SFTT_ROWS@@
@@SFTC_ROWS@@
@@DPOC_ROWS@@
</tbody></table></div>
<p class="note">TRL configs extend <code>TrainingArguments</code>, so <code>SFTConfig(evaluation_strategy=...)</code> fails or works according to the installed Transformers, not TRL. Names that only moved to TRL's shared base config in v0.29.0 (<code>bf16</code>, <code>logging_steps</code>, <code>gradient_checkpointing</code>, <code>lr_scheduler_kwargs</code>) are still accepted and are not listed. <code>GRPOConfig</code>, <code>DPOTrainer</code> and the other @@NRC1@@ TRL classes are in the lookup.</p>
<p><label for="filter">Filter all tables</label><input id="filter" placeholder="max_" autocomplete="off" style="max-width:320px"></p>

<h2 id="method">How was this built?</h2>
<ul>
<li><strong>Source:</strong> every final release tag of <code>huggingface/peft</code> (@@PN@@), <code>huggingface/trl</code> (@@RN@@) and <code>huggingface/transformers</code> from v4.0.0 (@@TN@@), parsed with Python's <code>ast</code>. No library code was imported or run.</li>
<li><strong>Config classes:</strong> the dataclass fields of the class plus those of its base classes in the same package (<code>LoraConfig</code> + <code>PeftConfig</code> + <code>PeftConfigMixin</code>; <code>SFTConfig</code> + TRL's base config). Fields declared <code>init=False</code> are left out.</li>
<li><strong>Trainers:</strong> the parameters of <code>__init__</code>. A name handled by <code>@deprecate_kwarg</code> is counted as an alias for the releases that carry the decorator.</li>
<li><strong>Replacements:</strong> taken from the deprecation message in the last release that still had the old name, and checked against the data: the build fails if a replacement did not exist in the stated release.</li>
<li><strong>The @@FWD@@ change:</strong> the first release whose <code>src/peft/config.py</code> catches the TypeError and warns (commit <a href="https://github.com/huggingface/peft/commit/85e3202a">85e3202a</a>).</li>
</ul>

<h2 id="limits">What this page does not cover</h2>
<ul>
<li>Nothing was executed. The page reports which names a constructor accepts, not whether a value is valid or what it does.</li>
<li>Changed defaults and changed behaviour of an argument that kept its name.</li>
<li>Transformers classes other than the four named above, and model or tokenizer <code>from_pretrained</code> arguments.</li>
<li>Release candidates, development installs and forks. An adapter saved from a PEFT source checkout can hold keys no release has yet.</li>
<li>Arguments passed through <code>**kwargs</code> to another library.</li>
</ul>

<h2 id="faq">Questions</h2>
<dl>
@@FAQ@@
</dl>

<p class="note">Related: <a href="/en/model-arch-min-version/">minimum Transformers and vLLM version for a model architecture</a> &middot; <a href="/en/vllm-removed-flags-lookup/">removed vLLM arguments, environment variables and request fields</a> &middot; <a href="/en/gguf-arch-min-build-lookup/">GGUF architecture lookup</a>.</p>

<h2 id="sources">Sources</h2>
<ul>
<li>PEFT: <a href="https://github.com/huggingface/peft/blob/main/src/peft/tuners/lora/config.py">tuners/lora/config.py</a>, <a href="https://github.com/huggingface/peft/blob/main/src/peft/config.py">config.py</a>, <a href="https://huggingface.co/docs/peft/developer_guides/troubleshooting">troubleshooting guide</a> ("Error while loading the config because of an unexpected keyword argument")</li>
<li>Transformers: <a href="https://github.com/huggingface/transformers/blob/main/src/transformers/training_args.py">training_args.py</a>, <a href="https://github.com/huggingface/transformers/blob/main/src/transformers/trainer.py">trainer.py</a></li>
<li>TRL: <a href="https://github.com/huggingface/trl/blob/main/trl/trainer/sft_config.py">sft_config.py</a>, <a href="https://github.com/huggingface/trl/blob/main/trl/trainer/sft_trainer.py">sft_trainer.py</a>, <a href="https://github.com/huggingface/trl/blob/main/trl/trainer/dpo_config.py">dpo_config.py</a></li>
</ul>
</main>"""

tk = alias("transformers", "Trainer", "tokenizer")
V5 = nxt("transformers", last("transformers", "TrainingArguments", "no_cuda"))
assert V5 == "v5.0.0", V5
assert len([1 for n, r, end in gone("transformers", "TrainingArguments") if TT[end] == "v4.57.6"]) >= 20
SFT_GONE = nxt("trl", last("trl", "SFTTrainer", "dataset_text_field"))
# ---- the most common errors, one row each; every release comes from the data ----
def same_first(lib, cls, args):
    v = {first(lib, cls, a) for a in args}
    assert len(v) == 1, (cls, args, v)
    assert all(last(lib, cls, a) == latest(lib) for a in args), (cls, args)
    return bare(v.pop())
def same_last(lib, cls, args):
    v = {last(lib, cls, a) for a in args}
    assert len(v) == 1, (cls, args, v)
    return v.pop()
def crow(cls, args, cause, fix):
    return "<tr><td>%s %s</td><td>%s</td><td>%s</td></tr>" % (e(cls), ", ".join(c("'%s'" % a) for a in args), cause, fix)
COMMON = []
for args in (["use_dora"], ["use_rslora"], ["layer_replication"], ["loftq_config"], ["lora_bias", "eva_config", "exclude_modules"],
             ["corda_config", "trainable_token_indices"], ["alora_invocation_tokens", "arrow_config", "ensure_weight_tying"]):
    v = same_first("peft", "LoraConfig", args)
    COMMON.append(crow("LoraConfig", args, "The installed PEFT is older than %s. Usually the adapter was saved with a newer PEFT; the same error appears when your own code passes the option." % v,
                       '<code>pip install -U "peft&gt;=%s"</code>' % v))
_es = last("transformers", "TrainingArguments", "evaluation_strategy")
COMMON.append(crow("TrainingArguments", ["evaluation_strategy"], "Removed from Transformers in %s (last accepted in %s)." % (bare(nxt("transformers", _es)), bare(_es)),
                   "Write <code>eval_strategy</code> (from %s)." % bare(first("transformers", "TrainingArguments", "eval_strategy"))))
COMMON.append(crow("TrainingArguments", ["eval_strategy"], "The installed Transformers is older than %s." % same_first("transformers", "TrainingArguments", ["eval_strategy"]),
                   "Upgrade Transformers, or write <code>evaluation_strategy</code> on that old release."))
_tk = alias("trl", "SFTTrainer", "tokenizer")
COMMON.append(crow("SFTTrainer", ["tokenizer"], "Renamed in TRL %s; the old name was a warned alias until %s and is rejected from %s." % (bare(_tk[1]), bare(_tk[2]), bare(nxt("trl", _tk[2]))),
                   "Write <code>processing_class</code>."))
_sl = same_last("trl", "SFTTrainer", ["dataset_text_field", "max_seq_length", "packing"])
COMMON.append(crow("SFTTrainer", ["dataset_text_field", "max_seq_length", "packing"], "No longer trainer arguments from TRL %s (last accepted in %s)." % (bare(nxt("trl", _sl)), bare(_sl)),
                   "Set them on <code>SFTConfig</code> and pass it as <code>args</code>."))
_ml = last("trl", "SFTConfig", "max_seq_length")
COMMON.append(crow("SFTConfig", ["max_seq_length"], "Removed from TRL in %s (last accepted in %s)." % (bare(nxt("trl", _ml)), bare(_ml)),
                   "Write <code>max_length</code> (from %s)." % bare(first("trl", "SFTConfig", "max_length"))))
_tt = alias("transformers", "Trainer", "tokenizer")
COMMON.append(crow("Trainer", ["tokenizer"], "Renamed in Transformers %s; a warned alias until %s, rejected from %s." % (bare(_tt[1]), bare(_tt[2]), bare(nxt("transformers", _tt[2]))),
                   "Write <code>processing_class</code>."))
COMMON_ROWS = "\n".join(COMMON)

# the example in the "forward" section: the keys the release after FWD added, as the warning would list them
EX_TAG = next(t for t in PT[PT.index(FWD) + 1:] if any(PT[r[0][0]] == t for r in LC.values()))
EX_KEYS = sorted(n for n, r in LC.items() if PT[r[0][0]] == EX_TAG)
assert EX_TAG == "v0.15.0" and EX_KEYS == ["corda_config", "trainable_token_indices"], (EX_TAG, EX_KEYS)
subs = {
    "COMMON_ROWS": COMMON_ROWS,
    "EX_VER": bare(EX_TAG), "EX_KEYS": e(repr(EX_KEYS)), "CFG_FROM": bare(first("trl", "SFTConfig", "dataset_text_field")),
    "H1": e(H1), "PUB": PUB, "P0": bare(PT[0]), "P1": bare(PT[-1]), "P1B": bare(PT[-1]), "PN": str(len(PT)), "R0": bare(RT[0]), "R1": bare(RT[-1]), "RN": str(len(RT)),
    "T0": bare(TT[0]), "T1": bare(TT[-1]), "TN": str(len(TT)),
    "L_RSLORA": lf("use_rslora"), "L_DORA": lf("use_dora"), "L_LAYERREP": lf("layer_replication"), "L_BIAS": lf("lora_bias"),
    "ES_LAST": bare(ES_LAST), "SFT_LAST": "TRL " + bare(last("trl", "SFTTrainer", "dataset_text_field")), "SFT_GONE": bare(SFT_GONE),
    "NPC": str(len(LIBS["peft"]["classes"])), "NPC1": str(len(LIBS["peft"]["classes"]) - 1), "NRC": str(len(LIBS["trl"]["classes"])), "NRC1": str(len(LIBS["trl"]["classes"]) - 3),
    "NLORA": str(N_LORA), "LORA_ROWS": LORA_ROWS, "PV": bare(first("peft", "LoraConfig", "peft_version")),
    "FWD": bare(FWD), "PREV_FWD": bare(PREV_FWD), "ENL": bare(last("peft", "LoraConfig", "enable_lora")),
    "V5": bare(V5), "TK_FROM": bare(tk[1]), "TK_TO": bare(tk[2]), "TK_GONE": bare(nxt("transformers", tk[2])),
    "TA_ROWS": gone_rows("transformers", "TrainingArguments") + "\n" + gone_rows("transformers", "Trainer", label=True),
    "SFTT_ROWS": gone_rows("trl", "SFTTrainer", label=True), "SFTC_ROWS": gone_rows("trl", "SFTConfig", label=True), "DPOC_ROWS": gone_rows("trl", "DPOConfig", label=True),
    "FAQ": "\n".join("<dt>%s</dt><dd>%s</dd>" % (e(q), e(a)) for q, a in FAQ),
}
body = BODY
for k, v in subs.items():
    body = body.replace("@@" + k + "@@", v)
assert not re.findall(r"@@[A-Z0-9_]+@@", body), re.findall(r"@@[A-Z0-9_]+@@", body)

data = {"libs": LIBS, "hints": hints, "ptype": D["peft_types"], "forward": FWD, "main": MAIN}
CSS = open(os.path.join(HERE, "style.css")).read()
JS = open(os.path.join(HERE, "tool.js")).read()
doc = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="canonical" href="%s">
<meta property="og:type" content="article">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:url" content="%s">
<script type="application/ld+json">%s</script>
<style>
%s
h3{font-size:1.05rem;margin:1.4em 0 .3em}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px 14px}
@media (max-width:560px){.grid3{grid-template-columns:1fr}}
#res td{overflow-wrap:anywhere}
#res td:first-child,#res td:nth-child(2){overflow-wrap:normal}
@media (max-width:560px){#res thead{display:none}#res tr{display:block;padding:8px 0;border-bottom:1px solid var(--line)}#res td{display:block;border:0;padding:2px 0}#res td:nth-child(3)::before{content:"Accepted in: ";color:var(--mut)}}
table.full{min-width:560px}
table.full td:first-child{white-space:nowrap}
</style>
</head>
<body>
%s
<script type="application/json" id="pt-data">%s</script>
<script>
%s
</script>
</body>
</html>
""" % (e(TITLE), e(DESC), URL, e(TITLE), e(DESC), URL, json.dumps(LD, ensure_ascii=True).replace("</", "<\\/"), CSS, body,
       json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/"), JS)
doc.encode("ascii")
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "index.html"), "w", encoding="ascii").write(doc)
print("index.html", len(doc), "bytes; LoraConfig keys", len(LC), "; TrainingArguments removed", len(gone("transformers", "TrainingArguments")),
      "; SFTTrainer removed", len(gone("trl", "SFTTrainer")), "; SFTConfig removed", len(gone("trl", "SFTConfig")), "; DPOConfig removed", len(gone("trl", "DPOConfig")))
