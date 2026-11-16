"""Build en/vllm-sm120-moe-backend-lookup/index.html from data.json and tool.js.
usage: python3 build_page.py <data.json> <out index.html> [published YYYY-MM-DD] [modified YYYY-MM-DD]"""
import json, html, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(sys.argv[1])); S = D["S"]
OUT = sys.argv[2]
PUBLISHED = sys.argv[3] if len(sys.argv) > 3 else "2026-11-15"
MODIFIED = sys.argv[4] if len(sys.argv) > 4 else PUBLISHED
TAGS = [t for t, _ in D["tags"]]
FIRST = TAGS[0]; LATEST = TAGS[-1]; LATEST_DATE = D["tags"][-1][1]
SCEN = [
    ("nvfp4", "NVFP4"),
    ("fp8_block", "FP8 block 128x128"),
    ("fp8_tensor", "FP8 per-tensor, dynamic act."),
    ("ct_fp8_channel", "FP8 per-channel / per-token (compressed-tensors)"),
    ("ct_fp8_tensor_static", "FP8 per-tensor, static act. (compressed-tensors)"),
    ("modelopt_fp8", "FP8 per-tensor, static act. (ModelOpt, fp8)"),
    ("mxfp4_gptoss", "MXFP4 (gpt-oss)"),
]
def e(x): return html.escape(str(x))
def rec(t, c, s): return D["r"].get(f"{t}|{c}|{s}")
def name(r):
    if r is None: return "-"
    return "(error)" if "e" in r else S[r["b"]]
def ranges(c, s):
    seq = []
    for t in TAGS:
        v = name(rec(t, c, s))
        if seq and seq[-1][1] == v: seq[-1][2] = t
        else: seq.append([t, v, t])
    return seq
def hist_cell(c, s):
    parts = []
    for a, v, b in ranges(c, s):
        span = a if a == b else f"{a}&ndash;{b}"
        parts.append(f"<code>{e(v)}</code> <span class='mut'>{span}</span>")
    return "<br>".join(parts)
def usable(t, c, s):
    r = rec(t, c, s)
    if not r or "e" in r: return []
    cand = D["CT"][r["c"]]
    return [S[int(k)] for k, v in cand.items() if S[v] == "ok"]

# ---- claims made in the prose; stop the build if the data no longer supports them ----
def auto(t, c, s): return name(rec(t, c, s))
for c in (120, 121):
    assert auto(LATEST, c, "nvfp4") == "FLASHINFER_CUTLASS"
    for s in ("fp8_block", "fp8_tensor", "ct_fp8_channel"): assert auto(LATEST, c, s) == "TRITON", s
    for s in ("ct_fp8_tensor_static", "modelopt_fp8"): assert auto(LATEST, c, s) == "FLASHINFER_CUTLASS", s
    assert auto(LATEST, c, "mxfp4_gptoss") == "MARLIN"
    assert auto("v0.15.0", c, "nvfp4") == "VLLM_CUTLASS" and auto("v0.15.1", c, "nvfp4") == "FLASHINFER_CUTLASS"
for t in TAGS:
    for s, _ in SCEN:
        assert auto(t, 120, s) == auto(t, 121, s), (t, s)          # "SM120 and SM121 are the same"
        if t != "v0.15.0": assert auto(t, 120, s) == auto(LATEST, 120, s), (t, s)   # "the one break is v0.15.0 to v0.15.1"
    assert "MARLIN" in usable(t, 120, "nvfp4"), t                   # "Marlin passes the checks in every release"
    if t != "v0.15.0":
        for s, _ in SCEN: assert "VLLM_CUTLASS" not in usable(t, 120, s) or s == "nvfp4", (t, s)   # FP8 VLLM_CUTLASS never usable on SM12x
assert D["flag"][0] == "v0.17.0"

rows = []
for s, lab in SCEN:
    r120 = name(rec(LATEST, 120, s)); r121 = name(rec(LATEST, 121, s))
    u = ", ".join(f"<code>{e(x)}</code>" for x in usable(LATEST, 120, s)) or "<span class='mut'>n/a</span>"
    rows.append(f"<tr><td>{e(lab)}</td><td><code>{e(r120)}</code></td><td><code>{e(r121)}</code></td><td>{u}</td></tr>")
latest_table = "\n".join(rows)
hist_rows = "\n".join(f"<tr><td>{e(lab)}</td><td>{hist_cell(120, s)}</td><td>{hist_cell(121, s)}</td></tr>" for s, lab in SCEN)
other_rows = []
for c, g in ((100, "SM100 (B200)"), (90, "SM90 (H100)"), (89, "SM89 (RTX 40, L40S)"), (80, "SM80 (A100)")):
    other_rows.append("<tr><td>" + e(g) + "</td>" + "".join(f"<td><code>{e(name(rec(LATEST, c, s)))}</code></td>" for s, _ in SCEN) + "</tr>")
other_head = "".join(f"<th>{e(l)}</th>" for _, l in SCEN)

TITLE = "vLLM MoE Backend on SM120 (RTX 50): NVFP4, FP8, MXFP4"
H1 = "Which MoE backend does vLLM use on RTX 50, RTX PRO 6000 and DGX Spark (SM120/SM121)?"
DESC = (f"Which MoE kernel vLLM picks on RTX 50, RTX PRO 6000 and DGX Spark (SM120/SM121) for NVFP4, FP8 and MXFP4, "
        f"and what --moe-backend can force, {FIRST} to {LATEST}.")
assert len(TITLE) <= 60 and len(DESC) <= 160, (len(TITLE), len(DESC))
URL = "https://erimaki-kobo.github.io/en/vllm-sm120-moe-backend-lookup/"
ORG = {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}

FAQ = [
    ("What does \"MoE backend ... does not support the deployment configuration\" mean in vLLM?",
     "A backend was forced with <code>--moe-backend</code> (or, before v0.24.0, with <code>VLLM_USE_FLASHINFER_MOE_FP4</code> / <code>VLLM_FLASHINFER_MOE_BACKEND</code>) and that backend rejected this GPU or checkpoint. In auto mode the same rejection is only a DEBUG log and vLLM tries the next backend. Remove the flag or variable, or force a backend that passes the checks, such as <code>marlin</code>."),
    ("Should I force <code>--moe-backend marlin</code> on an RTX 5090 for NVFP4?",
     f"If the default <code>FLASHINFER_CUTLASS</code> fails to start or produces garbage, the public report above used Marlin as the working path. Marlin runs NVFP4 weights with 16-bit activations, so it is a weight-only path. It passes vLLM's checks on SM120 in every release from {FIRST}."),
    ("Why does <code>VLLM_NVFP4_GEMM_BACKEND</code> do nothing for my MoE model?",
     "It chose the kernel for dense (linear) NVFP4 layers, not MoE layers. It existed from v0.11.1 to v0.23.0, was deprecated in v0.22.0 with the message \"Use --linear-backend.\", and is not in <code>vllm/envs.py</code> from v0.24.0. MoE layers follow <code>--moe-backend</code>."),
    ("Is DGX Spark (SM121) different from RTX 50 (SM120)?",
     "Not for MoE selection: in every release and format here the automatic pick is the same for 12.0 and 12.1, because the checks use <code>is_device_capability_family(120)</code>."),
]
def plain(x): return html.unescape(re.sub(r"<[^>]+>", "", x))
faq_html = "\n".join(f"<h3>{q}</h3>\n<p>{a}</p>" for q, a in FAQ)
LD = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL,
     "datePublished": PUBLISHED, "dateModified": MODIFIED, "inLanguage": "en",
     "about": ["vLLM", "Mixture-of-Experts inference", "NVIDIA RTX 50 series (SM120)", "DGX Spark (SM121)", "NVFP4 and FP8 quantization"],
     "author": ORG, "publisher": ORG, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "@id": URL + "#tool", "name": "vLLM MoE backend lookup", "url": URL + "#tool",
     "description": f"Shows which fused-MoE backend vLLM {FIRST} to {LATEST} selects for a GPU compute capability and checkpoint format, which backends pass vLLM's checks, and which --moe-backend value forces each.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "softwareVersion": "1.0.0", "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "publisher": ORG},
    {"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": [
        {"@type": "Question", "name": plain(q), "acceptedAnswer": {"@type": "Answer", "text": plain(a)}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
tool_js = open(os.path.join(HERE, "tool.js")).read()
assert "__D__" in tool_js

CSS = """:root{--bg:#fff;--fg:#1b1f24;--mut:#5b6470;--line:#d9dee4;--card:#f5f7f9;--acc:#0b5cad;--ok:#17703a;--no:#a33a1f;--pick:#fff7d6;--warn:#fff1e6}
@media (prefers-color-scheme:dark){:root{--bg:#14171b;--fg:#e6e9ed;--mut:#9aa4af;--line:#2d333b;--card:#1d2127;--acc:#6aaef5;--ok:#5cc985;--no:#f08b6e;--pick:#3a3418;--warn:#3b2a1d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.7rem;line-height:1.25;margin:.2em 0 .4em}h2{font-size:1.3rem;margin-top:2em}h3{font-size:1.05rem;margin-top:1.4em}
a{color:var(--acc);overflow-wrap:anywhere}code{font:0.88em ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--card);padding:1px 4px;border-radius:4px;word-break:break-word}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}table{border-collapse:collapse;width:100%;font-size:.92rem;margin:.6em 0}th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{background:var(--card)}
.mut{color:var(--mut);font-size:.9em}.ok{color:var(--ok)}.no{color:var(--no)}tr.pick td{background:var(--pick)}
.box{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:1em 0}
label{display:block;font-weight:600;margin:.6em 0 .2em}select,textarea{width:100%;font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}textarea{min-height:90px;font-family:ui-monospace,Menlo,monospace;font-size:.85rem}
button{font:inherit;margin-top:8px;padding:7px 14px;border:0;border-radius:6px;background:var(--acc);color:#fff;cursor:pointer}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}@media (max-width:720px){.grid{grid-template-columns:1fr}}
.res{border-left:4px solid var(--acc);padding:10px 12px;background:var(--bg);margin:12px 0}.res.bad{border-color:var(--no)}.res.warn{border-color:#d9822b;background:var(--warn)}
.big{font-size:1.4rem;font-weight:700;font-family:ui-monospace,Menlo,monospace}.k{color:var(--mut)}.log{margin-top:6px;font-size:.88rem}.note{font-size:.9rem;color:var(--mut)}
details{margin:.4em 0}summary{cursor:pointer;font-weight:600}"""

BODY = """<p class="mut"><a href="/en/">Answers for LLM inference engineers</a> &middot; data from vLLM @FIRST@ to @LATEST@ (@LATEST_DATE@) &middot; published @PUBLISHED@</p>
<h1>@H1@</h1>
<p><b>Short answer for vLLM @LATEST@:</b> on SM120 and SM121 the automatic choice is <code>FLASHINFER_CUTLASS</code> for NVFP4 MoE, <code>TRITON</code> for FP8 with block scales or dynamic activations, <code>FLASHINFER_CUTLASS</code> for FP8 with static per-tensor scales, and <code>MARLIN</code> for gpt-oss MXFP4. vLLM's own CUTLASS grouped FP8 kernel (<code>VLLM_CUTLASS</code>) is never usable on SM12x after v0.15.0: <code>cutlass_group_gemm_supported()</code> returns False for compute capability 11.0 and above. The error <code>... MoE backend 'X' does not support the deployment configuration</code> appears only when a backend was forced; in auto mode vLLM skips that backend with a DEBUG log and tries the next one.</p>

<h2 id="tool">Look up your GPU, checkpoint format and vLLM release</h2>
<div class="box">
<div class="grid">
<div><label for="gpu">GPU</label><select id="gpu"></select></div>
<div><label for="quant">Checkpoint format</label><select id="quant"></select></div>
<div><label for="ver">vLLM release</label><select id="ver"></select></div>
</div>
<details><summary>Or paste the model's config.json to detect the format</summary>
<textarea id="cfg" aria-label="config.json" placeholder='{"quantization_config": {"quant_method": "modelopt", "quant_algo": "NVFP4"}}'></textarea>
<button id="detbtn" type="button">Detect format</button> <span id="det"></span></details>
<details><summary>Or paste the error you got</summary>
<textarea id="err" aria-label="error message" placeholder="ValueError: NvFp4 MoE backend 'FLASHINFER_CUTLASS' does not support the deployment configuration since kernel does not support current device."></textarea>
<button id="errbtn" type="button">Explain</button><div id="errout"></div></details>
<div id="out"></div>
</div>
<p class="note">Every value here comes from running each release's own selection code (<code>vllm/model_executor/layers/fused_moe/oracle/</code>) with a simulated GPU, not from reading docs. Assumptions: the official pip wheel (FlashInfer installed, DeepGEMM not installed, the optional <code>b12x</code> package not installed, humming kernels installed from v0.22.0 when they became a dependency), one GPU (no tensor or expert parallel), no LoRA, BF16 activations, a Qwen3-MoE-like layer (128 experts, top-8, hidden 2048). See <a href="#method">how this was built</a>.</p>

<h2 id="latest">SM120 and SM121 in vLLM @LATEST@</h2>
<div class="tw"><table><thead><tr><th>Checkpoint format</th><th>Auto pick, SM120</th><th>Auto pick, SM121</th><th>Backends that pass vLLM's checks on SM120</th></tr></thead><tbody>
@latest_table@
</tbody></table></div>
<p class="note"><code>FLASHINFER_B12X</code> is never picked automatically; the code says it is excluded "until the upstream CUTLASS SM121 MMA op guard is resolved". Force it with <code>--moe-backend flashinfer_b12x</code>. <code>--moe-backend b12x</code> is a different backend that needs the separate <code>b12x</code> package (<code>vllm[b12x]</code>), so without it vLLM reports "kernel does not support current device".</p>

<h2 id="history">How the automatic pick changed, release by release</h2>
<div class="tw"><table><thead><tr><th>Format</th><th>SM120 (RTX 50, RTX PRO 6000)</th><th>SM121 (DGX Spark)</th></tr></thead><tbody>
@hist_rows@
</tbody></table></div>
<p>The one break is v0.15.0 to v0.15.1. In v0.15.0 the FlashInfer NVFP4 kernels only accepted SM90 and SM10x, so SM120 fell through to <code>VLLM_CUTLASS</code>, and anyone forcing FlashInfer got the error in <a href="https://github.com/vllm-project/vllm/issues/33416">#33416</a>. The fix, <a href="https://github.com/vllm-project/vllm/pull/33417">PR #33417</a>, first shipped in v0.15.1: it added <code>is_device_capability_family(120)</code> to <code>flashinfer_cutlass_moe.py</code>. The same release made <code>cutlass_group_gemm_supported()</code> return False for capability 11.0 and above, which moved FP8 per-channel models from <code>VLLM_CUTLASS</code> to <code>TRITON</code>.</p>

<h2 id="error">What "does not support the deployment configuration" means</h2>
<p><b>It means a backend was forced and that backend rejected this GPU or checkpoint.</b> Each selector builds a priority list, asks every kernel class <code>is_supported_config()</code>, and returns the first that passes. When nothing is forced, a rejection is logged at DEBUG level only. When you set <code>--moe-backend</code> (v0.17.0 and later) or, before v0.24.0, <code>VLLM_USE_FLASHINFER_MOE_FP4=1</code> together with <code>VLLM_FLASHINFER_MOE_BACKEND</code>, the same rejection is raised as a <code>ValueError</code>. These are the messages the @LATEST@ code produces on SM120 when forced:</p>
<div class="tw"><table><thead><tr><th>Forced</th><th>Format</th><th>Result on SM120, @LATEST@</th></tr></thead><tbody>
@forced_rows@
<tr><td><code>VLLM_USE_FLASHINFER_MOE_FP4=1</code> with <code>VLLM_FLASHINFER_MOE_BACKEND=throughput</code> on v0.15.0</td><td>NVFP4</td><td><code>@v0150_msg@</code> (the same variables and the same text as <a href="https://discuss.vllm.ai/t/running-nvfp4-nemotron-model-on-win11-wsl-rtx-5080-5070-ti/2310">this forum thread</a>; the text also appears in <a href="https://github.com/vllm-project/vllm/issues/33416">#33416</a>). Accepted from v0.15.1.</td></tr>
<tr><td><code>VLLM_USE_FLASHINFER_MOE_FP4=1</code> alone on v0.15.0</td><td>NVFP4</td><td><code>@v0150_alone@</code> Accepted from v0.15.1.</td></tr>
</tbody></table></div>
<p>To fix the error, remove the flag or variable and let auto pick, or choose a backend the tool marks <b>yes</b> for your GPU and release.</p>

<h2 id="works">Selected is not the same as working</h2>
<p>This page answers "which kernel will vLLM try". Whether that kernel then builds and produces correct output on SM12x is a separate question, and some public reports say it does not:</p>
<ul>
<li><b>NVFP4 on SM120.</b> A report from 4x RTX PRO 6000 describes grouped-GEMM initialization failures and garbage output from the native NVFP4 MoE kernels, with Marlin as the working path (<a href="https://discuss.vllm.ai/t/sm120-rtx-pro-6000-nvfp4-moe-performance-report-qwen3-5-397b/2536">forum report</a>).</li>
<li><b>FP8 on SM12x falls to <code>TRITON</code></b> because CUTLASS has no SM120/SM121 grouped-GEMM builder for tensor- or token-scaled FP8 (<a href="https://github.com/vllm-project/vllm/issues/43507">#43507</a>). That matches the code: <code>vllm/_custom_ops.py</code> returns False for capability 11.0 and above before calling the C++ check. The change proposed for it, PR #43814, is not in any release up to @LATEST@.</li>
<li><b><code>MARLIN</code> MoE</b> has a report of <code>CUDA error: an illegal memory access</code> under concurrent decode on RTX PRO 6000 with a W4A16 DeepSeek-V4-Flash checkpoint (<a href="https://github.com/vllm-project/vllm/pull/43730">PR #43730</a>, which proposes a fix and is not in any release up to @LATEST@).</li>
<li><b><code>VLLM_MOE_FORCE_MARLIN</code></b>, quoted in that forum report as the way to force Marlin, does not appear in the source tree of any vLLM release tag. Use <code>--moe-backend marlin</code>.</li>
</ul>
<p>None of these were run on a GPU for this page.</p>

<h2 id="env">Old environment variables that forced MoE backends</h2>
<div class="tw"><table><thead><tr><th>Variable</th><th>In <code>vllm/envs.py</code></th><th>Replacement</th></tr></thead><tbody>
<tr><td><code>VLLM_USE_FLASHINFER_MOE_FP4</code></td><td>v0.10.0 to v0.23.0, deprecated from v0.22.0</td><td><code>--moe-backend flashinfer_trtllm | flashinfer_cutlass | flashinfer_cutedsl</code></td></tr>
<tr><td><code>VLLM_USE_FLASHINFER_MOE_FP8</code></td><td>v0.10.0 to v0.23.0, deprecated from v0.22.0</td><td><code>--moe-backend flashinfer_trtllm | flashinfer_cutlass</code></td></tr>
<tr><td><code>VLLM_FLASHINFER_MOE_BACKEND</code></td><td>v0.10.1 to v0.23.0, deprecated from v0.22.0</td><td><code>--moe-backend flashinfer_trtllm | flashinfer_cutlass | flashinfer_cutedsl</code></td></tr>
<tr><td><code>VLLM_MXFP4_USE_MARLIN</code></td><td>v0.10.1 to v0.23.0, deprecated from v0.22.0</td><td><code>--moe-backend marlin</code></td></tr>
<tr><td><code>VLLM_TEST_FORCE_FP8_MARLIN</code></td><td>v0.5.5 to v0.28.0</td><td><code>--moe-backend marlin</code></td></tr>
<tr><td><code>VLLM_B12X_MOE_FP4_FORCE_A16</code></td><td>v0.29.0 to @LATEST@</td><td>(current) BF16 activations for the b12x FP4 MoE path</td></tr>
</tbody></table></div>
<p>The deprecation messages in v0.22.0 say these would go in v0.23; they were last present in v0.23.0. <code>--moe-backend</code> itself exists from v0.17.0. For every removed flag and variable, see <a href="/en/vllm-removed-flags-lookup/">the removed flags lookup</a>.</p>

<h2 id="other">Other GPUs in vLLM @LATEST@, for comparison</h2>
<div class="tw"><table><thead><tr><th>GPU</th>@other_head@</tr></thead><tbody>
@other_rows@
</tbody></table></div>

<h2 id="method">How this was built</h2>
<p>For each of the @NTAGS@ releases from @FIRST@ to @LATEST@ (the releases that have the <code>fused_moe/oracle/</code> selectors), the release's Python source was imported on a CPU machine with the compiled extensions stubbed out. <code>current_platform</code> was replaced by a CUDA platform that reports a chosen compute capability (8.0, 8.9, 9.0, 10.0, 10.3, 12.0, 12.1). Then the same selector the quantization method calls (<code>select_nvfp4_moe_backend</code>, <code>select_fp8_moe_backend</code>, <code>select_mxfp4_moe_backend</code> or, before v0.19.0, <code>get_mxfp4_backend</code>) was called with the weight and activation keys that method passes. The tool also asks every backend's kernel classes <code>is_supported_config()</code> and records the reason string vLLM itself produces. The scripts are in <a href="https://github.com/erimaki-kobo/erimaki-kobo.github.io/tree/main/.github/sm120-moe">this site's repository</a>.</p>
<p>Three things come from C++ in the real wheel and were re-implemented from the release's <code>csrc/</code>: <code>cutlass_group_gemm_supported</code> (SM90 needs CUDA 12.3, SM10x CUDA 12.8; the Python wrapper rejects capability below 9.0 or from 11.0 from v0.15.1), <code>mxfp4_experts_quant_supported</code> (10.0 to 11.9), and the dense FP8 checks, which do not affect MoE selection. All <code>has_flashinfer_*</code> checks were set to true (FlashInfer is a dependency of every release here). Check: setting the two environment variables from the forum thread on simulated SM120 in v0.15.0 reproduces the exact error text users posted.</p>
<p><b>Not covered:</b> unquantized BF16 MoE, INT4/INT8 MoE (AWQ, GPTQ, W4A16, W8A8-int), expert or tensor parallel (which change the activation format and the list), LoRA, <code>VLLM_BATCH_INVARIANT</code>, ROCm. Selection can still change at run time for unusual shapes ("Shape-specific fallbacks may still occur at runtime", in the selector's docstring). Nothing here was run on a GPU.</p>

<h2 id="faq">FAQ</h2>
@faq_html@

<h2 id="sources">Sources</h2>
<ul>
<li>vLLM source at each release tag: <a href="https://github.com/vllm-project/vllm/tree/@LATEST@/vllm/model_executor/layers/fused_moe/oracle">vllm/model_executor/layers/fused_moe/oracle/</a>, <a href="https://github.com/vllm-project/vllm/blob/@LATEST@/vllm/_custom_ops.py">vllm/_custom_ops.py</a>, <a href="https://github.com/vllm-project/vllm/blob/@LATEST@/csrc/quantization/w8a8/cutlass/scaled_mm_entry.cu">csrc/quantization/w8a8/cutlass/scaled_mm_entry.cu</a>, <a href="https://github.com/vllm-project/vllm/blob/@LATEST@/vllm/envs.py">vllm/envs.py</a>, <a href="https://github.com/vllm-project/vllm/blob/@LATEST@/docs/features/quantization/b12x.md">docs/features/quantization/b12x.md</a></li>
<li><a href="https://github.com/vllm-project/vllm/issues/43507">vLLM #43507: CUTLASS MoE backend unavailable on SM_120/SM_121 for tensor/token-scaled FP8 models</a></li>
<li><a href="https://github.com/vllm-project/vllm/issues/33416">vLLM #33416: NVFP4 MoE kernels fail on RTX Blackwell (SM12.0)</a> and <a href="https://github.com/vllm-project/vllm/pull/33417">PR #33417</a></li>
<li><a href="https://github.com/vllm-project/vllm/pull/43730">vLLM PR #43730: Fix CUDA illegal memory access in Marlin MoE on SM 12.0a</a></li>
<li><a href="https://discuss.vllm.ai/t/running-nvfp4-nemotron-model-on-win11-wsl-rtx-5080-5070-ti/2310">vLLM forum: Running NVFP4 Nemotron model on Win11/WSL RTX 5080 + 5070 Ti</a></li>
<li><a href="https://discuss.vllm.ai/t/sm120-rtx-pro-6000-nvfp4-moe-performance-report-qwen3-5-397b/2536">vLLM forum: SM120 (RTX PRO 6000) NVFP4 MoE Performance Report</a></li>
</ul>
<p class="mut">Related: <a href="/en/vllm-torch-cuda-driver-matrix/">vLLM PyTorch/CUDA/driver matrix</a> &middot; <a href="/en/vllm-removed-flags-lookup/">vLLM removed flags lookup</a> &middot; <a href="/en/vllm-kv-concurrency-planner/">vLLM KV cache planner</a> &middot; <a href="/en/triton-ptxas-arch-lookup/">Triton ptxas error on SM120/SM121 (sm_121a is not defined)</a></p>"""

# forced-backend messages: read from forced.json (made by forced.sh from real runs), never typed by hand
F = json.load(open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "forced.json")))
def fmsg(key):
    v = F[key]; assert v, key
    return v
def short(m):   # long QuantKey reasons are cut after the first key
    m = re.sub(r"^[A-Za-z]+Error: ", "", m)
    i = m.find(")x")
    return m if i < 0 or len(m) < 200 else m[:i + 2] + "..."
FORCED = [
    ("--moe-backend flashinfer_trtllm", "NVFP4", "flashinfer_trtllm|nvfp4", " (TRT-LLM kernels are SM10x only)"),
    ("--moe-backend cutlass", "FP8 block (quant_method fp8)", "cutlass|fp8_block", " (this code path passes <code>allow_vllm_cutlass=False</code>)"),
    ("--moe-backend cutlass", "FP8 per-channel (compressed-tensors)", "cutlass|ct_fp8_channel", ""),
    ("--moe-backend flashinfer_cutlass", "FP8 block", "flashinfer_cutlass|fp8_block", ""),
    ("--moe-backend b12x", "NVFP4 (without the b12x package)", "b12x|nvfp4", ""),
    ("--moe-backend b12x", "gpt-oss MXFP4", "b12x|mxfp4_gptoss", ""),
]
forced_rows = "\n".join(f"<tr><td><code>{e(a)}</code></td><td>{e(b)}</td><td><code>{e(short(fmsg(k)))}</code>{x}</td></tr>" for a, b, k, x in FORCED)
for s in ("nvfp4", "fp8_block", "ct_fp8_channel", "mxfp4_gptoss"): assert F["marlin|" + s] == "ok:MARLIN", s
forced_rows += "\n<tr><td><code>--moe-backend marlin</code></td><td>NVFP4, FP8, MXFP4</td><td>accepted (<code>MARLIN</code>)</td></tr>"
v0150 = re.sub(r"^[A-Za-z]+Error: ", "", fmsg("v0.15.0|env_fp4_throughput|nvfp4"))
v0150_alone = fmsg("v0.15.0|env_fp4|nvfp4")
assert v0150_alone.startswith("NotImplementedError: Found VLLM_USE_FLASHINFER_MOE_FP4=1"), v0150_alone
for k in ("env_fp4", "env_fp4_throughput", "env_fp4_latency"): assert F[f"v0.15.1|{k}|nvfp4"] == "ok:FLASHINFER_CUTLASS", k
assert v0150 == "NvFp4 MoE backend 'FLASHINFER_CUTLASS' does not support the deployment configuration since kernel does not support current device.", v0150

subs = {"FIRST": e(FIRST), "LATEST": e(LATEST), "LATEST_DATE": e(LATEST_DATE), "PUBLISHED": e(PUBLISHED), "H1": e(H1),
        "latest_table": latest_table, "hist_rows": hist_rows, "other_head": other_head, "other_rows": "".join(other_rows),
        "NTAGS": str(len(TAGS)), "faq_html": faq_html, "forced_rows": forced_rows, "v0150_msg": e(v0150), "v0150_alone": e(v0150_alone)}
body = BODY
for k, v in subs.items(): body = body.replace("@" + k + "@", v)
assert not re.search(r"@[A-Za-z_0-9]+@", body), re.findall(r"@[A-Za-z_0-9]+@", body)

page = f"""<!DOCTYPE html>
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
<script type="application/ld+json">{json.dumps(LD).replace("</", "<\\/")}</script>
<style>
{CSS}
</style>
</head>
<body><main>
{body}
</main>
<script>
var __D__ = {json.dumps(D, separators=(",", ":")).replace("</", "<\\/")};
{tool_js}
</script>
</body>
</html>
"""
open(OUT, "w").write(page)
print(len(page), "bytes", "title", len(TITLE), "desc", len(DESC))
