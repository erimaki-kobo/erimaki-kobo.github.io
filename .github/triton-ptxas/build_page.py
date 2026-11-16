"""Build en/triton-ptxas-arch-lookup/index.html from data.json and tool.js.
usage: python3 build_page.py <data.json> <out index.html> [published YYYY-MM-DD] [modified YYYY-MM-DD]"""
import json, html, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(sys.argv[1])); OUT = sys.argv[2]
PUBLISHED = sys.argv[3] if len(sys.argv) > 3 else "2026-11-16"
MODIFIED = sys.argv[4] if len(sys.argv) > 4 else PUBLISHED
def e(x): return html.escape(str(x))
def vkey(v): return [int(x) for x in re.findall(r"\d+", v)]
T = D["triton"]; TV = sorted(T, key=vkey); TORCH = D["torch"]; TOV = sorted(TORCH, key=vkey); VL = D["vllm"]
LATEST_T = TV[-1]; LATEST_TORCH = TOV[-1]; LATEST_V = VL[-1]["v"]; LATEST_CUDA = sorted(D["cuda"], key=vkey)[-1]
GPU = {121: "DGX Spark (GB10)", 120: "RTX 50 series, RTX PRO Blackwell", 110: "Jetson AGX Thor", 103: "B300 / GB300", 100: "B200 / GB200",
       90: "H100, H200", 89: "RTX 40 series, L4, L40S", 86: "RTX 30 series, A10, A40", 80: "A100, A30"}
def first(cap):
    t = next(v for v in TV if T[v]["res"][str(cap)]["ok"])
    to = next((v for v in TOV if vkey(TORCH[v]["triton"]) >= vkey(t)), None)
    vl = next((x["v"] for x in VL if vkey(TORCH[x["torch"]]["triton"]) >= vkey(t)), None)
    return t, to, vl
def cc(c): return f"{c // 10}.{c % 10}"

# ---- claims made in the prose; stop the build if the data no longer supports them ----
F = {c: first(c) for c in (100, 103, 110, 120, 121)}
assert F[120][0] == "3.3.0" and F[100][0] == "3.3.0" and F[121][0] == "3.6.0" and F[103][0] == "3.6.0" and F[110][0] == "3.7.0", F
assert (F[120][1], F[121][1], F[110][1]) == ("2.7.0", "2.10.0", "2.12.0"), F
for c in D["caps"]:      # once a release knows a GPU, every later release does
    seen = False
    for v in TV:
        ok = T[v]["res"][str(c)]["ok"]; assert ok or not seen, (c, v); seen = seen or ok
    if c <= 90: assert all(T[v]["res"][str(c)]["ok"] for v in TV), c
assert all(T[v]["name"]["120"] == "sm_120" for v in TV if vkey(v) <= [3, 2, 0]) and all(T[v]["name"]["120"] == "sm_120a" for v in TV if vkey(v) >= [3, 3, 0])
assert [v for v in TV if "ptxas-blackwell" not in T[v]["tools"] and vkey(v) >= [3, 3, 0]] == ["3.4.0", "3.5.0", "3.5.1"]
assert [v for v in TV if "-" in "".join(T[v]["env"].values())] == ["3.3.0", "3.3.1"]
assert T["3.2.0"]["cuda_rule"] == "12.0-12.6" and all(not T["3.2.0"]["res"][str(c)].get("cuda") for c in (100, 103, 110, 120, 121))
assert [v for v in TV if "13+" in T[v]["cuda_rule"]][0] == "3.5.0"
assert T[LATEST_T]["sel_rule"] == ">=90" and T["3.8.0"]["sel_rule"] == ">=100"
assert T["3.5.1"]["res"]["121"]["cuda"][0] == "12.9" and T["3.4.0"]["res"]["121"]["cuda"] == ["12.9"] and T["3.6.0"]["res"]["110"]["cuda"][0] == "13.0"
assert T["3.6.0"]["res"]["110"]["var"] == "TRITON_PTXAS_BLACKWELL_PATH" and T["3.5.1"]["res"]["121"]["var"] == "TRITON_PTXAS_PATH"
assert [v for v in TV if T[v]["aarch64"]][0] == "3.5.0" and [v for v in TOV if TORCH[v]["aarch64"]][0] == "2.11.0"
assert all(T[v]["byte_identical"] for v in TV if vkey(v) >= [3, 3, 0])
C = D["cuda"]
def cuda_first(name): return next(m for m in sorted(C, key=vkey) if name in C[m])
assert (cuda_first("sm_120a"), cuda_first("sm_100a"), cuda_first("sm_121a"), cuda_first("sm_103a"), cuda_first("sm_110a")) == ("12.8", "12.8", "12.9", "12.9", "13.0")
assert "sm_101a" in C["12.9"] and "sm_101a" not in C["13.0"] and cuda_first("sm_107a") == "13.4"
vl_of = {x["v"]: x for x in VL}
assert vl_of["0.12.0"]["torch"] == "2.9.0" and TORCH["2.9.0"]["triton"] == "3.5.0"      # the setup in vLLM #30163

# ---- tables ----
gpu_rows = []
for c in (121, 120, 110, 103, 100):
    t, to, vl = F[c]
    older = sorted({(T[v]["res"][str(c)]["var"]) for v in TV if not T[v]["res"][str(c)]["ok"] and T[v]["res"][str(c)]["cuda"]})
    gpu_rows.append(f"<tr><td>{cc(c)}</td><td>{e(GPU[c])}</td><td><code>sm_{c}a</code></td><td>CUDA {cuda_first(f'sm_{c}a')}</td><td><b>{t}</b></td><td>{to}</td><td>{vl}</td></tr>")
gpu_rows = "\n".join(gpu_rows)
def cell(v, c):
    r = T[v]["res"][str(c)]
    if r["ok"]: return '<td class="ok">ok</td>'
    if r["cuda"]:
        rng = r["cuda"][0] if len(r["cuda"]) == 1 else (f'{r["cuda"][0]}+' if r["cuda"][-1] == LATEST_CUDA else f'{r["cuda"][0]} to {r["cuda"][-1]}')
        return f'<td class="no">no<br><span class="mut">fix: CUDA {rng} ptxas</span></td>'
    return '<td class="no">no<br><span class="mut">upgrade only</span></td>'
tr_rows = []
for v in reversed(TV):
    r = T[v]; pins = [t for t in TOV if TORCH[t]["triton"] == v]
    tools = "<br>".join(f"<code>{e(n)}</code> {e(x)}" for n, x in sorted(r["tools"].items()))
    rule = {"one": "all GPUs: <code>ptxas</code>", ">=100": "10.0 and up: <code>ptxas-blackwell</code>", ">=90": "9.0 and up: <code>ptxas-blackwell</code>"}[r["sel_rule"]]
    env = "<br>".join(f"<code>{e(x)}</code>" for _, x in sorted(r["env"].items()))
    tr_rows.append(f"<tr><td><b>{v}</b><br><span class='mut'>{r['date']}</span></td><td>{', '.join(pins) or '-'}</td><td>{tools}</td><td>{rule}</td><td>{env}</td><td>{e(r['cuda_rule'])}</td>"
                   + "".join(cell(v, c) for c in (100, 103, 110, 120, 121)) + "</tr>")
tr_rows = "\n".join(tr_rows)
cuda_rows = []; prev = None
for m in sorted(C, key=vkey):
    names = [n for n in C[m] if int(re.search(r"\d+", n).group()) >= 100]
    if names == prev: cuda_rows[-1][1] = m; continue
    cuda_rows.append([m, m, names, D["cuda_first"][m]]); prev = names
cuda_rows = "\n".join(f"<tr><td>CUDA {a}{'' if a == b else ' to ' + b}</td><td>{d}</td><td>{' '.join('<code>' + e(n) + '</code>' for n in names) or '<span class=mut>none (newest is sm_90a)</span>'}</td></tr>" for a, b, names, d in cuda_rows)
vl_rows = []; cur = None
for x in VL:
    t = TORCH[x["torch"]]["triton"]
    if cur and cur[2] == x["torch"]: cur[1] = x["v"]
    else: cur = [x["v"], x["v"], x["torch"], t]; vl_rows.append(cur)
vl_rows = "\n".join(f"<tr><td>{a}{'' if a == b else ' to ' + b}</td><td>{to}</td><td>{t}</td>" + "".join(cell(t, c) for c in (110, 120, 121)) + "</tr>" for a, b, to, t in reversed(vl_rows))

TITLE = "ptxas: 'sm_121a' is not defined for option 'gpu-name'"
H1 = "ptxas fatal: Value 'sm_121a' is not defined for option 'gpu-name': which Triton, PyTorch and vLLM release fixes it"
DESC = ("Triton's bundled ptxas is older than your GPU. Which Triton, PyTorch and vLLM releases know sm_120a, sm_121a and sm_110a, "
        "and which variable fixes older ones.")
assert len(TITLE) <= 60 and len(DESC) <= 160, (len(TITLE), len(DESC))
URL = "https://erimaki-kobo.github.io/en/triton-ptxas-arch-lookup/"
ORG = {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}
FAQ = [
    ("What does \"Value 'sm_121a' is not defined for option 'gpu-name'\" mean?",
     f"Triton compiles its kernels by running NVIDIA's <code>ptxas</code> with <code>--gpu-name=sm_NNNa</code>, where NNN is your GPU's compute capability. The ptxas that ships inside the Triton wheel is a fixed CUDA build, and that build is older than your GPU. DGX Spark (12.1) needs a ptxas from CUDA {cuda_first('sm_121a')} or newer, Jetson AGX Thor (11.0) from CUDA {cuda_first('sm_110a')} or newer, RTX 50 (12.0) from CUDA {cuda_first('sm_120a')} or newer."),
    ("Why does <code>TRITON_PTXAS_PATH</code> have no effect?",
     f"Three reasons, by release. In Triton 3.3.x and from 3.6.0 on, Blackwell GPUs use a second binary, <code>ptxas-blackwell</code>, and its variable is <code>TRITON_PTXAS_BLACKWELL_PATH</code> (in 3.3.x the name is <code>TRITON_PTXAS-BLACKWELL_PATH</code>, with a hyphen). In every release, a path that does not exist is skipped without a message and the bundled binary is used. And Triton 3.2.0 rejects any ptxas newer than CUDA 12.6, while Triton 3.4.0 and older reject CUDA 13."),
    ("Does <code>TORCH_CUDA_ARCH_LIST</code> change the name Triton passes to ptxas?",
     "No. Triton asks for the compute capability of the current device and builds the name from it. <code>TORCH_CUDA_ARCH_LIST</code> is a build-time setting for compiling PyTorch and extensions."),
    ("Why does my error say <code>sm_120</code> without the trailing a?",
     "That is Triton 3.2.0 or older, which PyTorch 2.6 and older pin. Those releases add the <code>a</code> only for 9.0. Their bundled ptxas is CUDA 12.4, which knows nothing newer than <code>sm_90a</code>. Triton 3.3.0 (PyTorch 2.7.0) is the first that knows RTX 50."),
]
def plain(x): return html.unescape(re.sub(r"<[^>]+>", "", x))
faq_html = "\n".join(f"<h3>{q}</h3>\n<p>{a}</p>" for q, a in FAQ)
LD = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": "ptxas: Value 'sm_121a' is not defined for option 'gpu-name' (Triton, PyTorch, vLLM)", "description": DESC, "url": URL,
     "datePublished": PUBLISHED, "dateModified": MODIFIED, "inLanguage": "en",
     "about": ["Triton (GPU kernel compiler)", "NVIDIA ptxas", "PyTorch torch.compile", "vLLM", "DGX Spark (sm_121)", "Jetson AGX Thor (sm_110)", "NVIDIA RTX 50 series (sm_120)"],
     "author": ORG, "publisher": ORG, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "@id": URL + "#tool", "name": "Triton ptxas GPU support lookup", "url": URL + "#tool",
     "description": f"For a GPU compute capability and a Triton, PyTorch or vLLM release, shows which bundled ptxas Triton runs, whether it knows the GPU, the first release that does, and the environment variable that points an older release at a newer ptxas. Triton 3.0.0 to {LATEST_T}.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "softwareVersion": "1.0.0", "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "publisher": ORG},
    {"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": [
        {"@type": "Question", "name": plain(q), "acceptedAnswer": {"@type": "Answer", "text": plain(a)}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
tool_js = open(os.path.join(HERE, "tool.js")).read(); assert "__D__" in tool_js
slim = {"triton": {v: {"env": T[v]["env"], "res": T[v]["res"]} for v in TV}, "torch": {v: {"triton": TORCH[v]["triton"]} for v in TOV}, "vllm": [{"v": x["v"], "torch": x["torch"]} for x in VL]}

CSS = """:root{--bg:#fff;--fg:#1b1f24;--mut:#5b6470;--line:#d9dee4;--card:#f5f7f9;--acc:#0b5cad;--ok:#17703a;--no:#a33a1f;--warn:#fff1e6}
@media (prefers-color-scheme:dark){:root{--bg:#14171b;--fg:#e6e9ed;--mut:#9aa4af;--line:#2d333b;--card:#1d2127;--acc:#6aaef5;--ok:#5cc985;--no:#f08b6e;--warn:#3b2a1d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.6rem;line-height:1.25;margin:.2em 0 .4em;overflow-wrap:anywhere}h2{font-size:1.3rem;margin-top:2em}h3{font-size:1.05rem;margin-top:1.4em}
a{color:var(--acc);overflow-wrap:anywhere}code{font:0.88em ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--card);padding:1px 4px;border-radius:4px;word-break:break-word}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}table{border-collapse:collapse;width:100%;font-size:.9rem;margin:.6em 0}th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{background:var(--card)}
.mut{color:var(--mut);font-size:.9em}.ok{color:var(--ok)}.no{color:var(--no)}
.box{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:1em 0}
label{display:block;font-weight:600;margin:.6em 0 .2em}select,textarea{width:100%;font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}textarea{min-height:70px;font-family:ui-monospace,Menlo,monospace;font-size:.85rem}
button{font:inherit;margin-top:8px;padding:7px 14px;border:0;border-radius:6px;background:var(--acc);color:#fff;cursor:pointer}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media (max-width:720px){.grid{grid-template-columns:1fr}}
.res{border-left:4px solid var(--acc);padding:10px 12px;background:var(--bg);margin:12px 0}.res.bad{border-color:var(--no)}.res.warn{border-color:#d9822b;background:var(--warn)}
.big{font-size:1.2rem;font-weight:700}.log{margin-top:6px;font-size:.92rem}
details{margin:.4em 0}summary{cursor:pointer;font-weight:600}pre{background:var(--card);padding:10px;border-radius:6px;overflow-x:auto;font-size:.85rem}"""

BODY = """<p class="mut"><a href="/en/">Answers for LLM inference engineers</a> &middot; Triton 3.0.0 to @LATEST_T@, PyTorch 2.4.0 to @LATEST_TORCH@, vLLM @FIRST_V@ to @LATEST_V@, CUDA 12.0 to @LATEST_CUDA@ &middot; published @PUBLISHED@</p>
<h1>@H1@</h1>
<p><b>Short answer:</b> the <code>ptxas</code> inside your Triton wheel is older than your GPU. The bundled binary knows RTX 50 (<code>sm_120a</code>) from <b>Triton @T120@</b> (PyTorch @P120@, vLLM @V120@), DGX Spark (<code>sm_121a</code>) and B300 (<code>sm_103a</code>) from <b>Triton @T121@</b> (PyTorch @P121@, vLLM @V121@), and Jetson AGX Thor (<code>sm_110a</code>) from <b>Triton @T110@</b> (PyTorch @P110@, vLLM @V110@). On an older release you can point Triton at a newer ptxas, but the variable is not always <code>TRITON_PTXAS_PATH</code>: from Triton 3.6.0 these GPUs use a second binary whose variable is <code>TRITON_PTXAS_BLACKWELL_PATH</code>, and a path that does not exist is ignored without a message.</p>

<h2 id="tool">Look up your GPU and release</h2>
<div class="box">
<div class="grid">
<div><label for="gpu">GPU (compute capability)</label><select id="gpu"></select></div>
<div><label for="ver">What you have installed</label><select id="ver"></select></div>
</div>
<details><summary>Or paste the error</summary>
<textarea id="err" aria-label="error text" placeholder="ptxas fatal   : Value 'sm_121a' is not defined for option 'gpu-name'"></textarea>
<button id="errbtn" type="button">Read error</button> <span id="errmsg" class="mut"></span></details>
<div id="out" aria-live="polite"></div>
<p class="mut">Runs in your browser; nothing is sent. To see what you have: <code>python -c "import triton, torch; print(triton.__version__, torch.__version__, torch.cuda.get_device_capability())"</code></p>
</div>

<h2 id="gpus">First release that knows each Blackwell-generation GPU</h2>
<div class="tw"><table>
<tr><th>Compute capability</th><th>GPU</th><th>Name Triton passes</th><th>ptxas that knows it</th><th>First Triton (bundled)</th><th>First PyTorch pinning it</th><th>First vLLM pinning that PyTorch</th></tr>
@gpu_rows@
</table></div>
<p class="mut">Hopper and older (9.0, 8.9, 8.6, 8.0) pass in every Triton release from 3.0.0. PyTorch means the wheel on PyPI and the <code>triton</code> requirement in its metadata. vLLM means the <code>torch==</code> line in that tag's CUDA requirements file.</p>

<h2 id="triton">Every Triton release: what is bundled, which binary runs, which variable overrides it</h2>
<div class="tw"><table>
<tr><th>Triton</th><th>Pinned by PyTorch</th><th>Bundled ptxas (CUDA build)</th><th>Binary used</th><th>Override variable</th><th>CUDA numbers it accepts from an override</th><th>10.0</th><th>10.3</th><th>11.0</th><th>12.0</th><th>12.1</th></tr>
@tr_rows@
</table></div>
<p class="mut">"ok" means the name Triton passes is present in the bundled binary. "fix: CUDA X ptxas" means the override variable in that row works when it points at the ptxas of that CUDA release (X+ means that release or newer, up to the newest read here). "upgrade only" means no ptxas is both new enough for the GPU and accepted by that Triton release.</p>

<h2 id="traps">Six ways the usual advice fails</h2>
<ol>
<li><b><code>TRITON_PTXAS_PATH</code> is the wrong variable for Blackwell on Triton 3.3.x and from 3.6.0.</b> Those releases ship two binaries and run <code>ptxas-blackwell</code> for compute capability 10.0 and up (9.0 and up in @LATEST_T@). If the error line starts with <code>ptxas-blackwell fatal</code>, this is your case. Set <code>TRITON_PTXAS_BLACKWELL_PATH</code>.</li>
<li><b>On Triton 3.3.0 and 3.3.1 (PyTorch 2.7.x) that variable is spelled <code>TRITON_PTXAS-BLACKWELL_PATH</code>.</b> The name is built with <code>binary.upper()</code>, which keeps the hyphen, and bash <code>export</code> does not accept a hyphen. Use <code>env 'TRITON_PTXAS-BLACKWELL_PATH=/usr/local/cuda/bin/ptxas' python ...</code>, set it through <code>os.environ</code> before importing triton, or replace <code>triton/backends/nvidia/bin/ptxas-blackwell</code> with a symlink. Triton 3.6.0 converts the hyphen to an underscore.</li>
<li><b>A path that does not exist is skipped silently.</b> In every release, if the file the variable names is not there, Triton uses the bundled binary and prints nothing. Inside a container <code>/usr/local/cuda/bin/ptxas</code> is often absent, because runtime-only CUDA images do not include the compiler. The error then looks exactly as before. The <code>Repro command:</code> line in the traceback (Triton 3.2.0 and newer) shows which file was run.</li>
<li><b>Old Triton rejects new CUDA numbers.</b> Triton reads the override's <code>--version</code> and maps it to a PTX version. Triton 3.2.0 (PyTorch 2.6.0) accepts nothing newer than CUDA 12.6, so no ptxas that knows a Blackwell GPU is usable with it. Triton 3.3.0 to 3.4.0 accept CUDA 12.x only, so a CUDA 13 ptxas raises <code>Triton only support CUDA 10.0 or higher, but got CUDA version: 13.x</code>. CUDA 13 is accepted from Triton 3.5.0. Jetson AGX Thor needs CUDA 13, so it has no fix below Triton 3.5.0.</li>
<li><b>Triton 3.4.0 to 3.5.1 (PyTorch 2.8.0 to 2.9.1) went back to one binary.</b> They ship only <code>ptxas</code>, the CUDA 12.8.93 build, for every GPU. That build knows <code>sm_120a</code> but not <code>sm_121a</code>, <code>sm_103a</code> or <code>sm_110a</code>. Here <code>TRITON_PTXAS_PATH</code> is the right variable.</li>
<li><b><code>TORCH_CUDA_ARCH_LIST</code> does nothing for this error.</b> Triton builds the name from the device's compute capability (<code>major * 10 + minor</code>, plus <code>a</code> for 9.0 and up from Triton 3.3.0). There is no setting that makes it pass <code>sm_120a</code> on an <code>sm_121</code> device.</li>
</ol>
<p>Arm machines (DGX Spark, Jetson AGX Thor): PyPI has aarch64 Triton wheels from 3.5.0 only. The Triton requirement in PyTorch's PyPI metadata is limited to x86_64 up to 2.10.0 and applies to every Linux machine from 2.11.0. CUDA builds of PyTorch for Arm often come from another index, which was not read here. On Arm, check <code>triton.__version__</code> directly instead of inferring it from PyTorch.</p>

<h2 id="vllm">vLLM releases</h2>
<p>vLLM does not set either variable itself: <code>vllm/triton_utils/</code> and <code>vllm/env_override.py</code> at @LATEST_V@ contain no reference to ptxas. Which Triton you get follows from the PyTorch pin.</p>
<div class="tw"><table>
<tr><th>vLLM</th><th>PyTorch pin</th><th>Triton</th><th>11.0 Thor</th><th>12.0 RTX 50</th><th>12.1 DGX Spark</th></tr>
@vl_rows@
</table></div>
<p class="mut">This covers only the Triton step. Whether vLLM's own compiled kernels support a GPU is a separate question: see the <a href="/en/vllm-torch-cuda-driver-matrix/">PyTorch/CUDA/driver matrix</a> and the <a href="/en/vllm-sm120-moe-backend-lookup/">MoE backend lookup for SM120/SM121</a>.</p>

<h2 id="cuda">Which ptxas knows which GPU name</h2>
<div class="tw"><table>
<tr><th>ptxas release</th><th>First on PyPI</th><th>Names for compute capability 10.0 and up</th></tr>
@cuda_rows@
</table></div>
<p class="mut"><code>sm_101</code> was dropped in CUDA 13.0, the release that added <code>sm_110</code>. The <code>f</code> suffix (family) appeared in CUDA 12.9. To get a newer ptxas without installing a full toolkit: <code>pip download --no-deps nvidia-cuda-nvcc-cu12==12.9.86</code> (CUDA 12) or <code>nvidia-cuda-nvcc</code> (CUDA 13), then unzip the file ending in <code>bin/ptxas</code> from the wheel and make it executable.</p>

<h2 id="method">How this was checked, and what was not</h2>
<ul>
<li>Bundled binaries: every Triton wheel on PyPI from 3.0.0 to @LATEST_T@ (x86_64, and aarch64 where it exists) was downloaded, verified against the sha256 PyPI publishes, and <code>bin/ptxas</code> and <code>bin/ptxas-blackwell</code> were read for their version banner and for the <code>sm_*</code> names they contain. From Triton 3.3.0 each bundled file is byte-identical to the ptxas in NVIDIA's own <code>nvidia-cuda-nvcc</code> wheel of the same version.</li>
<li>ptxas releases: the same reading for every <code>nvidia-cuda-nvcc-cu12</code> and <code>nvidia-cuda-nvcc</code> wheel on PyPI, CUDA 12.0 to @LATEST_CUDA@, both architectures. Patch releases of one minor version list the same names.</li>
<li>Rules: which binary runs, how the name is built, the variable names, the fallback and the accepted CUDA numbers were read from <code>third_party/nvidia/backend/compiler.py</code> and <code>python/triton/knobs.py</code> at each release tag.</li>
<li><b>Not run.</b> No ptxas was executed and nothing here was tested on a GPU. "Knows the name" is necessary for the compile to succeed, not sufficient: an override can get past this error and still fail later, most likely on Triton 3.2.0 and older, whose LLVM predates these GPUs.</li>
<li>Not covered: PyTorch wheels from download.pytorch.org (their Triton pin was not read), Triton built from source, <code>triton-windows</code>, and nightly builds.</li>
</ul>

<h2 id="faq">Questions</h2>
@faq_html@

<h2 id="sources">Sources</h2>
<ul>
<li>Triton source at each release tag: <a href="https://github.com/triton-lang/triton/blob/v@LATEST_T@/third_party/nvidia/backend/compiler.py">third_party/nvidia/backend/compiler.py</a>, <a href="https://github.com/triton-lang/triton/blob/v@LATEST_T@/python/triton/knobs.py">python/triton/knobs.py</a>, <a href="https://github.com/triton-lang/triton/blob/v@LATEST_T@/cmake/nvidia-toolchain-version.json">cmake/nvidia-toolchain-version.json</a></li>
<li>PyPI: <a href="https://pypi.org/project/triton/#history">triton</a>, <a href="https://pypi.org/project/torch/#history">torch</a>, <a href="https://pypi.org/project/nvidia-cuda-nvcc-cu12/#history">nvidia-cuda-nvcc-cu12</a>, <a href="https://pypi.org/project/nvidia-cuda-nvcc/#history">nvidia-cuda-nvcc</a></li>
<li><a href="https://github.com/vllm-project/vllm/issues/30163">vLLM #30163</a>: two DGX Spark, vLLM 0.12.0, "Triton's bundled ptxas 12.8 doesn't support GB10" (vLLM 0.12.0 pins PyTorch 2.9.0, which pins Triton 3.5.0)</li>
<li><a href="https://github.com/vllm-project/vllm/pull/32704">vLLM PR #32704</a>: proposal to set <code>TRITON_PTXAS_PATH</code> automatically for sm_110a and sm_121a</li>
<li><a href="https://forums.developer.nvidia.com/t/running-llama-3-1-8b-fp4-get-triton-error-value-sm-121a-is-not-defined-for-option-gpu-name/348808">NVIDIA forum: Value 'sm_121a' is not defined for option 'gpu-name'</a> (the error line begins with <code>ptxas-blackwell fatal</code>)</li>
<li><a href="https://forums.developer.nvidia.com/t/facing-difficulty-in-installing-webui-related-things-in-jetson-agx-thor/355426">NVIDIA forum: Triton 3.6.0 on Jetson AGX Thor, bundled ptxas-blackwell rejects sm_110a</a></li>
<li><a href="https://discuss.pytorch.org/t/rtx-5070-ti-blackwell-pytorch-nightly-triton-still-getting-sm-120-is-not-defined-for-option-gpu-name-error/220460">PyTorch forum: "sm_120 is not defined for option 'gpu-name'"</a></li>
</ul>
<p class="mut">Related: <a href="/en/vllm-torch-cuda-driver-matrix/">vLLM PyTorch/CUDA/driver matrix</a> &middot; <a href="/en/vllm-sm120-moe-backend-lookup/">vLLM MoE backend on SM120/SM121</a> &middot; <a href="/en/gguf-arch-min-build-lookup/">GGUF architecture minimum build</a></p>"""

subs = {"LATEST_T": LATEST_T, "LATEST_TORCH": LATEST_TORCH, "LATEST_V": LATEST_V, "FIRST_V": VL[0]["v"], "LATEST_CUDA": LATEST_CUDA, "PUBLISHED": PUBLISHED, "H1": e(H1),
        "T120": F[120][0], "P120": F[120][1], "V120": F[120][2], "T121": F[121][0], "P121": F[121][1], "V121": F[121][2], "T110": F[110][0], "P110": F[110][1], "V110": F[110][2],
        "gpu_rows": gpu_rows, "tr_rows": tr_rows, "cuda_rows": cuda_rows, "vl_rows": vl_rows, "faq_html": faq_html}
body = BODY
for k, v in subs.items(): body = body.replace("@" + k + "@", str(v))
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
<body>
<main>
{body}
</main>
<script>
{tool_js.replace("__D__", json.dumps(slim, separators=(",", ":"), sort_keys=True))}
</script>
</body>
</html>
"""
assert not re.search(r"[぀-ヿ一-鿿]", page)
os.makedirs(os.path.dirname(OUT), exist_ok=True); open(OUT, "w").write(page)
print("wrote", OUT, len(page.encode()), "bytes;", "title", len(TITLE), "desc", len(DESC))
