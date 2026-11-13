"""Build /en/vllm-removed-flags-lookup/index.html. Usage: python3 build_page.py out/data.json scripts OUTDIR PUBLISHED MODIFIED"""
import json, sys, os, html
D = json.load(open(sys.argv[1])); S = sys.argv[2]; OUT, PUB, MOD = sys.argv[3:6]
URL = "https://erimaki-kobo.github.io/en/vllm-removed-flags-lookup/"
e = lambda s: html.escape(str(s), quote=True)
c = lambda s: f"<code>{e(s)}</code>"
L = D["libs"]
def rng(lib, n):
    T = L[lib]["tags"]; return [(T[a], T[b]) for a, b in L[lib]["names"][n]]
def last(lib, n): return rng(lib, n)[-1][1]
def first(lib, n): return rng(lib, n)[0][0]
VL, SG = L["vllm_cli"]["tags"][-1], L["sglang_cli"]["tags"][-1]
# ---- curated replacements; every version claim is checked against the data ----
HV = [  # (lib, names, claimed last, replacement html, replacement flag(s) checked to exist since version)
 ("vllm_cli", ["--speculative-model", "--num-speculative-tokens"], "v0.8.2", "Use <code>--speculative-config</code> (JSON, from v0.8.2), e.g. <code>--speculative-config '{\"model\": \"...\", \"num_speculative_tokens\": 5}'</code>.", [("--speculative-config", "v0.8.2")]),
 ("vllm_cli", ["--enable-reasoning"], "v0.9.2", "Drop it; <code>--reasoning-parser</code> alone turns reasoning parsing on.", [("--reasoning-parser", "v0.7.1")]),
 ("vllm_cli", ["--use-v2-block-manager"], "v0.9.2", "Drop it; there is only one block manager.", []),
 ("vllm_cli", ["--guided-decoding-backend"], "v0.10.2", "Use <code>--structured-outputs-config '{\"backend\": \"...\"}'</code> (from v0.11.0).", [("--structured-outputs-config", "v0.11.0")]),
 ("vllm_cli", ["--task"], "v0.12.0", "For text generation, drop it. For embedding, classification or reward models use <code>--runner pooling</code> with <code>--convert embed|classify|reward</code> (from v0.10.1).", [("--runner", "v0.10.1"), ("--convert", "v0.10.1")]),
 ("vllm_cli", ["--disable-log-requests"], "v0.16.0", "Drop it; requests are not logged by default. <code>--enable-log-requests</code> (from v0.10.1) turns logging on.", [("--enable-log-requests", "v0.10.1")]),
 ("vllm_cli", ["--worker-use-ray"], "v0.6.6.post1", "Use <code>--distributed-executor-backend ray</code> (from v0.4.3).", [("--distributed-executor-backend", "v0.4.3")]),
 ("vllm_cli", ["--engine-use-ray"], "v0.6.1", "Use <code>--distributed-executor-backend ray</code> (from v0.4.3).", [("--distributed-executor-backend", "v0.4.3")]),
 ("vllm_cli", ["--swap-space"], "v0.17.1", "Drop it; there is no CPU swap space any more.", []),
 ("vllm_env", ["VLLM_USE_V1"], "v0.11.0", "Drop it; the V1 engine is the only engine.", []),
 ("vllm_env", ["VLLM_ATTENTION_BACKEND"], "v0.14.1", "Use <code>--attention-backend</code> (from v0.13.0).", [("--attention-backend", "v0.13.0")]),
 ("vllm_env", ["VLLM_FLASH_ATTN_VERSION", "VLLM_USE_TRTLLM_ATTENTION"], "v0.14.1", "Use the matching key of <code>--attention-config</code> (from v0.13.0).", [("--attention-config", "v0.13.0")]),
 ("vllm_env", ["VLLM_USE_TRITON_FLASH_ATTN"], "v0.11.0", "No replacement variable; choose the backend with <code>--attention-backend</code> on v0.13.0 and later.", []),
 ("vllm_env", ["VLLM_TORCH_PROFILER_DIR"], "v0.15.1", "Use <code>--profiler-config</code> (from v0.13.0).", [("--profiler-config", "v0.13.0")]),
 ("vllm_env", ["VLLM_ALL2ALL_BACKEND"], "v0.15.1", "Use <code>--all2all-backend</code> (from v0.11.1).", [("--all2all-backend", "v0.11.1")]),
 ("vllm_env", ["VLLM_MM_INPUT_CACHE_GIB"], "v0.12.0", "Use <code>--mm-processor-cache-gb</code> (from v0.10.1).", [("--mm-processor-cache-gb", "v0.10.1")]),
 ("vllm_env", ["VLLM_USE_FLASHINFER_MOE_FP8"], "v0.23.0", "Probably <code>--moe-backend</code> (from v0.17.0); the move was not traced line by line.", [("--moe-backend", "v0.17.0")]),
 ("vllm_env", ["VLLM_SLEEP_WHEN_IDLE"], "v0.17.1", "No replacement.", []),
 ("vllm_env", ["VLLM_RPC_TIMEOUT"], "v0.22.1", "No replacement.", []),
 ("vllm_env", ["VLLM_ENGINE_ITERATION_TIMEOUT_S"], "v0.31.0", "No replacement.", []),
 ("vllm_env", ["VLLM_TORCH_COMPILE_LEVEL"], "v0.6.4.post1", "Use <code>-O</code> or <code>--compilation-config</code>.", []),
 ("vllm_sampling_params", ["use_beam_search", "length_penalty", "early_stopping"], "v0.6.2", "Use <code>LLM.beam_search()</code> with <code>BeamSearchParams</code> (from v0.6.3).", []),
 ("vllm_sampling_params", ["guided_decoding"], "v0.11.2", "Use <code>structured_outputs=StructuredOutputsParams(...)</code> (from v0.11.0).", []),
 ("vllm_sampling_params", ["best_of"], "v0.11.2", "Generate <code>n</code> samples and pick in your code.", []),
 ("vllm_sampling_params", ["logits_processors", "truncate_prompt_tokens"], "v0.16.0", "<code>logits_processors</code>: probably the server-level <code>--logits-processors</code> (from v0.10.1). <code>truncate_prompt_tokens</code>: still a server request field.", []),
 ("vllm_chat", ["guided_json", "guided_regex", "guided_choice", "guided_grammar", "guided_decoding_backend"], "v0.11.2", "Send <code>\"structured_outputs\": {\"json\": ...}</code> (or <code>regex</code>, <code>choice</code>, <code>grammar</code>), from v0.11.0, or <code>response_format</code>.", []),
 ("vllm_chat", ["best_of"], "v0.11.2", "Ask for <code>n</code> completions and pick in your code.", []),
 ("vllm_chat", ["logits_processors"], "v0.16.0", "Probably the server-level <code>--logits-processors</code> (from v0.10.1).", []),
 ("vllm_chat", ["return_assistant_tokens_mask"], "v0.30.0", "No replacement.", []),
 ("sglang_cli", ["--enable-flashinfer"], "v0.1.17", "FlashInfer became the default; choose kernels with <code>--attention-backend</code> (from v0.3.1.post1).", []),
 ("sglang_cli", ["--disable-flashinfer-sampling"], "v0.4.1.post1", "Use <code>--sampling-backend</code> (from v0.3.1.post1).", []),
 ("sglang_cli", ["--enable-overlap-schedule"], "v0.4.1.post1", "Overlap scheduling is the default; only <code>--disable-overlap-schedule</code> remains.", []),
 ("sglang_cli", ["--enable-ep-moe", "--enable-deepep-moe"], "v0.5.4", "Use <code>--ep-size</code> and <code>--moe-a2a-backend</code> (from v0.4.10.post2).", []),
 ("sglang_cli", ["--enable-flashinfer-cutlass-moe"], "v0.5.4", "Use <code>--moe-runner-backend</code> (from v0.5.1).", []),
 ("sglang_cli", ["--cuda-graph-max-bs", "--cuda-graph-bs"], "v0.5.19", "Use <code>--cuda-graph-max-bs-decode</code> / <code>--cuda-graph-max-bs-prefill</code>, <code>--cuda-graph-bs-decode</code> / <code>--cuda-graph-bs-prefill</code> or <code>--cuda-graph-config</code> (from v0.5.14). From v0.5.20 the old name is a prefix of two new ones, so argparse reports it as ambiguous rather than unrecognized.", []),
 ("sglang_cli", ["--disable-piecewise-cuda-graph"], "v0.5.19", "Use <code>--cuda-graph-backend-prefill</code> / <code>--cuda-graph-backend-decode</code> (from v0.5.14).", []),
 ("sglang_cli", ["--torchao-config", "--stream-output"], "v0.5.19", "No replacement argument.", []),
]
hints = {}
for lib, names, lst, txt, deps in HV:
    for n in names:
        got = last(lib, n)
        if lib == "sglang_cli" and n == "--torchao-config": assert got == "v0.5.17", got
        else: assert got == lst, (lib, n, got, lst)
        hints.setdefault(lib, {})[n] = txt
    for f, since in deps:
        assert first("vllm_cli", f) == since, (f, first("vllm_cli", f), since)
hints["vllm_completion"] = {k: v for k, v in hints["vllm_chat"].items() if k in L["vllm_completion"]["names"]}

def gone(lib):
    T = L[lib]["tags"]; lastI = len(T) - 1
    out = [(n, r) for n, r in L[lib]["names"].items() if r[-1][1] != lastI]
    out.sort(key=lambda x: (x[1][-1][1], x[0]))
    return out
def gone_rows(lib):
    T = L[lib]["tags"]
    return "\n".join(f"<tr><td>{c(n)}</td><td>{T[r[0][0]]}</td><td>{T[r[-1][1]]}</td><td>{T[r[-1][1] + 1]}</td></tr>" for n, r in gone(lib))
G = {k: len(gone(k)) for k in L}
assert G["vllm_cli"] == 81 and G["vllm_env"] == 120 and G["sglang_cli"] == 106, G
req_gone = sorted(set(n for k in ("vllm_chat", "vllm_completion") for n, r in gone(k)))
def cur(lib): return len(L[lib]["names"]) - G[lib]

TITLE = "vLLM Removed Arguments, Env Vars and Request Fields Lookup"
DESC = "Paste a vllm serve command, VLLM_ variables or a request body: see which names were removed, in which release, what replaces them. SGLang too."
assert len(TITLE) <= 62 and len(DESC) <= 160, (len(TITLE), len(DESC))
H1 = "\"unrecognized arguments\" and settings that silently stop working: removed vLLM arguments, environment variables and request fields"
FAQ = [
 ("Why does vllm serve say \"unrecognized arguments: --X\"?", "The argument is not defined in your vLLM release: either it was removed (for example --speculative-model after v0.8.2, --guided-decoding-backend after v0.10.2, --task after v0.12.0, --disable-log-requests after v0.16.0) or it was added in a newer release than yours. The lookup on this page gives the release range for every argument vLLM ever had."),
 ("Is VLLM_ATTENTION_BACKEND still supported?", "No. It was last read in v0.14.1. From v0.13.0 the replacement is the --attention-backend argument. Setting the variable on newer releases does not raise an error; from v0.17.0 vLLM only logs \"Unknown vLLM environment variable detected\" at startup."),
 ("Why is my guided_json request not constrained any more?", "guided_json and the other guided_* request fields were removed after v0.11.2. Because vLLM's server accepts unknown fields and drops them, the request still succeeds and the output is simply unconstrained. Use structured_outputs (from v0.11.0) or response_format. vLLM v0.30.0 and later log a warning for these specific fields."),
 ("How do I turn off a boolean option like chunked prefill?", "From v0.8.5, vLLM's boolean options use --X and --no-X, so write --no-enable-chunked-prefill. The old form --enable-chunked-prefill False fails there with \"unrecognized arguments: False\". On v0.5.3 to v0.8.4 write --enable-chunked-prefill false."),
 ("Can I write --max_model_len with underscores?", "Yes. vLLM's argument parser accepts underscores and dashes in argument names, and reads --json-arg.key value as a key inside a JSON argument."),
]
LD = {"@context": "https://schema.org", "@graph": [
 {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD, "inLanguage": "en",
  "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"}, "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
  "about": ["vLLM", "SGLang", "vllm serve", "environment variables", "OpenAI-compatible server"]},
 {"@type": "WebApplication", "@id": URL + "#tool", "name": "Removed vLLM and SGLang argument lookup", "url": URL + "#lookup", "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (runs in the browser)", "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "description": "Paste a command, environment variables or a request body; get the releases that support each name and what replaces removed ones."},
 {"@type": "Dataset", "@id": URL + "#data", "name": "vLLM and SGLang argument, environment variable and request field history", "description": f"Release ranges of every vLLM command-line argument (v0.1.0 to {VL}), VLLM_ environment variable, SamplingParams argument and OpenAI-compatible request field, and every SGLang server argument (v0.1.3 to {SG}).", "url": URL, "dateModified": MOD, "creator": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"}, "license": "https://creativecommons.org/licenses/by/4.0/"},
 {"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}]}

def hint_rows(lib):
    rows = []
    for l2, names, lst, txt, deps in HV:
        if l2 != lib: continue
        rows.append(f"<tr><td>{' '.join(c(n) for n in names)}</td><td>{e(last(lib, names[0]))}</td><td>{txt}</td></tr>")
    return "\n".join(rows)

body = f"""<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>{e(H1)}</h1>
<p class="lede"><strong>vLLM has removed {G['vllm_cli']} command-line arguments, {G['vllm_env']} environment variables and {len(req_gone)} server request fields since its first release. A removed argument stops <code>vllm serve</code> with "unrecognized arguments"; a removed variable or request field does not: vLLM ignores it and runs without the setting.</strong> Common cases: <code>--speculative-model</code> ended in v0.8.2 (use <code>--speculative-config</code>), <code>--task</code> in v0.12.0 (use <code>--runner</code> and <code>--convert</code>), <code>VLLM_ATTENTION_BACKEND</code> in v0.14.1 (use <code>--attention-backend</code>), and <code>guided_json</code> in v0.11.2 (use <code>structured_outputs</code>). Paste your command or request below to check every name in it.</p>
<p class="meta">Published {PUB} &middot; vLLM v0.1.0 to {VL} ({len(L['vllm_cli']['tags'])} releases) &middot; SGLang v0.1.3 to {SG} ({len(L['sglang_cli']['tags'])} releases) &middot; read from each release's source</p>

<h2 id="lookup">Which names in my command still work?</h2>
<p>Paste a <code>vllm serve</code> or <code>python -m sglang.launch_server</code> command, the error message, <code>export VLLM_...</code> lines, a JSON request body, or a <code>SamplingParams(...)</code> call. Enter your version to check against it; otherwise the newest release is used.</p>
<div class="card">
<label for="q">Command, error, variables or request</label>
<textarea id="q" spellcheck="false" placeholder="VLLM_ATTENTION_BACKEND=FLASHINFER vllm serve Qwen/Qwen3-8B --task generate --disable-log-requests --guided-decoding-backend xgrammar"></textarea>
<div class="grid">
<div><label for="eng">Server</label><select id="eng"><option value="auto">Detect (vLLM unless the text says sglang)</option><option value="vllm">vLLM</option><option value="sglang">SGLang</option></select></div>
<div><label for="v">Your version (optional)</label><input id="v" placeholder="0.10.1" autocomplete="off"></div>
</div>
<div class="row"><button id="go" type="button">Check</button><span id="status" role="status"></span></div>
<div id="res" aria-live="polite"></div>
</div>
<p class="note">Runs in your browser; nothing is sent anywhere. Version: <code>python -c "import vllm; print(vllm.__version__)"</code>. Environment variables are checked against vLLM only.</p>

<h2 id="silent">Which removals fail loudly, and which fail silently?</h2>
<p><strong>Only command-line arguments and <code>SamplingParams</code> arguments raise an error. Environment variables and server request fields are dropped without one.</strong></p>
<div class="tw"><table>
<thead><tr><th>Where the name is used</th><th>What happens with a removed name</th><th>Since</th></tr></thead>
<tbody>
<tr><td><code>vllm serve --X</code></td><td>Exits with "unrecognized arguments: --X"</td><td>always</td></tr>
<tr><td><code>VLLM_X=...</code> in the environment</td><td>Not read. No error. From v0.17.0 a startup warning "Unknown vLLM environment variable detected: VLLM_X" (an error with <code>--fail-on-environ-validation</code>)</td><td>warning from v0.17.0</td></tr>
<tr><td>Field in a request to the OpenAI-compatible server</td><td>v0.6.4 and earlier: rejected (400). v0.6.5 to v0.17.1: accepted, dropped, logged as a WARNING "The following fields were present in the request but ignored". From v0.18.0 that log line is DEBUG, so nothing shows. From v0.30.0 the removed <code>guided_*</code> fields get their own warning that output will not be constrained</td><td>silent from v0.18.0</td></tr>
<tr><td><code>SamplingParams(x=...)</code> in Python</td><td><code>TypeError: unexpected keyword argument</code></td><td>always</td></tr>
</tbody></table></div>

<h2 id="common">What replaces the removed vLLM arguments people still copy?</h2>
<div class="tw"><table>
<thead><tr><th>Argument</th><th>Last release with it</th><th>What to use</th></tr></thead>
<tbody>
{hint_rows('vllm_cli')}
</tbody></table></div>
<p id="negated" class="note"><strong>Turning a boolean off.</strong> <code>--no-X</code> exists only for arguments built with argparse's BooleanOptionalAction: the first was <code>--enable-prefix-caching</code> in v0.6.5, most config-backed switches followed in v0.8.5, server switches in v0.10.0. From v0.8.5 a value after the switch is not accepted, so <code>--enable-chunked-prefill False</code> fails with "unrecognized arguments: False"; write <code>--no-enable-chunked-prefill</code>. On v0.5.3 to v0.8.4 write <code>--enable-chunked-prefill false</code>.</p>

<h2 id="env">Which VLLM_ environment variables stopped working?</h2>
<div class="tw"><table>
<thead><tr><th>Variable</th><th>Last release that reads it</th><th>What to use</th></tr></thead>
<tbody>
{hint_rows('vllm_env')}
</tbody></table></div>
<p class="note">"Last release that reads it" is the last release whose <code>vllm/envs.py</code> defines the name. Environment variables are tracked from v0.4.2, when that file appeared.</p>

<h2 id="request">Which request fields and SamplingParams arguments were removed?</h2>
<div class="tw"><table>
<thead><tr><th>Server request field</th><th>Last release</th><th>What to use</th></tr></thead>
<tbody>
{hint_rows('vllm_chat')}
</tbody></table></div>
<div class="tw"><table>
<thead><tr><th><code>SamplingParams</code> argument</th><th>Last release</th><th>What to use</th></tr></thead>
<tbody>
{hint_rows('vllm_sampling_params')}
</tbody></table></div>
<p class="note">The structured-output fields and which backend serves them are covered in detail on <a href="/en/vllm-structured-output-backend-cost/">vLLM structured output: which backend runs your schema</a>.</p>

<h2 id="sglang">Which SGLang arguments were removed?</h2>
<p><strong>SGLang has removed {G['sglang_cli']} server arguments; {cur('sglang_cli')} exist in {SG}.</strong> Unlike vLLM, SGLang's parser accepts unambiguous prefixes, so <code>--tp</code> works as <code>--tp-size</code>, and an old name that is now the prefix of two new ones fails as "ambiguous option".</p>
<div class="tw"><table>
<thead><tr><th>Argument</th><th>Last release with it</th><th>What to use</th></tr></thead>
<tbody>
{hint_rows('sglang_cli')}
</tbody></table></div>

<h2 id="table">Full lists of removed names</h2>
<p>Every name that existed in some release and is gone from the newest one: the first release that had it, the last one, and the first one without it. Filter all four tables at once.</p>
<p><label for="filter">Filter</label><input id="filter" placeholder="guided" autocomplete="off" style="max-width:320px"></p>
<h3>vLLM command-line arguments ({G['vllm_cli']})</h3>
<div class="tw"><table class="full"><thead><tr><th>Argument</th><th>From</th><th>Last</th><th>Gone in</th></tr></thead><tbody>
{gone_rows('vllm_cli')}
</tbody></table></div>
<h3>vLLM environment variables ({G['vllm_env']})</h3>
<div class="tw"><table class="full"><thead><tr><th>Variable</th><th>From</th><th>Last</th><th>Gone in</th></tr></thead><tbody>
{gone_rows('vllm_env')}
</tbody></table></div>
<h3>vLLM chat-completions request fields ({G['vllm_chat']}) and SamplingParams arguments ({G['vllm_sampling_params']})</h3>
<div class="tw"><table class="full"><thead><tr><th>Field</th><th>From</th><th>Last</th><th>Gone in</th></tr></thead><tbody>
{gone_rows('vllm_chat')}
{gone_rows('vllm_sampling_params').replace('<tr><td><code>', '<tr><td>SamplingParams <code>')}
</tbody></table></div>
<h3>SGLang server arguments ({G['sglang_cli']})</h3>
<div class="tw"><table class="full"><thead><tr><th>Argument</th><th>From</th><th>Last</th><th>Gone in</th></tr></thead><tbody>
{gone_rows('sglang_cli')}
</tbody></table></div>

<h2 id="method">How was this built?</h2>
<ul>
<li><strong>vLLM arguments:</strong> at each of {len(L['vllm_cli']['tags'])} final releases, every name in <code>add_argument(...)</code> in <code>vllm/engine/arg_utils.py</code> and the server's <code>cli_args.py</code> (under <code>entrypoints/openai/</code>, then <code>launchers/</code>, then <code>common/</code>), plus fields of the <code>FrontendArgs</code> dataclasses that become arguments.</li>
<li><strong>Environment variables:</strong> the keys of <code>environment_variables</code> in <code>vllm/envs.py</code>, {len(L['vllm_env']['tags'])} releases from v0.4.2.</li>
<li><strong>Request fields:</strong> the fields of <code>SamplingParams</code>, <code>ChatCompletionRequest</code> and <code>CompletionRequest</code> at each release.</li>
<li><strong>SGLang:</strong> <code>add_argument(...)</code> in <code>server_args.py</code>, and from v0.5.14 the annotated dataclass fields that generate arguments, {len(L['sglang_cli']['tags'])} releases.</li>
<li><strong>Replacements:</strong> read from the help text and source of the releases around each removal. Two are marked "probably": the move was not traced line by line.</li>
</ul>

<h2 id="limits">What this page does not cover</h2>
<ul>
<li>Release candidates and code on the main branch. An argument added after {VL} shows as "not in any release".</li>
<li>Values: an argument that still exists can change the values it accepts (for example a backend name). Only names are checked.</li>
<li>Variables read outside <code>vllm/envs.py</code>, SGLang's own <code>SGLANG_</code> variables, and SGLang's request fields.</li>
<li>Which releases accept <code>--no-X</code> for each switch is summarized in the note above, not checked per argument by the lookup.</li>
</ul>

<h2 id="faq">Questions</h2>
<dl>
{chr(10).join(f"<dt>{e(q)}</dt><dd>{e(a)}</dd>" for q, a in FAQ)}
</dl>

<p class="note">Related: <a href="/en/vllm-torch-cuda-driver-matrix/">vLLM compatibility matrix: PyTorch, CUDA and driver by release</a> &middot; <a href="/en/model-arch-min-version/">Minimum vLLM version for a model</a> &middot; <a href="/en/vllm-structured-output-backend-cost/">vLLM structured output backends</a>.</p>

<h2 id="sources">Sources</h2>
<ul>
<li>vLLM: <a href="https://github.com/vllm-project/vllm/blob/{VL}/vllm/engine/arg_utils.py">engine/arg_utils.py</a>, <a href="https://github.com/vllm-project/vllm/blob/{VL}/vllm/envs.py">envs.py</a>, <a href="https://github.com/vllm-project/vllm/blob/{VL}/vllm/entrypoints/serve/engine/protocol.py">entrypoints/serve/engine/protocol.py</a>, <a href="https://github.com/vllm-project/vllm/blob/{VL}/vllm/utils/argparse_utils.py">utils/argparse_utils.py</a>, <a href="https://github.com/vllm-project/vllm/releases">releases</a></li>
<li>SGLang: <a href="https://github.com/sgl-project/sglang/blob/{SG}/python/sglang/srt/server_args.py">server_args.py</a>, <a href="https://github.com/sgl-project/sglang/tree/{SG}/python/sglang/srt/arg_groups/fields">arg_groups/fields</a></li>
<li>Reports: <a href="https://discuss.vllm.ai/t/vllm-error-unrecognized-arguments-no-enable-chunked-prefill/1183">unrecognized arguments: --no-enable-chunked-prefill</a></li>
</ul>
</main>"""
data = {"libs": L, "hints": hints}
CSS = open(os.path.join(S, "style.css")).read(); JS = open(os.path.join(S, "tool.js")).read()
doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(TITLE)}</title>
<meta name="description" content="{e(DESC)}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESC)}">
<meta property="og:url" content="{URL}">
<script type="application/ld+json">{json.dumps(LD, ensure_ascii=True)}</script>
<style>
{CSS}
h3{{font-size:1.05rem;margin:1.4em 0 .3em}}
select{{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}}
#res td{{overflow-wrap:anywhere}}
</style>
</head>
<body>
{body}
<script type="application/json" id="rf-data">{json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")}</script>
<script>
{JS}</script>
</body>
</html>
"""
assert doc.isascii()
os.makedirs(OUT, exist_ok=True); open(os.path.join(OUT, "index.html"), "w").write(doc)
print("index.html", len(doc), "removed:", G, "req", len(req_gone))
