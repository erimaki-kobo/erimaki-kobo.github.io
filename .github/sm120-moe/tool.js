// vLLM MoE backend lookup. __D__ is injected by build_page.py.
(function () {
  "use strict";
  var D = __D__, S = D.S;
  var GPUS = [
    [120, "RTX 50 series, RTX PRO 6000 Blackwell (SM120)"],
    [121, "DGX Spark / GB10 (SM121)"],
    [100, "B200, GB200 (SM100)"],
    [103, "B300, GB300 (SM103)"],
    [90, "H100, H200, H20 (SM90)"],
    [89, "RTX 40 series, L4, L40S (SM89)"],
    [80, "A100, A800 (SM80)"]
  ];
  var SCEN = [
    ["nvfp4", "NVFP4 MoE (ModelOpt NVFP4, compressed-tensors W4A4 NVFP4)", "NvFp4"],
    ["fp8_block", "FP8, 128x128 block scales (quant_method fp8 with weight_block_size; compressed-tensors block)", "Fp8"],
    ["fp8_tensor", "FP8, per-tensor weights, dynamic activations (quant_method fp8, no block size)", "Fp8"],
    ["ct_fp8_channel", "FP8, per-channel weights, dynamic per-token activations (compressed-tensors \"FP8-dynamic\")", "Fp8"],
    ["ct_fp8_tensor_static", "FP8, per-tensor, static activation scales (compressed-tensors)", "Fp8"],
    ["modelopt_fp8", "FP8, per-tensor, static activation scales (ModelOpt FP8, or quant_method fp8 with activation_scheme static)", "Fp8"],
    ["mxfp4_gptoss", "MXFP4 (gpt-oss)", "Mxfp4"]
  ];
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function tagIdx(t) { for (var i = 0; i < D.tags.length; i++) if (D.tags[i][0] === t) return i; return -1; }
  function rec(t, c, s) { return D.r[t + "|" + c + "|" + s] || null; }
  function hasFlag(t) { return D.flag.indexOf(t) >= 0; }

  function fill() {
    var g = $("gpu"), q = $("quant"), v = $("ver");
    GPUS.forEach(function (x) { var o = document.createElement("option"); o.value = x[0]; o.textContent = x[1]; g.appendChild(o); });
    SCEN.forEach(function (x) { var o = document.createElement("option"); o.value = x[0]; o.textContent = x[1]; q.appendChild(o); });
    for (var i = D.tags.length - 1; i >= 0; i--) { var o = document.createElement("option"); o.value = D.tags[i][0]; o.textContent = D.tags[i][0] + " (" + D.tags[i][1] + ")"; v.appendChild(o); }
  }

  // ---- config.json -> scenario ----
  function detect(txt) {
    var cfg;
    try { cfg = JSON.parse(txt); } catch (e) { return { err: "That is not valid JSON. Paste the whole config.json (or just its quantization_config object)." }; }
    if (!cfg || typeof cfg !== "object") return { err: "That is not a JSON object. Paste the whole config.json (or just its quantization_config object)." };
    var qc = cfg.quantization_config || (cfg.text_config && cfg.text_config.quantization_config) || (cfg.quant_method ? cfg : null);
    if (!qc) return { err: "No quantization_config found. An unquantized (BF16/FP16) MoE uses a different selector that this page does not cover." };
    var m = String(qc.quant_method || "").toLowerCase();
    if (m === "modelopt" || m === "modelopt_fp4") {
      var algo = String(qc.quant_algo || (qc.quantization && qc.quantization.quant_algo) || "").toUpperCase();
      if (m === "modelopt_fp4" || algo.indexOf("NVFP4") >= 0) return { s: "nvfp4", why: "quant_method " + m + (algo ? ", quant_algo " + algo : "") };
      if (algo.indexOf("FP8") >= 0) return { s: "modelopt_fp8", why: "quant_method modelopt, quant_algo " + algo };
      return { err: "ModelOpt checkpoint with quant_algo '" + algo + "' is not covered here (only NVFP4 and FP8)." };
    }
    if (m === "fp8") {
      if (qc.weight_block_size) return { s: "fp8_block", why: "quant_method fp8 with weight_block_size " + JSON.stringify(qc.weight_block_size) };
      if (String(qc.activation_scheme || "").toLowerCase() === "static") return { s: "modelopt_fp8", why: "quant_method fp8, activation_scheme static" };
      return { s: "fp8_tensor", why: "quant_method fp8, no weight_block_size, dynamic activations" };
    }
    if (m === "mxfp4") return { s: "mxfp4_gptoss", why: "quant_method mxfp4" };
    if (m === "compressed-tensors") {
      var groups = qc.config_groups || {}, k, w = null, a = null;
      for (k in groups) if (groups[k] && groups[k].weights) { w = groups[k].weights; a = groups[k].input_activations || null; break; }
      if (!w) return { err: "compressed-tensors config without config_groups[*].weights." };
      var bits = w.num_bits, type = String(w.type || "").toLowerCase(), st = String(w.strategy || "").toLowerCase();
      if (bits === 4 && type === "float") {
        if (!a) return { err: "compressed-tensors NVFP4 weights with 16-bit activations (W4A16) take a different code path in some versions; this page covers W4A4 NVFP4 only." };
        return { s: "nvfp4", why: "compressed-tensors, 4-bit float weights (NVFP4)" };
      }
      if (bits === 8 && type === "float") {
        if (st === "block") return { s: "fp8_block", why: "compressed-tensors FP8, block strategy" };
        if (st === "channel") return { s: "ct_fp8_channel", why: "compressed-tensors FP8, channel weights" + (a ? ", " + a.strategy + " activations" : "") };
        if (st === "tensor") {
          if (a && a.dynamic === false) return { s: "ct_fp8_tensor_static", why: "compressed-tensors FP8, tensor strategy, static input scales" };
          return { err: "compressed-tensors FP8 per-tensor with dynamic activations is not one of the computed cases." };
        }
      }
      return { err: "compressed-tensors scheme (" + bits + "-bit " + type + ", " + st + ") is not covered. INT4/INT8 (W4A16, W8A8-int) MoE use other selectors." };
    }
    return { err: "quant_method '" + m + "' is not covered. AWQ, GPTQ and other INT4 MoE checkpoints go through the WNA16 selector, which this page does not include." };
  }

  // ---- render ----
  function orderList(r) { return r.o ? r.o.map(function (i) { return S[i]; }) : null; }
  function render() {
    var c = +$("gpu").value, s = $("quant").value, t = $("ver").value, out = $("out");
    var r = rec(t, c, s), fam = SCEN.filter(function (x) { return x[0] === s; })[0][2];
    if (!r) { out.innerHTML = "<p>No data for this combination.</p>"; return; }
    var h = "";
    if (r.e !== undefined) {
      h += "<div class='res bad'><b>vLLM " + esc(t) + " stops here:</b> <code>" + esc(S[r.e]) + "</code></div>";
      out.innerHTML = h; return;
    }
    var b = S[r.b], ord = orderList(r);
    h += "<div class='res'><div class='k'>With <code>--moe-backend auto</code> (the default), vLLM " + esc(t) + " picks</div><div class='big'>" + esc(b) + "</div>";
    if (ord) h += "<div class='log'>Startup log line: <code>Using " + (fam === "Fp8" ? "" : "'") + esc(b) + (fam === "Fp8" ? "" : "'") + " " + esc(fam) + " MoE backend out of potential backends: [" + ord.map(function (x) { return "'" + esc(x) + "'"; }).join(", ") + "].</code></div>";
    h += "</div>";
    // candidates
    var cand = D.CT[r.c] || {}, mp = D.MT[r.m] || {}, rev = {};
    Object.keys(mp).forEach(function (k) {
      var v = mp[k], arr = Array.isArray(v) ? v : [v];
      arr.forEach(function (x) { var n = S[x]; (rev[n] = rev[n] || []).push(S[+k]); });
    });
    var names = Object.keys(cand).map(function (k) { return S[+k]; });
    if (names.length) {
      var flag = hasFlag(t);
      h += "<h3>Every " + esc(fam) + " MoE backend on this GPU in " + esc(t) + "</h3>";
      h += "<p class='note'>" + (flag ? "\"Forcible with\" is the <code>--moe-backend</code> value that maps to it. Forcing a backend marked <b>no</b> raises <code>ValueError: ... does not support the deployment configuration since ...</code> at startup." : "This release has no <code>--moe-backend</code> flag (added in v0.17.0); forcing was done with environment variables, see the table below the tool.") + "</p>";
      h += "<div class='tw'><table><thead><tr><th>Backend</th><th>Usable here?</th>" + (flag ? "<th>Forcible with</th>" : "") + "</tr></thead><tbody>";
      var sorted = names.slice();
      if (ord) sorted.sort(function (x, y) { var a = ord.indexOf(x), bb = ord.indexOf(y); a = a < 0 ? 99 : a; bb = bb < 0 ? 99 : bb; return a - bb; });
      sorted.forEach(function (n) {
        var st = S[cand[S.indexOf(n)]];
        var ok = st === "ok";
        var cls = n === b ? " class='pick'" : "";
        var f = rev[n] ? rev[n].map(function (x) { return "<code>--moe-backend " + esc(x) + "</code>"; }).join("<br>") : "<span class='mut'>not selectable</span>";
        h += "<tr" + cls + "><td><code>" + esc(n) + "</code>" + (n === b ? " <b>(auto pick)</b>" : "") + (ord && ord.indexOf(n) < 0 ? " <span class='mut'>(not in auto list)</span>" : "") + "</td><td>" + (ok ? "<b class='ok'>yes</b>" : "<span class='no'>no</span>: " + esc(st)) + "</td>" + (flag ? "<td>" + f + "</td>" : "") + "</tr>";
      });
      h += "</tbody></table></div>";
    }
    // history
    h += "<h3>Auto pick across releases for this GPU and format</h3><div class='tw'><table><thead><tr><th>vLLM releases</th><th>Auto backend</th></tr></thead><tbody>";
    var seq = [];
    D.tags.forEach(function (x) {
      var rr = rec(x[0], c, s), v = rr ? (rr.e !== undefined ? "(error)" : S[rr.b]) : "-";
      if (seq.length && seq[seq.length - 1][1] === v) seq[seq.length - 1][2] = x[0]; else seq.push([x[0], v, x[0]]);
    });
    seq.forEach(function (z) { h += "<tr" + (tagIdx(t) >= tagIdx(z[0]) && tagIdx(t) <= tagIdx(z[2]) ? " class='pick'" : "") + "><td>" + esc(z[0] === z[2] ? z[0] : z[0] + " to " + z[2]) + "</td><td><code>" + esc(z[1]) + "</code></td></tr>"; });
    h += "</tbody></table></div>";
    var warn = WARN[c + "|" + s];
    if (warn) h += "<div class='res warn'><b>Selected is not the same as working.</b> " + warn + "</div>";
    out.innerHTML = h;
  }
  var WARN = {};
  [120, 121].forEach(function (cc) {
    WARN[cc + "|nvfp4"] = "On SM120, the native NVFP4 MoE kernels have a public report of grouped-GEMM initialization failures and garbage output on 4x RTX PRO 6000 (<a href='https://discuss.vllm.ai/t/sm120-rtx-pro-6000-nvfp4-moe-performance-report-qwen3-5-397b/2536'>forum report</a>). The working path in that report is Marlin: <code>--moe-backend marlin</code>.";
    WARN[cc + "|mxfp4_gptoss"] = "MARLIN MoE has a public report of <code>CUDA error: an illegal memory access</code> under concurrent decode on RTX PRO 6000 with a W4A16 DeepSeek-V4-Flash checkpoint (<a href='https://github.com/vllm-project/vllm/pull/43730'>PR #43730</a>, not in any release up to v0.33.0). It is not specific to gpt-oss.";
  });

  function detectRun() {
    var r = detect($("cfg").value), o = $("det");
    if (r.err) { o.innerHTML = "<span class='no'>" + esc(r.err) + "</span>"; return; }
    $("quant").value = r.s; o.innerHTML = "Detected: <b>" + esc(SCEN.filter(function (x) { return x[0] === r.s; })[0][1]) + "</b> (" + esc(r.why) + ")"; render();
  }
  function errRun() {
    var txt = $("err").value, o = $("errout"), m;
    var fam = /NvFp4/i.test(txt) ? "nvfp4" : /Mxfp4/i.test(txt) ? "mxfp4_gptoss" : null;
    m = txt.match(/backend '?([A-Z0-9_]+)'? does not support the deployment configuration(?: since (.*?))?\.?$/m);
    var h = "";
    if (/vLLM CUTLASS FP8 MoE backend is disabled/.test(txt)) h = "You forced <code>--moe-backend cutlass</code> on a checkpoint type whose code path passes <code>allow_vllm_cutlass=False</code> (quant_method fp8 and ModelOpt FP8). vLLM refuses it before checking the GPU. Use <code>triton</code> or <code>marlin</code>, or remove the flag.";
    else if (/No .* MoE backend supports the deployment configuration/.test(txt)) h = "Auto selection found no usable backend. On NVIDIA GPUs this usually means an unusual setting (LoRA, expert parallel, batch invariance, or a shape) excluded every kernel. Run with <code>VLLM_LOGGING_LEVEL=DEBUG</code>: vLLM logs one <code>does not support the deployment configuration since ...</code> line per rejected backend.";
    else if (m) {
      h = "This error is raised only when a backend was <b>requested explicitly</b> (with <code>--moe-backend</code>, or with the old <code>VLLM_USE_FLASHINFER_MOE_FP4=1</code> plus <code>VLLM_FLASHINFER_MOE_BACKEND</code> variables before v0.24.0). In auto mode the same check is only a debug log and vLLM moves to the next backend. Backend: <code>" + esc(m[1]) + "</code>" + (m[2] ? "; reason: <code>" + esc(m[2]) + "</code>" : "") + ". Remove the flag or variable, or pick a backend marked <b>yes</b> above" + (fam ? " (format set to " + (fam === "nvfp4" ? "NVFP4" : "MXFP4") + ")" : "") + ".";
      if (fam) { $("quant").value = fam; render(); }
    } else h = "No known MoE backend error found in the text.";
    o.innerHTML = h;
  }
  if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded", function () {
    fill();
    ["gpu", "quant", "ver"].forEach(function (id) { $(id).addEventListener("change", render); });
    $("detbtn").addEventListener("click", detectRun);
    $("errbtn").addEventListener("click", errRun);
    render();
  });
  if (typeof module !== "undefined") module.exports = { detect: detect };
})();
