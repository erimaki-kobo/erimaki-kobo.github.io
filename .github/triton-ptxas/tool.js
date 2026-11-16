// Lookup for en/triton-ptxas-arch-lookup. __D__ is replaced by data.json at build time.
// The pure functions (parseError, resolve, verdict) are also loaded by check.js under Node.
var D = __D__;
var GPUS = [
  [121, "12.1  DGX Spark (GB10)"],
  [120, "12.0  RTX 50 series, RTX PRO Blackwell"],
  [110, "11.0  Jetson AGX Thor"],
  [103, "10.3  B300 / GB300"],
  [100, "10.0  B200 / GB200"],
  [90, "9.0  H100, H200"],
  [89, "8.9  RTX 40 series, L4, L40S"],
  [86, "8.6  RTX 30 series, A10, A40"],
  [80, "8.0  A100, A30"]
];
function vkey(v) { return v.split(".").map(Number); }
function vcmp(a, b) { var x = vkey(a), y = vkey(b); for (var i = 0; i < 4; i++) { var d = (x[i] || 0) - (y[i] || 0); if (d) return d; } return 0; }
var TRITONS = Object.keys(D.triton).sort(vcmp);
var TORCHES = Object.keys(D.torch).sort(vcmp);

// Reads a pasted error. Returns {cap, name, blackwell} or null.
function parseError(text) {
  var m = /Value\s+['‘’"`]?(sm_(\d{2,3})([af]?))['‘’"`]?\s+is not defined for option\s+['‘’"`]?gpu-name/i.exec(text) ||
          /--gpu-name[= ](sm_(\d{2,3})([af]?))/i.exec(text) || /\b(sm_(\d{2,3})([af]?))\b/i.exec(text);
  if (!m) return null;
  return { cap: parseInt(m[2], 10), name: m[1].toLowerCase(), blackwell: /ptxas-blackwell/i.test(text) };
}
// kind: "triton" | "torch" | "vllm"; returns {triton, torch, vllm, chain}
function resolve(kind, ver) {
  var r = { triton: null, torch: null, vllm: null };
  if (kind === "vllm") {
    for (var i = 0; i < D.vllm.length; i++) if (D.vllm[i].v === ver) { r.vllm = ver; r.torch = D.vllm[i].torch; }
    if (!r.torch) return null;
  }
  if (kind === "torch") r.torch = ver;
  if (r.torch) { if (!D.torch[r.torch]) return null; r.triton = D.torch[r.torch].triton; }
  if (kind === "triton") r.triton = ver;
  return D.triton[r.triton] ? r : null;
}
function firstOk(cap) {
  var t = null, i;
  for (i = 0; i < TRITONS.length; i++) if (D.triton[TRITONS[i]].res[cap].ok) { t = TRITONS[i]; break; }
  if (!t) return null;
  var torch = null, vllm = null;
  for (i = 0; i < TORCHES.length; i++) if (vcmp(D.torch[TORCHES[i]].triton, t) >= 0) { torch = TORCHES[i]; break; }
  for (i = 0; i < D.vllm.length; i++) if (vcmp(D.torch[D.vllm[i].torch].triton, t) >= 0) { vllm = D.vllm[i].v; break; }
  return { triton: t, torch: torch, vllm: vllm };
}
// The answer for one Triton release and one compute capability.
function verdict(triton, cap) {
  var T = D.triton[triton], e = T.res[String(cap)];
  var out = { triton: triton, cap: cap, tool: e.tool, ver: e.ver, name: e.name, ok: e.ok, first: firstOk(String(cap)) };
  if (!e.ok) {
    out.env = e.var; out.cuda = e.cuda.slice();
    out.hyphen = e.var.indexOf("-") >= 0;
    out.ignored = e.tool === "ptxas-blackwell" ? "TRITON_PTXAS_PATH" : null;   // the variable people set that this release does not read for this GPU
  }
  return out;
}
function fixLines(v) {
  if (v.ok || !v.cuda.length) return [];
  var p = "/usr/local/cuda/bin/ptxas";
  if (v.hyphen) return ["env '" + v.env + "=" + p + "' python your_script.py"];
  return ["export " + v.env + "=" + p];
}
if (typeof module !== "undefined") module.exports = { D: D, parseError: parseError, resolve: resolve, verdict: verdict, firstOk: firstOk, fixLines: fixLines, TRITONS: TRITONS, TORCHES: TORCHES, GPUS: GPUS };

if (typeof document !== "undefined") (function () {
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function opt(sel, value, label, group) { var o = document.createElement("option"); o.value = value; o.textContent = label; (group || sel).appendChild(o); return o; }
  var gpu = $("gpu"), ver = $("ver"), err = $("err"), out = $("out"), i;
  for (i = 0; i < GPUS.length; i++) opt(gpu, GPUS[i][0], GPUS[i][1]);
  function grp(label) { var g = document.createElement("optgroup"); g.label = label; ver.appendChild(g); return g; }
  var g1 = grp("PyTorch (PyPI wheel)"), g2 = grp("Triton"), g3 = grp("vLLM");
  for (i = TORCHES.length - 1; i >= 0; i--) opt(ver, "torch|" + TORCHES[i], "PyTorch " + TORCHES[i] + "  (Triton " + D.torch[TORCHES[i]].triton + ")", g1);
  for (i = TRITONS.length - 1; i >= 0; i--) opt(ver, "triton|" + TRITONS[i], "Triton " + TRITONS[i], g2);
  for (i = D.vllm.length - 1; i >= 0; i--) opt(ver, "vllm|" + D.vllm[i].v, "vLLM " + D.vllm[i].v + "  (PyTorch " + D.vllm[i].torch + ")", g3);
  gpu.value = "121"; ver.value = "torch|2.9.0";
  function cudaRange(c) { return c.length === 1 ? "CUDA " + c[0] : "CUDA " + c[0] + " to " + c[c.length - 1]; }
  function render() {
    var kv = ver.value.split("|"), r = resolve(kv[0], kv[1]), cap = parseInt(gpu.value, 10);
    if (!r) { out.innerHTML = ""; return; }
    var v = verdict(r.triton, cap), T = D.triton[r.triton], h = "";
    var chain = (r.vllm ? "vLLM " + r.vllm + " pins PyTorch " + r.torch + ", which pins " : r.torch ? "PyTorch " + r.torch + " pins " : "") + "Triton " + r.triton;
    h += '<div class="res ' + (v.ok ? "" : "bad") + '"><div class="big ' + (v.ok ? "ok" : "no") + '">' + (v.ok ? "Bundled ptxas knows " : "Bundled ptxas does not know ") + esc(v.name) + "</div>";
    h += '<div class="log">' + esc(chain) + ". For compute capability " + (cap / 10).toFixed(1) + " it runs <code>" + esc(v.tool) + " --gpu-name=" + esc(v.name) + "</code>, and the bundled <code>" + esc(v.tool) + "</code> is the CUDA " + esc(v.ver) + " build.</div>";
    if (v.ok) {
      h += '<div class="log">This step passes. If you still see the error, check that <code>' + esc(T.env[v.tool]) + "</code> is not set to an older ptxas: when it is set, Triton uses that binary instead of the bundled one.</div>";
    } else {
      h += '<div class="log"><b>Error you get:</b> <code>' + esc(v.tool) + " fatal   : Value '" + esc(v.name) + "' is not defined for option 'gpu-name'</code></div>";
    }
    h += "</div>";
    if (!v.ok) {
      if (v.first) {
        h += '<div class="res"><b>Fix 1, upgrade:</b> Triton ' + esc(v.first.triton) + " is the first release whose bundled binary knows this GPU. That is PyTorch " + esc(v.first.torch || "(none on PyPI yet)") + " or newer" + (v.first.vllm ? ", or vLLM " + esc(v.first.vllm) + " or newer" : "") + ".</div>";
      }
      if (v.cuda.length) {
        h += '<div class="res"><b>Fix 2, point Triton ' + esc(r.triton) + " at a newer ptxas:</b><br><code>" + esc(fixLines(v)[0]) + "</code>";
        h += '<div class="log">The file must be the ptxas of ' + esc(cudaRange(v.cuda)) + " (check with <code>ptxas --version</code>). Other releases either do not know " + esc(v.name) + " or are rejected by Triton " + esc(r.triton) + ".</div>";
        if (v.ignored) h += '<div class="log"><b>' + esc(v.ignored) + " has no effect here.</b> For this GPU Triton " + esc(r.triton) + " reads <code>" + esc(v.env) + "</code>.</div>";
        if (v.hyphen) h += '<div class="log">The variable name contains a hyphen, so <code>export</code> rejects it in bash. Use <code>env</code> as shown, set it in Python with <code>os.environ</code> before importing triton, or replace the file <code>triton/backends/nvidia/bin/ptxas-blackwell</code> with a symlink.</div>';
        h += '<div class="log">If the file does not exist at that path, Triton silently falls back to the bundled binary and the error stays the same.</div></div>';
      } else {
        h += '<div class="res warn"><b>No environment-variable fix on Triton ' + esc(r.triton) + ":</b> every ptxas that knows " + esc(v.name) + " reports a CUDA release that this Triton rejects (<code>Triton only support CUDA 10.0 or higher, but got CUDA version: ...</code>). Upgrade.</div>";
      }
    }
    out.innerHTML = h;
  }
  $("errbtn").addEventListener("click", function () {
    var p = parseError(err.value), msg = $("errmsg");
    if (!p) { msg.textContent = "No sm_NNN name found in the text."; return; }
    var known = false;
    for (var i = 0; i < GPUS.length; i++) if (GPUS[i][0] === p.cap) known = true;
    if (!known) { msg.textContent = "Found " + p.name + ", which is not one of the GPUs in this table."; return; }
    gpu.value = String(p.cap);
    var hint = "Found " + p.name + ".";
    if (p.cap >= 100 && !/[af]$/.test(p.name)) { hint += " No 'a' suffix: that is Triton 3.2.0 or older (PyTorch 2.6 or older)."; ver.value = "triton|3.2.0"; }
    else if (p.blackwell) hint += " The message names ptxas-blackwell: that is Triton 3.3.x or 3.6.0 and newer.";
    msg.textContent = hint; render();
  });
  gpu.addEventListener("change", render); ver.addEventListener("change", render); render();
})();
