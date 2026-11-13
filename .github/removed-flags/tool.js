(function () {
"use strict";
var D = JSON.parse(document.getElementById("rf-data").textContent);
function $(id) { return document.getElementById(id); }
function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
function code(s) { return "<code>" + esc(s) + "</code>"; }
function vnum(s) {
  var m = String(s).match(/(\d+)\.(\d+)\.(\d+)(?:\.post(\d+))?/); if (!m) { m = String(s).match(/(\d+)\.(\d+)/); if (!m) return null; return [+m[1], +m[2], 0, 0]; }
  return [+m[1], +m[2], +m[3], m[4] ? +m[4] : 0];
}
function cmp(a, b) { for (var i = 0; i < 4; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1; return 0; }
// index of the newest release at or below a version string
function idxOf(L, v) {
  var x = vnum(v); if (!x) return null;
  var best = -1; for (var i = 0; i < L.tags.length; i++) if (cmp(vnum(L.tags[i]), x) <= 0) best = i;
  return best;
}
function span(L, r) { return r.map(function (p) { return L.tags[p[0]] + (p[1] === p[0] ? "" : " to " + L.tags[p[1]]); }).join(", "); }
function parse(txt) {
  var out = { flags: [], env: [], fields: [], isChat: /"messages"\s*:/.test(txt), py: /SamplingParams\s*\(/.test(txt) };
  function push(a, x) { if (a.indexOf(x) < 0) a.push(x); }
  var m, re = /(?:^|[\s'"(\[,])(--[A-Za-z0-9][A-Za-z0-9_\-.]*)/g;
  while ((m = re.exec(txt))) push(out.flags, m[1]);
  re = /\b(VLLM_[A-Z0-9_]+)\b/g; while ((m = re.exec(txt))) push(out.env, m[1]);
  var o = null; try { o = JSON.parse(txt); } catch (e) {}
  if (o && typeof o === "object" && !Array.isArray(o)) {
    Object.keys(o).forEach(function (k) { if (k !== "extra_body") push(out.fields, k); });
    if (o.extra_body && typeof o.extra_body === "object") Object.keys(o.extra_body).forEach(function (k) { push(out.fields, k); });
  } else {
    re = /ignored:\s*\{([^}]*)\}/g; while ((m = re.exec(txt))) (m[1].match(/'([^']+)'/g) || []).forEach(function (s) { push(out.fields, s.slice(1, -1)); });
    re = /removed guided-decoding field\(s\)\s*\[([^\]]*)\]/g; while ((m = re.exec(txt))) (m[1].match(/'([^']+)'/g) || []).forEach(function (s) { push(out.fields, s.slice(1, -1)); });
    var sp = txt.match(/SamplingParams\s*\(([\s\S]*?)\)\s*$/m) || txt.match(/SamplingParams\s*\(([\s\S]*)/);
    if (sp) { re = /(?:^|[,(\s])([a-z_][a-z0-9_]*)\s*=/g; while ((m = re.exec(sp[1]))) push(out.fields, m[1]); }
    re = /extra_body\s*=\s*\{([\s\S]*?)\}/g; while ((m = re.exec(txt))) (m[1].match(/["']([a-z_][a-z0-9_]*)["']\s*:/g) || []).forEach(function (s) { push(out.fields, s.replace(/["':\s]/g, "")); });
    re = /unexpected keyword argument '([a-z_][a-z0-9_]*)'/g; while ((m = re.exec(txt))) { push(out.fields, m[1]); out.py = true; }
  }
  return out;
}
function H(lib, name) { var h = D.hints[lib] && D.hints[lib][name]; return h || null; }
function verdict(lib, raw, name, mine, label) {
  var L = D.libs[lib], r = L.names[name], last = L.tags.length - 1, latest = L.tags[last];
  var hint = H(lib, name), row = { name: raw, kind: label, cls: "", text: "", have: "" };
  if (!r) {
    row.have = "never";
    row.cls = "n"; row.text = "Not a name in any " + (lib === "sglang_cli" ? "SGLang" : "vLLM") + " release from " + L.tags[0] + " to " + latest + ".";
    return row;
  }
  row.have = span(L, r);
  var now = r[r.length - 1][1] === last;
  var mi = mine ? idxOf(L, mine) : null, inMine = null;
  if (mi !== null && mi >= 0) inMine = r.some(function (p) { return p[0] <= mi && mi <= p[1]; });
  if (now) { row.cls = "y"; row.text = "Current in " + latest + "."; if (inMine === false) { row.cls = "n"; row.text = "Added in " + L.tags[r[0][0]] + "; your " + esc(mine) + " is older. Upgrade, or drop it."; } }
  else { row.cls = "n"; row.text = "Removed after " + L.tags[r[r.length - 1][1]] + "."; if (inMine === true) { row.cls = "y"; row.text = "Still there in your " + esc(mine) + "; removed after " + L.tags[r[r.length - 1][1]] + "."; } }
  if (hint) row.text += " " + hint;
  return row;
}
function run(push) {
  var txt = $("q").value, eng = $("eng").value, mine = $("v").value.trim(), out = $("res"), st = $("status");
  out.innerHTML = ""; st.textContent = "";
  if (!txt.trim()) { st.textContent = "Paste a command, an error message, environment variables or a request body."; return; }
  var p = parse(txt);
  var sg = eng === "sglang" || (eng === "auto" && /sglang/i.test(txt));
  var rows = [];
  p.flags.forEach(function (raw) {
    var lib = sg ? "sglang_cli" : "vllm_cli", L = D.libs[lib];
    var base = raw.split("=")[0], n = base;
    if (!sg) { n = "--" + n.slice(2).replace(/_/g, "-"); if (n.indexOf(".") > 0) n = n.split(".")[0]; }
    var row = verdict(lib, raw, n, mine, sg ? "SGLang argument" : "vLLM argument");
    if (row.have === "never" && /^--no-/.test(n) && L.names["--" + n.slice(5)]) {
      var b = "--" + n.slice(5), r = L.names[b];
      row.cls = ""; row.have = "(negated form)"; row.text = "The negated form of " + code(b) + " (" + span(L, r) + "). Whether " + code(n) + " is accepted depends on the release: see the <a href=\"#negated\">note on --no-</a>.";
    } else if (row.have === "never") {
      var other = sg ? D.libs.vllm_cli.names[n] : D.libs.sglang_cli.names[n];
      if (other) row.text += " It is " + (sg ? "a vLLM" : "an SGLang") + " argument; check which server you are starting.";
    }
    if (row.cls === "n") {
      // argparse (allow_abbrev) reads an unambiguous prefix of a current argument as that argument
      var ti = mine ? idxOf(L, mine) : null; if (ti === null || ti < 0) ti = L.tags.length - 1;
      var cand = Object.keys(L.names).filter(function (k) { return k !== n && k.indexOf(n) === 0 && L.names[k].some(function (p) { return p[0] <= ti && ti <= p[1]; }); });
      if (cand.length === 1) row.text += " <strong>No error in " + esc(L.tags[ti]) + "</strong>: the parser accepts unambiguous prefixes, so this is read as " + code(cand[0]) + ".";
      else if (cand.length > 1) row.text += " In " + esc(L.tags[ti]) + " the error is \"ambiguous option\" (it could match " + cand.slice(0, 4).map(code).join(", ") + (cand.length > 4 ? ", ..." : "") + "), not \"unrecognized arguments\".";
    }
    if (n !== base && !sg && base.indexOf(".") > 0) row.text += " (Read as " + code(n) + "; the part after the dot is a key inside that JSON argument.)";
    rows.push(row);
  });
  p.env.forEach(function (n) { var row = verdict("vllm_env", n, n, mine, "vLLM environment variable"); if (row.cls === "n" && row.have !== "never") row.text += " <strong>No error</strong>: vLLM simply does not read it (from v0.17.0 it logs \"Unknown vLLM environment variable detected\")."; rows.push(row); });
  p.fields.forEach(function (n) {
    if (p.py && !p.isChat) { var row = verdict("vllm_sampling_params", n, n, mine, "SamplingParams argument"); if (row.cls === "n" && row.have !== "never") row.text += " Python raises <code>TypeError</code>."; rows.push(row); return; }
    var lib = p.isChat || !D.libs.vllm_completion.names[n] ? "vllm_chat" : "vllm_completion";
    if (["model", "messages", "prompt"].indexOf(n) >= 0 && D.libs[lib].names[n]) return;
    var row2 = verdict(lib, n, n, mine, "request field (" + (lib === "vllm_chat" ? "chat" : "completions") + ")");
    if (row2.cls === "n" && row2.have !== "never") row2.text += " <strong>No error</strong>: the server drops it (see <a href=\"#silent\">how</a>).";
    if (row2.have === "never" && D.libs.vllm_sampling_params.names[n]) { row2.cls = ""; row2.text = "Not a server field, but a " + code("SamplingParams") + " argument (" + span(D.libs.vllm_sampling_params, D.libs.vllm_sampling_params.names[n]) + ")."; }
    rows.push(row2);
  });
  if (!rows.length) { st.textContent = "Found no --arguments, VLLM_ variables or request fields in that text."; return; }
  var bad = rows.filter(function (r) { return r.cls === "n"; }).length;
  var head = bad ? '<div class="verdict v-bad">' + bad + " of " + rows.length + " names will not work" + (mine ? " in " + esc(mine) : " in the newest release") + "<span>Details and replacements below.</span></div>" : '<div class="verdict v-ok">All ' + rows.length + " names are valid" + (mine ? " in " + esc(mine) : " in the newest release") + "</div>";
  out.innerHTML = head + '<div class="tw"><table><thead><tr><th>Name</th><th>Kind</th><th>Releases that have it</th><th>Verdict</th></tr></thead><tbody>' + rows.map(function (r) {
    return "<tr><td>" + code(r.name) + "</td><td>" + esc(r.kind) + "</td><td>" + esc(r.have === "never" ? "none" : r.have) + "</td><td>" + (r.cls ? '<span class="s ' + r.cls + '">' + (r.cls === "y" ? "ok" : "problem") + "</span> " : "") + r.text + "</td></tr>";
  }).join("") + "</tbody></table></div>";
  if (push) { try { var u = new URLSearchParams(); if (txt.length < 600) u.set("q", txt); if (mine) u.set("v", mine); if (eng !== "auto") u.set("e", eng); history.replaceState(null, "", location.pathname + "?" + u.toString() + "#lookup"); } catch (e) {} }
}
window.rfRun = run;
$("go").addEventListener("click", function () { run(true); });
var fi = $("filter");
if (fi) fi.addEventListener("input", function () { var v = fi.value.trim().toLowerCase(); document.querySelectorAll("table.full tbody tr").forEach(function (r) { r.style.display = !v || r.textContent.toLowerCase().indexOf(v) >= 0 ? "" : "none"; }); });
try { var sp = new URLSearchParams(location.search); if (sp.get("q")) { $("q").value = sp.get("q"); if (sp.get("v")) $("v").value = sp.get("v"); if (sp.get("e")) $("eng").value = sp.get("e"); run(false); } } catch (e) {}
})();
