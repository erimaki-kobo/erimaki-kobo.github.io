(function () {
"use strict";
var LL = JSON.parse(document.getElementById("ll-data").textContent);
var J = null, TOKJSON = null, OLLR = null;
import("./jinja-0.5.13.js").then(function (m) { J = m; }).catch(function () {});
fetch("/en/gguf-arch-min-build-lookup/archs.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (j) { if (j && j.ollama_releases) OLLR = j; }).catch(function () {});
function $(id) { return document.getElementById(id); }
function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
function code(s) { return "<code>" + esc(s) + "</code>"; }
function pj(id, label) {
  var t = $(id).value.trim(); if (!t) return { v: null };
  try { return { v: JSON.parse(t) }; } catch (e) { return { err: label + " is not valid JSON: " + e.message }; }
}
function render(t, ctx) { return new J.Template(t).render(ctx); }
function bnum(s) { var m = String(s || "").match(/b?(\d{3,6})/); return m ? +m[1] : null; }
function ollamaBuild(v) {
  if (!OLLR || !v) return null;
  var want = String(v).trim().replace(/^v/, ""), hit = null;
  OLLR.ollama_releases.forEach(function (r) { if (r.release.replace(/^v/, "") === want) hit = r; });
  return hit ? { build: bnum(r2b(hit)), release: hit.release } : { build: null, release: want };
}
function r2b(r) { return r.llama_cpp_build; }
// llama.cpp lists as they stood at a given build (texts the code did not yet name are dropped)
function listsAt(build) {
  if (!build) return LL;
  var keep = function (t) { var f = LL.first[t]; return !f || +f[0] <= build; };
  return { tag: "b" + build, eot: LL.eot.filter(keep), eom: LL.eom.filter(keep), fim_pad: LL.fim_pad, fim_rep: LL.fim_rep, fim_sep: LL.fim_sep, eog: LL.eog.filter(keep) };
}

$("fetch").addEventListener("click", function () {
  var id = $("hf").value.trim().replace(/^https?:\/\/huggingface\.co\//, "").replace(/\/(tree|blob|resolve)\/.*$/, "").replace(/\/+$/, "");
  var st = $("fstatus");
  if (!/^[\w.\-]+\/[\w.\-]+$/.test(id)) { st.textContent = "Enter a model id like Qwen/Qwen3-8B."; return; }
  st.textContent = "Fetching..."; TOKJSON = null; $("res").innerHTML = ""; $("status").textContent = "";
  ["cfg", "gen", "tok", "tmpl"].forEach(function (k) { $(k).value = ""; });
  var base = "https://huggingface.co/" + id + "/resolve/main/";
  function get(f) { return fetch(base + f).then(function (r) { return r.ok ? r.text() : (r.status === 401 || r.status === 403 ? Promise.reject(new Error("gated")) : null); }); }
  Promise.all(["config.json", "generation_config.json", "tokenizer_config.json", "chat_template.jinja"].map(function (f) { return get(f).catch(function (e) { return e; }); })).then(function (r) {
    if (r.some(function (x) { return x instanceof Error && x.message === "gated"; })) { st.textContent = "This model is gated: open its page on Hugging Face, copy the files and paste them below."; return; }
    if (!r[0] || r[0] instanceof Error) { st.textContent = "config.json not found for " + id + "."; return; }
    $("cfg").value = r[0]; $("gen").value = typeof r[1] === "string" ? r[1] : ""; $("tok").value = typeof r[2] === "string" ? r[2] : ""; $("tmpl").value = typeof r[3] === "string" ? r[3] : "";
    var tok = null; try { tok = JSON.parse(r[2]); } catch (e) {}
    var need = !tok || !tok.added_tokens_decoder;
    if (!need) { st.textContent = "Fetched " + id + "."; run(); return; }
    st.textContent = "Fetching tokenizer.json...";
    get("tokenizer.json").then(function (t) { try { TOKJSON = JSON.parse(t); } catch (e) {} st.textContent = "Fetched " + id + "."; run(); }).catch(function () { st.textContent = "Fetched " + id + " (no tokenizer.json)."; run(); });
  });
});
$("go").addEventListener("click", function () { run(); });

var NAMES = { transformers: "Transformers generate()", vllm: "vLLM", sglang: "SGLang", llamacpp: "llama.cpp", ollama: "Ollama", mlx: "MLX-LM" };
function fix(k, mk, e) {
  var id = mk && mk.id !== null ? mk.id : "ID", t = mk ? mk.text : "TOKEN";
  return {
    transformers: code("model.generation_config.eos_token_id = [" + [id].concat(Array.from(e.stop)).filter(function (x, i, a) { return a.indexOf(x) === i; }).join(", ") + "]"),
    vllm: "per request " + code('"stop_token_ids": [' + id + "]") + ", or serve with " + code("--generation-config <dir>") + " holding a generation_config.json whose " + code("eos_token_id") + " lists " + id,
    sglang: "per request " + code('"stop_token_ids": [' + id + "]"),
    llamacpp: "a newer build, or " + code("--override-kv tokenizer.ggml.eos_token_id=int:" + id) + " (the eos token is always added to the end-of-generation set)",
    ollama: "add " + code("PARAMETER stop \"" + t + "\"") + " to the Modelfile and " + code("ollama create"),
    mlx: code("mlx_lm.generate --extra-eos-token \"" + t + "\"") + "; for the server, send " + code('"stop": ["' + t + '"]')
  }[k];
}
function run() {
  var out = $("res"), st = $("status"); out.innerHTML = ""; st.textContent = "";
  var c = pj("cfg", "config.json"), g = pj("gen", "generation_config.json"), t = pj("tok", "tokenizer_config.json");
  var bad = [c, g, t].filter(function (x) { return x.err; })[0];
  if (bad) { st.textContent = bad.err; return; }
  if (!c.v && !t.v) { st.textContent = "Paste at least config.json and tokenizer_config.json, or fetch a model."; return; }
  if (!J && (($("tmpl").value.trim()) || (t.v && t.v.chat_template)) && !$("marker").value.trim()) { st.textContent = "Template engine still loading, try again in a second."; return; }
  var lb = bnum($("lb").value), ov = $("ov").value.trim(), ob = ollamaBuild(ov);
  var F = { config: c.v || {}, gen: g.v, tok: t.v || {}, template: $("tmpl").value, tokjson: TOKJSON, llamalog: $("log").value, modelfile: $("mf").value, marker: $("marker").value.trim() };
  var r = StopCheck.analyze(F, listsAt(lb), J ? render : null);
  if (ob && ob.build) { var ro = StopCheck.analyze(F, listsAt(ob.build), J ? render : null); r.engines.ollama = ro.engines.ollama; r.engines.ollama.atBuild = ob.build; }
  var mk = r.marker, head;
  if (!mk) head = '<div class="verdict v-load">No end-of-turn token found<span>' + esc(r.render.why || "") + ". Type the token the model ends its answer with (for example <code>&lt;|im_end|&gt;</code>) in the last field and check again.</span></div>";
  else if (mk.src === "none") head = '<div class="verdict v-load">The template writes nothing after the answer<span>So the model is expected to end with an eos token itself. The table shows which tokens each engine stops on.</span></div>';
  else head = '<div class="verdict v-ok">The model ends a turn with ' + code(mk.text) + (mk.id !== null ? " (id " + mk.id + ")" : "") + "<span>" + ({ template: "Read from the chat template.", given: "As you entered it.", harmony: "Harmony format: past turns end in <code>&lt;|end|&gt;</code>, a generated final answer ends in <code>&lt;|return|&gt;</code>." }[mk.src]) + "</span></div>";
  var rows = Object.keys(NAMES).map(function (k) {
    var e = r.engines[k], ids = Array.from(e.stop).sort(function (a, b) { return a - b; });
    var list = ids.slice(0, 8).map(function (i) { return code(i + (r.table.byId.has(i) ? " " + r.table.byId.get(i) : "")); }).join(" ") + (ids.length > 8 ? " +" + (ids.length - 8) : "");
    if (k === "ollama" && e.strings.length) list += "<br>stop strings: " + e.strings.map(code).join(" ");
    var v = { stops: '<span class="s y">stops</span>', "stops-string": '<span class="s y">stops (stop string)</span>', "runs-on": '<span class="s n">does not stop at end of turn</span>', "no-marker": "see stop list", unknown: "?" }[e.verdict];
    var from = esc(e.from) + (e.atBuild ? " (Ollama " + esc(ob.release) + " bundles b" + e.atBuild + ")" : "") + (e.predicted ? ". Paste the load log for the exact set." : "") + (e.note ? " " + esc(e.note) : "") + (e.rules && e.rules.length ? " " + esc(e.rules.join("; ")) : "");
    return "<tr><td>" + NAMES[k] + "</td><td>" + v + "</td><td>" + (list || "none") + "</td><td>" + from + (e.verdict === "runs-on" ? "<br><strong>Fix:</strong> " + fix(k, mk, e) : "") + "</td></tr>";
  }).join("");
  var notes = r.notes.slice();
  if (lb && lb < 2702) notes.push("llama.cpp builds before b2702 (2024-04-21) stop only on the GGUF eos token.");
  var ovn = ov.replace(/^v/, "").split(".").map(Number);
  if (ov && ovn.length >= 2 && (ovn[0] === 0 && ((ovn[1] > 5 || (ovn[1] === 5 && (ovn[2] || 0) >= 12)) && (ovn[1] < 31 || (ovn[1] === 31 && (ovn[2] || 0) <= 1))))) notes.push("Ollama " + esc(ov) + " can run some models in its own Go engine instead of llama.cpp (0.5.12 to 0.31.1); the Ollama row assumes llama.cpp.");
  if (ov && ob && !ob.build) notes.push("Ollama " + esc(ov) + " is not in the release table; Ollama was checked with the newest llama.cpp lists.");
  if (!r.fullVocab && !r.table.byId.size) notes.push("No token list found in tokenizer_config.json; token ids could not be named. Fetch the model or paste a tokenizer_config.json with added_tokens_decoder.");
  out.innerHTML = head + '<div class="tw"><table><thead><tr><th>Engine</th><th>End of turn</th><th>Tokens it stops on</th><th>Where they come from</th></tr></thead><tbody>' + rows + "</tbody></table></div>" + (notes.length ? '<ul class="note">' + notes.map(function (n) { return "<li>" + n + "</li>"; }).join("") + "</ul>" : "");
  window.lastStopCheck = r;
}
window.stopRun = run;
})();
