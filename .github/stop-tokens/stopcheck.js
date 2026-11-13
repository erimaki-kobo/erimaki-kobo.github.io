// stopcheck.js: which token ends a chat turn, and which inference engines stop on it.
// Pure functions; the page passes in the model files and a Jinja renderer.
// Engine rules read from: Transformers v5.22.2, vLLM v0.33.0, SGLang v0.5.23, MLX-LM v0.32.2,
// llama.cpp b12352 (LL = lists extracted from src/llama-vocab.cpp), Ollama v0.40.16.
(function (root) {
"use strict";

function ids(v) {
  if (v === null || v === undefined || v === false) return [];
  if (Array.isArray(v)) return v.filter(function (x) { return Number.isInteger(x); });
  return Number.isInteger(v) ? [v] : [];
}
function tokText(v) { return typeof v === "string" ? v : (v && typeof v === "object" && typeof v.content === "string" ? v.content : null); }

// token table from tokenizer_config.added_tokens_decoder, tokenizer.json added_tokens and (optionally) its vocab
function table(tok, tj) {
  var byText = new Map(), byId = new Map(), special = new Set();
  function add(id, text, isSpecial) {
    id = +id; if (!Number.isInteger(id) || typeof text !== "string") return;
    if (!byId.has(id)) byId.set(id, text);
    if (!byText.has(text)) byText.set(text, id);
    if (isSpecial) special.add(id);
  }
  var atd = tok && tok.added_tokens_decoder;
  if (atd && typeof atd === "object") Object.keys(atd).forEach(function (k) { add(k, tokText(atd[k]), atd[k].special !== false); });
  if (tj && Array.isArray(tj.added_tokens)) tj.added_tokens.forEach(function (a) { add(a.id, a.content, a.special !== false); });
  var full = false;
  if (tj && tj.model && tj.model.vocab) {
    var v = tj.model.vocab;
    if (Array.isArray(v)) v.forEach(function (p, i) { add(i, Array.isArray(p) ? p[0] : p, false); });
    else Object.keys(v).forEach(function (k) { add(v[k], k, false); });
    full = true;
  }
  return { byText: byText, byId: byId, special: special, full: full };
}

function chatTemplate(tok, tmplFile) {
  if (typeof tmplFile === "string" && tmplFile.trim()) return tmplFile;
  var ct = tok && tok.chat_template;
  if (typeof ct === "string") return ct;
  if (Array.isArray(ct)) {
    var d = ct.filter(function (x) { return x && x.name === "default"; })[0] || ct[0];
    return d && typeof d.template === "string" ? d.template : null;
  }
  return null;
}

var SENT = "QQ_ANSWER_7f3e9";
// Render [user, assistant] and read what the template writes right after the assistant's text.
function endMarker(T, tok, render) {
  if (!T || !render) return { status: "none", why: T ? "no renderer" : "no chat template" };
  var out, bos = tokText(tok && tok.bos_token) || "", eos = tokText(tok && tok.eos_token) || "";
  try {
    out = render(T, {
      messages: [{ role: "user", content: "Hi" }, { role: "assistant", content: SENT }],
      add_generation_prompt: false, bos_token: bos, eos_token: eos,
      pad_token: tokText(tok && tok.pad_token) || "", unk_token: tokText(tok && tok.unk_token) || "",
      tools: [], documents: [], date_string: "13 Nov 2026"
    });
  } catch (e) { return { status: "error", why: String(e && e.message || e).slice(0, 200) }; }
  var i = out.lastIndexOf(SENT);
  if (i < 0) return { status: "error", why: "the template did not print the assistant message" };
  return { status: "ok", after: out.slice(i + SENT.length, i + SENT.length + 80) };
}

// longest known token text at the start of s (after optional whitespace)
function matchToken(s, tab) {
  var t = s.replace(/^[ \t\r\n]+/, ""), best = null;
  tab.byText.forEach(function (id, text) {
    if (text.length >= 2 && /[^A-Za-z0-9 ]/.test(text) && t.indexOf(text) === 0 && (!best || text.length > best.text.length)) best = { id: id, text: text };
  });
  return best;
}

function analyze(F, LL, render) {
  var cfg = F.config || {}, gen = F.gen, tok = F.tok || {}, tab = table(tok, F.tokjson);
  var notes = [];
  var tcfg = cfg.text_config || cfg.llm_config || cfg.language_config || null;
  var tokEosText = tokText(tok.eos_token);
  var tokEos = tokEosText !== null && tab.byText.has(tokEosText) ? tab.byText.get(tokEosText) : null;
  if (tokEosText && tokEos === null) notes.push("eos_token " + JSON.stringify(tokEosText) + " is not among the added tokens; paste tokenizer.json to resolve it.");
  var cfgEos = ids(cfg.eos_token_id), txtEos = tcfg ? ids(tcfg.eos_token_id) : [];
  var genHas = !!(gen && typeof gen === "object"), genEos = genHas ? ids(gen.eos_token_id) : [];
  // Transformers GenerationConfig.from_model_config: top-level value, else the decoder/text_config value
  var fromModel = cfg.eos_token_id !== undefined && cfg.eos_token_id !== null ? cfgEos : txtEos;

  // ---- end of the assistant turn ----
  var T = chatTemplate(tok, F.template), em = endMarker(T, tok, render), marker = null;
  if (F.marker) {
    var mt = String(F.marker).trim();
    marker = tab.byText.has(mt) ? { id: tab.byText.get(mt), text: mt, src: "given" } : (/^\d+$/.test(mt) ? { id: +mt, text: tab.byId.get(+mt) || "?", src: "given" } : { id: null, text: mt, src: "given" });
  } else if (em.status === "ok") {
    var m = matchToken(em.after, tab);
    if (m) {
      marker = { id: m.id, text: m.text, src: "template" };
      // harmony (gpt-oss): history turns end in <|end|>, a generated final answer ends in <|return|>
      if (m.text === "<|end|>" && tab.byText.has("<|return|>")) { marker = { id: tab.byText.get("<|return|>"), text: "<|return|>", src: "harmony" }; }
      // Solar Open: history turns end in <|end|>, a generated answer ends in <|flush|> (a tool call in <|calls|>)
      else if (m.text === "<|end|>" && tab.byText.has("<|flush|>") && tab.byText.has("<|calls|>")) { marker = { id: tab.byText.get("<|flush|>"), text: "<|flush|>", src: "solar" }; }
    } else marker = { id: null, text: "", src: "none" };
  }

  // ---- engines ----
  function set(list) { var s = new Set(); list.forEach(function (x) { ids(x).forEach(function (i) { s.add(i); }); }); return s; }
  var E = {};
  E.transformers = { stop: set([genHas ? genEos : fromModel]), from: genHas ? "generation_config.json eos_token_id" : "config.json eos_token_id (no generation_config.json)" };
  if (genHas && !genEos.length) notes.push("generation_config.json has no eos_token_id: Transformers' generate() then has no end token at all.");
  E.vllm = { stop: set([tokEos, genHas ? genEos : fromModel]), from: "tokenizer eos_token + " + (genHas ? "generation_config.json" : "config.json (no generation_config.json)") };
  var sgAdd = ["<|eom_id|>", "<|content_model_end_sampling|>", "<|ifm|im_end|>"].filter(function (t) { return tab.byText.has(t); }).map(function (t) { return tab.byText.get(t); });
  E.sglang = { stop: set([cfgEos, genEos, tokEos, sgAdd]), from: "config.json + generation_config.json + tokenizer eos_token + built-in extras" };
  E.mlx = { stop: set([genEos.length ? genEos : cfgEos, tokEos]), from: (genEos.length ? "generation_config.json" : "config.json") + " + tokenizer eos_token" };
  if (!genEos.length && !cfgEos.length) E.mlx.note = "No eos_token_id in config.json or generation_config.json; MLX-LM may use a per-model default.";

  // llama.cpp: exact from a pasted load log, else predicted for a fresh conversion
  var ll = llamaEOG(F, LL, tab, tok, cfg, tcfg);
  E.llamacpp = ll;
  var stopStr = [];
  (F.modelfile || "").replace(/^\s*PARAMETER\s+stop\s+(.+?)\s*$/gim, function (_, v) { stopStr.push(v.replace(/^"(.*)"$/, "$1")); return _; });
  E.ollama = { stop: ll.stop, strings: stopStr, from: "llama.cpp EOG of the GGUF + Modelfile stop strings", predicted: ll.predicted };

  Object.keys(E).forEach(function (k) {
    var e = E[k];
    if (!marker || marker.src === "none") { e.verdict = marker ? "no-marker" : "unknown"; return; }
    if (marker.id !== null && e.stop.has(marker.id)) e.verdict = "stops";
    else if (k === "ollama" && e.strings.indexOf(marker.text) >= 0) e.verdict = "stops-string";
    else e.verdict = "runs-on";
  });
  return { marker: marker, render: em, tokEos: tokEos, tokEosText: tokEosText, cfgEos: cfgEos, txtEos: txtEos, genHas: genHas, genEos: genEos, engines: E, notes: notes, table: tab, fullVocab: tab.full, template: !!T };
}

function llamaEOG(F, LL, tab, tok, cfg, tcfg) {
  var log = F.llamalog || "";
  var got = [], m, re = /-\s+(\d+)\s+\('((?:[^']|'(?!\)))*)'\)/g, sec = log.indexOf("printing all EOG tokens");
  if (sec >= 0) {
    var part = log.slice(sec);
    while ((m = re.exec(part))) got.push(+m[1]);
    if (got.length) return { stop: new Set(got), from: "your llama.cpp load log", predicted: false };
  }
  // predicted: GGUF eos from tokenizer_config eos_token, else config.json eos_token_id (integer), as gguf-py's SpecialVocab does
  var s = new Set(), why = [];
  var eosT = tokText(tok.eos_token), eos = eosT !== null && tab.byText.has(eosT) ? tab.byText.get(eosT) : null;
  if (eos === null) { var c = Number.isInteger(cfg.eos_token_id) ? cfg.eos_token_id : (tcfg && Number.isInteger(tcfg.eos_token_id) ? tcfg.eos_token_id : null); eos = c; }
  function has(t) { return tab.byText.has(t); }
  LL.fim_pad.concat(LL.fim_rep, LL.fim_sep).forEach(function (t) { if (has(t)) s.add(tab.byText.get(t)); });
  LL.eog.forEach(function (t) { if (has(t)) s.add(tab.byText.get(t)); });
  LL.eot.concat(LL.eom).forEach(function (t) { if (has(t)) s.add(tab.byText.get(t)); });
  if (eos !== null) s.add(eos);
  var idOf = function (t) { return tab.byText.get(t); };
  if (has("<|end|>") && ((has("<|return|>") && has("<|call|>")) || (has("<|calls|>") && has("<|flush|>")))) { s.delete(idOf("<|end|>")); why.push("<|end|> removed (harmony / solar-open rule)"); }
  if (has("</s>") && s.has(idOf("</s>")) && (has('<rfl:parameter name="') || has("<|tool_response>") || has("<|plamo:eos|>"))) { s.delete(idOf("</s>")); why.push("</s> treated as a normal token"); }
  return { stop: s, from: "predicted for a GGUF converted with llama.cpp b" + LL.tag.slice(1), predicted: true, rules: why, eos: eos };
}

root.StopCheck = { analyze: analyze, table: table, chatTemplate: chatTemplate, ids: ids };
})(typeof window !== "undefined" ? window : globalThis);
