"""Build /en/generation-stop-tokens-check/: index.html + jinja-0.5.13.js.
Usage: python3 build_page.py out/llama_eog.json out/tmpl_markers.txt scripts OUTDIR PUBLISHED MODIFIED"""
import json, sys, html, os, re
LL = json.load(open(sys.argv[1])); TM = open(sys.argv[2], encoding="utf-8").read(); S = sys.argv[3]; OUT, PUB, MOD = sys.argv[4:7]
URL = "https://erimaki-kobo.github.io/en/generation-stop-tokens-check/"
e = lambda s: html.escape(str(s), quote=True).encode("ascii", "xmlcharrefreplace").decode()
c = lambda s: f"<code>{e(s)}</code>"
F = LL["first"]
# facts used in prose
assert F["<|eot_id|>"][0] == "2702" and F["<|im_end|>"][0] == "2714" and F["<turn|>"][0] == "8637" and F["<eos>"][0] == "8717"
assert LL["tag"] == "b12352" and len(LL["eog"]) == 24

# real templates from llama.cpp models/templates
rows = []
for l in TM.splitlines():
    if not l.strip() or l.startswith("{"): continue
    f, m = l[:52].strip().replace(".jinja", ""), l[53:79].strip().replace(" [harmony]", "")
    rows.append((f, m))
n_t = len(rows); n_ok = sum(1 for f, m in rows if m not in ("-", "(none)")); n_none = sum(1 for f, m in rows if m == "(none)"); n_err = sum(1 for f, m in rows if m == "-")
assert (n_t, n_ok, n_none, n_err) == (74, 59, 9, 6), (n_t, n_ok, n_none, n_err)
known = set(LL["eog"]) | set(LL["eot"]) | set(LL["eom"])
by = {}
for f, m in rows:
    if m in ("-", "(none)"): continue
    by.setdefault(m, []).append(f)
mk_rows = []
n_unknown_t = 0
for m, fs in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    inl = m in known
    if not inl: n_unknown_t += len(fs)
    fb = f"b{F[m][0]} ({F[m][1]})" + (" or earlier" if F[m][2] else "") if m in F else ""
    mk_rows.append(f"<tr><td>{c(m)}</td><td>{len(fs)}</td><td>{e(', '.join(fs))}</td><td>{'yes, from ' + fb if inl else '<strong>no</strong>: needs eos/eot in the GGUF'}</td></tr>")
n_unknown_m = sum(1 for m in by if m not in known)

REAL = json.load(open(os.path.join(os.path.dirname(sys.argv[1]), "real.json")))
assert len(REAL) == 14
qq = [r for r in REAL if r["model"] == "Qwen/Qwen3.5-4B"][0]
assert qq["gen"] == "missing" and qq["v"]["transformers"] == "runs-on" and qq["v"]["vllm"] == "stops"
VW = {"stops": '<span class="s y">stops</span>', "runs-on": '<span class="s n">runs on</span>', "no-marker": "&mdash;"}
real_rows = []
for r in REAL:
    real_rows.append("<tr><td>" + e(r["model"]) + "</td><td>" + (c(r["marker"]) if r["marker"] else "nothing") + "</td><td>" + r["gen"] + "</td>" + "".join("<td>" + VW[r["v"][k]] + "</td>" for k in ["transformers", "vllm", "sglang", "llamacpp", "mlx"]) + "</tr>")
first_rows = []
for t, (b, d, early) in sorted(F.items(), key=lambda kv: (int(kv[1][0]), kv[0])):
    first_rows.append(f"<tr><td>{c(t)}</td><td>b{b}{' or earlier' if early else ''}</td><td>{d}</td></tr>")

TITLE = "Model Doesn't Stop Generating? Check Stop Tokens per Engine"
DESC = "Paste a model's files or Hugging Face id: see the token that ends a chat turn and whether Transformers, vLLM, SGLang, llama.cpp, Ollama, MLX stop on it."
assert len(TITLE) <= 62 and len(DESC) <= 160, (len(TITLE), len(DESC))
H1 = "Why does my model not stop generating? The end-of-turn token, and which engines stop on it"
FAQ = [
 ("Why does Llama 3 Instruct keep generating after <|eot_id|>?", "Its tokenizer's eos_token is <|end_of_text|>, while a chat turn ends with <|eot_id|>. The second one is only listed in generation_config.json (eos_token_id [128001, 128009]). An engine or copy of the model that does not read that list stops only at <|end_of_text|>, which the model rarely emits in chat. vLLM reads it from v0.4.1."),
 ("Which file decides where generation stops?", "It depends on the engine. Transformers' generate() uses generation_config.json (or config.json when that file is missing) and ignores the tokenizer's eos_token. vLLM adds the tokenizer's eos_token to that. SGLang adds config.json as well. llama.cpp uses the eos, eot and eom ids stored in the GGUF plus a built-in list of token texts. Ollama passes stop strings from the Modelfile to llama.cpp."),
 ("How do I make vLLM stop on a token?", "Send \"stop_token_ids\": [ID] in the request, or start vLLM with --generation-config pointing at a directory whose generation_config.json lists the id in eos_token_id."),
 ("How do I make llama.cpp or Ollama stop on a token?", "For llama.cpp, --override-kv tokenizer.ggml.eos_token_id=int:ID makes that token the eos, and the eos is always in the end-of-generation set. For Ollama, add PARAMETER stop \"<token>\" to the Modelfile and run ollama create."),
 ("My fine-tuned model never stops, but the base model does. Why?", "If the training examples did not end with the end-of-turn or eos token, the model never learned to emit it. No engine setting fixes that; add the token to the end of every training example and train again."),
]
LD = {"@context": "https://schema.org", "@graph": [
 {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD, "inLanguage": "en",
  "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"}, "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
  "about": ["eos_token_id", "generation_config.json", "chat template", "vLLM", "llama.cpp", "Ollama", "SGLang", "MLX-LM", "Hugging Face Transformers"]},
 {"@type": "WebApplication", "@id": URL + "#tool", "name": "Stop token checker for LLM inference engines", "url": URL + "#check", "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (runs in the browser)", "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "description": "Reads config.json, generation_config.json, tokenizer_config.json and the chat template; shows the end-of-turn token and whether each engine stops on it."},
 {"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}]}

ENG = [
 ("Transformers <code>generate()</code>", "v5.22.2", "<code>eos_token_id</code> of generation_config.json. Without that file, the one in config.json (top level, else <code>text_config</code>). The tokenizer's <code>eos_token</code> is not added.", "If generation_config.json exists but has no <code>eos_token_id</code>, there is no end token at all."),
 ("vLLM", "v0.33.0", "The tokenizer's <code>eos_token</code>, plus <code>eos_token_id</code> of generation_config.json (or of config.json when that file is missing), plus the request's <code>stop_token_ids</code>.", "<code>--generation-config vllm</code> drops the sampling defaults, not these tokens. <code>ignore_eos</code> turns the end tokens off."),
 ("SGLang", "v0.5.23", "<code>eos_token_id</code> of config.json (top level) and of generation_config.json, the tokenizer's <code>eos_token</code>, three built-in extras when the vocabulary has them (" + ", ".join(c(x) for x in ["<|eom_id|>", "<|content_model_end_sampling|>", "<|ifm|im_end|>"]) + "), and the request's <code>stop_token_ids</code>.", "The widest net of the six."),
 ("llama.cpp", LL["tag"], "The end-of-generation (EOG) set: the GGUF's eos, eot and eom ids, the FIM pad, repo and separator tokens, and every vocabulary token whose text is in a built-in list (" + str(len(LL["eog"])) + " texts in " + LL["tag"] + ").", "Two exceptions remove tokens again: <code>&lt;|end|&gt;</code> when <code>&lt;|return|&gt;</code> and <code>&lt;|call|&gt;</code> exist (gpt-oss), and <code>&lt;/s&gt;</code> for Gemma 4, PLaMo and Beam."),
 ("Ollama", "v0.40.16", "llama.cpp's EOG set from the GGUF (Ollama runs <code>llama-server</code> and passes the request on), plus the <code>stop</code> strings from the Modelfile and the request.", "The EOG list is that of the llama.cpp build Ollama bundles; the <a href=\"/en/gguf-arch-min-build-lookup/#ollama\">GGUF lookup</a> lists it per release."),
 ("MLX-LM", "v0.32.2", "<code>eos_token_id</code> of config.json (top level), replaced by the one in generation_config.json when that is set, plus the tokenizer's <code>eos_token</code>.", "<code>--extra-eos-token</code> adds more."),
]
eng_rows = "\n".join(f"<tr><td>{n}</td><td>{v}</td><td>{a}</td><td>{b}</td></tr>" for n, v, a, b in ENG)

body = f"""<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>{e(H1)}</h1>
<p class="lede"><strong>A chat model ends its answer with one special token, written by its chat template: <code>&lt;|eot_id|&gt;</code> for Llama 3, <code>&lt;|im_end|&gt;</code> for Qwen, <code>&lt;end_of_turn&gt;</code> for Gemma 2 and 3, <code>&lt;turn|&gt;</code> for Gemma 4. Generation stops only if the engine counts that token as an end token, and each engine builds that set from different files.</strong> Transformers reads generation_config.json, vLLM adds the tokenizer's eos_token, llama.cpp reads the GGUF and a list of {len(LL['eog'])} built-in token texts, and Ollama adds the Modelfile's stop strings. Paste a model's files below to see where each engine stops.</p>
<p class="meta">Published {PUB} &middot; Rules read from Transformers v5.22.2, vLLM v0.33.0, SGLang v0.5.23, MLX-LM v0.32.2, llama.cpp {LL['tag']} and Ollama v0.40.16 &middot; no model was run</p>

<h2 id="check">Which engines will stop on my model's end-of-turn token?</h2>
<p>Fetch a public model from Hugging Face, or paste its files. For a GGUF, paste the lines that llama.cpp prints while loading (they start with <code>printing all EOG tokens</code>) to replace the prediction with the real set.</p>
<div class="card">
<label for="hf">Hugging Face model id</label>
<div class="row" style="margin-top:0"><input id="hf" placeholder="Qwen/Qwen3-8B" autocomplete="off" style="max-width:360px"><button id="fetch" type="button">Fetch files</button><span id="fstatus" class="note"></span></div>
<div class="grid" style="margin-top:12px">
<div><label for="cfg">config.json</label><textarea id="cfg" spellcheck="false" placeholder='{{"eos_token_id": 128001, ...}}'></textarea></div>
<div><label for="gen">generation_config.json (if the model has one)</label><textarea id="gen" spellcheck="false" placeholder='{{"eos_token_id": [128001, 128009]}}'></textarea></div>
<div><label for="tok">tokenizer_config.json</label><textarea id="tok" spellcheck="false" placeholder='{{"eos_token": "&lt;|end_of_text|&gt;", "added_tokens_decoder": ...}}'></textarea></div>
<div><label for="tmpl">chat_template.jinja (if it is a separate file)</label><textarea id="tmpl" spellcheck="false"></textarea></div>
<div><label for="log">llama.cpp load log (optional)</label><textarea id="log" spellcheck="false" placeholder="load: printing all EOG tokens:&#10;load:   - 128009 ('&lt;|eot_id|&gt;')"></textarea></div>
<div><label for="mf">Ollama Modelfile (optional: <code>ollama show --modelfile NAME</code>)</label><textarea id="mf" spellcheck="false" placeholder='PARAMETER stop "&lt;|im_end|&gt;"'></textarea></div>
<div><label for="lb">Your llama.cpp build (optional)</label><input id="lb" placeholder="b5000" autocomplete="off"></div>
<div><label for="ov">Your Ollama version (optional)</label><input id="ov" placeholder="0.24.0" autocomplete="off"></div>
<div><label for="marker">End-of-turn token, if the template cannot be read (optional)</label><input id="marker" placeholder="&lt;|im_end|&gt;" autocomplete="off"></div>
</div>
<div class="row"><button id="go" type="button">Check</button><span id="status" role="status"></span></div>
<div id="res" aria-live="polite"></div>
</div>
<p class="note">Runs in your browser. Only the Fetch button contacts huggingface.co, for the four small files and, if needed, tokenizer.json. Gated models (Llama, Gemma) have to be pasted. The chat template is rendered with <a href="https://github.com/huggingface/huggingface.js/tree/main/packages/jinja">@huggingface/jinja</a> 0.5.13, the renderer Transformers.js uses.</p>

<h2 id="engines">Where does each engine get its end tokens?</h2>
<p><strong>Six engines, six rules. The same model files can stop in one engine and run on in another.</strong> Each row was read from the source of the release named.</p>
<div class="tw wide"><table id="eng">
<thead><tr><th>Engine</th><th>Read at</th><th>Tokens that end generation</th><th>Watch out for</th></tr></thead>
<tbody>
{eng_rows}
</tbody></table></div>

<h2 id="models">What does the checker say about popular models?</h2>
<p><strong>{len(REAL) - 1} of {len(REAL)} public models stop correctly in all six engines by these rules. The exception is <code>Qwen/Qwen3.5-4B</code>: its repository has no generation_config.json, and its config.json lists only <code>&lt;|endoftext|&gt;</code> (248044, inside <code>text_config</code>), so Transformers' <code>generate()</code> would not stop at <code>&lt;|im_end|&gt;</code>.</strong> vLLM, SGLang and MLX-LM still stop there because they add the tokenizer's <code>eos_token</code>, which is <code>&lt;|im_end|&gt;</code>. The 27B model of the same family ships a generation_config.json with both ids.</p>
<div class="tw wide"><table id="real">
<thead><tr><th>Model</th><th>Turn ends with</th><th>generation_config.json</th><th>Transformers</th><th>vLLM</th><th>SGLang</th><th>llama.cpp (predicted)</th><th>MLX-LM</th></tr></thead>
<tbody>
{chr(10).join(real_rows)}
</tbody></table></div>
<p class="note">Files fetched from Hugging Face on 2026-11-13. Gated models were read from Unsloth's public copies, whose files can differ from the originals (Unsloth's Llama 3 copy, for example, sets the tokenizer's eos to <code>&lt;|eot_id|&gt;</code>). GLM-4.6's template writes nothing after the answer; the model ends with <code>&lt;|user|&gt;</code> or <code>&lt;|observation|&gt;</code>, which its config lists. The Ollama column is the same as llama.cpp here and is left out. No model was run.</p>

<h2 id="mismatch">What are the usual reasons a model does not stop?</h2>
<div class="tw"><table>
<thead><tr><th>Symptom</th><th>Cause</th><th>Fix</th></tr></thead>
<tbody>
<tr><td>Llama 3 Instruct runs past <code>&lt;|eot_id|&gt;</code></td><td>The tokenizer's eos is <code>&lt;|end_of_text|&gt;</code>; <code>&lt;|eot_id|&gt;</code> (128009) is listed only in generation_config.json. Engines or copies without that list stop only at <code>&lt;|end_of_text|&gt;</code>.</td><td>An engine that reads generation_config.json (vLLM from v0.4.1), or <code>stop_token_ids=[128009]</code></td></tr>
<tr><td>Only the quantized or converted copy runs on</td><td>The uploader copied an older generation_config.json or tokenizer_config.json</td><td>Compare its files with the original model's in the checker above</td></tr>
<tr><td>Only llama.cpp or Ollama runs on</td><td>The GGUF's eos/eot ids point elsewhere and the end token is not in the built-in list of your build (see the table below)</td><td>A newer build, a GGUF converted with a newer llama.cpp, or <code>--override-kv</code></td></tr>
<tr><td>Only Ollama runs on</td><td>A model imported with a hand-written Modelfile lacks <code>PARAMETER stop</code></td><td>Add the stop string and <code>ollama create</code> again</td></tr>
<tr><td>A fine-tuned model runs on everywhere</td><td>The training examples did not end with the end-of-turn token</td><td>Fix the training data; no engine setting helps</td></tr>
</tbody></table></div>

<h2 id="templates">Which end-of-turn tokens does llama.cpp recognize by name?</h2>
<p><strong>Of the {n_t} chat templates that llama.cpp keeps for its tests, {n_ok} end the assistant's turn with a token, {n_none} write nothing after it, and {n_err} could not be rendered with a simple conversation.</strong> {n_unknown_m} of the end tokens found are not in llama.cpp's built-in list; for those {n_unknown_t} templates, llama.cpp stops only if the GGUF's eos or eot id points at the token, so the converter has to get it right.</p>
<div class="tw"><table>
<thead><tr><th>End-of-turn token</th><th>Templates</th><th>Which</th><th>In llama.cpp's built-in list?</th></tr></thead>
<tbody>
{chr(10).join(mk_rows)}
</tbody></table></div>
<p class="note">"Writes nothing after it" means the template relies on the model emitting an eos token (GLM and Apertus, for example). Rendering used one user and one assistant message; templates that require tools or special content fields failed and are counted as not rendered.</p>

<h3 id="history">From which llama.cpp build is each text in the list?</h3>
<p>The first <code>bNNNN</code> release whose vocabulary code compares token texts against each name. A GGUF whose eos or eot id already points at the token stops in older builds too; before b2702 (2024-04-21) there was no end-of-generation set at all, only the eos id.</p>
<div class="tw"><table>
<thead><tr><th>Token text</th><th>Named from</th><th>Date</th></tr></thead>
<tbody>
{chr(10).join(first_rows)}
</tbody></table></div>
<p class="note">b2702 compared against <code>&lt;|im_emd|&gt;</code>, a typo; <code>&lt;|im_end|&gt;</code> arrived in b2714 the next day.</p>

<h2 id="method">How was this built?</h2>
<ul>
<li><strong>Engine rules:</strong> read from <code>generation/utils.py</code> and <code>generation/configuration_utils.py</code> (Transformers v5.22.2), <code>sampling_params.py</code>, <code>v1/engine/input_processor.py</code> and <code>transformers_utils/config.py</code> (vLLM v0.33.0), <code>configs/model_config.py</code>, <code>managers/schedule_batch.py</code> and <code>utils/hf_transformers/common.py</code> (SGLang v0.5.23), <code>utils.py</code> and <code>tokenizer_utils.py</code> (MLX-LM v0.32.2), <code>src/llama-vocab.cpp</code> and <code>gguf-py/gguf/vocab.py</code> (llama.cpp {LL['tag']}), <code>llm/llama_server.go</code> (Ollama v0.40.16).</li>
<li><strong>llama.cpp lists:</strong> the token texts compared in <code>src/llama-vocab.cpp</code> at {LL['tag']}, extracted by a script; the first build for each by binary search over the release tags.</li>
<li><strong>Predicted GGUF ids:</strong> without a load log, the checker takes the eos the converter would write (tokenizer_config.json's <code>eos_token</code>, else config.json's <code>eos_token_id</code>). Some converters set eot or eom as well, which only adds tokens.</li>
<li><strong>Templates:</strong> llama.cpp's <code>models/templates</code> at {LL['tag']}, rendered with @huggingface/jinja 0.5.13.</li>
</ul>

<h2 id="limits">What this page does not cover</h2>
<ul>
<li>No model was run. The checker reports which tokens each engine treats as the end; whether the model emits that token is up to its weights.</li>
<li>Stop strings in requests (<code>stop</code>) are matched on text and work in every engine; they are not part of the table.</li>
<li>Older releases of Transformers, vLLM, SGLang and MLX-LM may differ; vLLM began reading <code>eos_token_id</code> from generation_config.json in v0.4.1 (2024-04).</li>
<li>Ollama's MLX runner on macOS and its older own engine (0.5.12 to 0.31.1) are not covered.</li>
</ul>

<h2 id="faq">Questions</h2>
<dl>
{chr(10).join(f"<dt>{e(q)}</dt><dd>{e(a)}</dd>" for q, a in FAQ)}
</dl>

<p class="note">Related: <a href="/en/model-arch-min-version/">Minimum Transformers, vLLM and llama.cpp version for a model</a> &middot; <a href="/en/gguf-arch-min-build-lookup/">GGUF architecture lookup</a> &middot; <a href="/en/engine-logprob-parity-check/">Why logprobs differ between engines</a>.</p>

<h2 id="sources">Sources</h2>
<ul>
<li>Transformers: <a href="https://github.com/huggingface/transformers/blob/v5.22.2/src/transformers/generation/utils.py">generation/utils.py</a>, <a href="https://github.com/huggingface/transformers/blob/v5.22.2/src/transformers/generation/configuration_utils.py">configuration_utils.py</a></li>
<li>vLLM: <a href="https://github.com/vllm-project/vllm/blob/v0.33.0/vllm/sampling_params.py">sampling_params.py</a>, <a href="https://github.com/vllm-project/vllm/blob/v0.33.0/vllm/transformers_utils/config.py">transformers_utils/config.py</a>, PR <a href="https://github.com/vllm-project/vllm/pull/4182">#4182</a>, issue <a href="https://github.com/vllm-project/vllm/issues/4180">#4180</a></li>
<li>SGLang: <a href="https://github.com/sgl-project/sglang/blob/v0.5.23/python/sglang/srt/configs/model_config.py">model_config.py</a>, <a href="https://github.com/sgl-project/sglang/blob/v0.5.23/python/sglang/srt/managers/schedule_batch.py">schedule_batch.py</a></li>
<li>llama.cpp: <a href="https://github.com/ggml-org/llama.cpp/blob/{LL['tag']}/src/llama-vocab.cpp">src/llama-vocab.cpp</a>, <a href="https://github.com/ggml-org/llama.cpp/tree/{LL['tag']}/models/templates">models/templates</a>, issue <a href="https://github.com/ggml-org/llama.cpp/issues/9606">#9606</a></li>
<li>MLX-LM: <a href="https://github.com/ml-explore/mlx-lm/blob/v0.32.2/mlx_lm/tokenizer_utils.py">tokenizer_utils.py</a>; Ollama: <a href="https://github.com/ollama/ollama/blob/v0.40.16/llm/llama_server.go">llm/llama_server.go</a>, <a href="https://github.com/ollama/ollama/blob/main/docs/modelfile.mdx">Modelfile</a></li>
<li>Reports: <a href="https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct/discussions/26">Meta-Llama-3-8B-Instruct #26</a>, <a href="https://huggingface.co/turboderp/Llama-3-8B-Instruct-exl2/discussions/1">exl2 thread</a>, <a href="https://forgather.readthedocs.io/en/latest/guides/eos-and-generate-stopping/">forgather: eos and generate stopping</a></li>
</ul>
</main>"""

ll_data = json.dumps(LL, ensure_ascii=True, separators=(",", ":"))
SC = open(os.path.join(S, "stopcheck.js")).read(); UI = open(os.path.join(S, "ui.js")).read(); CSS = open(os.path.join(S, "style.css")).read()
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
#eng{{min-width:820px}}
#res td{{overflow-wrap:anywhere}}
.grid textarea{{min-height:90px}}
</style>
</head>
<body>
{body}
<script type="application/json" id="ll-data">{ll_data}</script>
<script>
{SC}</script>
<script>
{UI}</script>
</body>
</html>
"""
assert doc.isascii(), [ch for ch in doc if not ch.isascii()][:5]
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "index.html"), "w").write(doc)
J = open(os.path.join(S, "jinja-0.5.13.js"), encoding="utf-8").read()
open(os.path.join(OUT, "jinja-0.5.13.js"), "w", encoding="utf-8").write("/*! @huggingface/jinja 0.5.13, MIT License, Copyright (c) Hugging Face. https://github.com/huggingface/huggingface.js */\n" + J)
print("index.html", len(doc))
