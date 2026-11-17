(function () {
"use strict";
var D = JSON.parse(document.getElementById("pt-data").textContent);
var ORDER = ["peft", "transformers", "trl"], NAME = { peft: "PEFT", transformers: "Transformers", trl: "TRL" };
function $(id) { return document.getElementById(id); }
function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
function code(s) { return "<code>" + esc(s) + "</code>"; }
function vnum(s) {
  var m = String(s).match(/(\d+)\.(\d+)\.(\d+)(?:\.post(\d+))?/); if (!m) { m = String(s).match(/(\d+)\.(\d+)/); if (!m) return null; return [+m[1], +m[2], 0, 0]; }
  return [+m[1], +m[2], +m[3], m[4] ? +m[4] : 0];
}
function cmp(a, b) { for (var i = 0; i < 4; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1; return 0; }
// index of the newest release at or below a version string; null if no version, -1 if older than every release
function idxOf(L, v) {
  var x = vnum(v); if (!x) return null;
  var best = -1; for (var i = 0; i < L.tags.length; i++) if (cmp(vnum(L.tags[i]), x) <= 0) best = i;
  return best;
}
function span(L, r) { return r.map(function (p) { return L.tags[p[0]] + (p[1] === p[0] ? "" : " to " + L.tags[p[1]]); }).join(", "); }
function inR(r, i) { return r.some(function (p) { return p[0] <= i && i <= p[1]; }); }
function merge(a, b) {
  var all = a.concat(b).map(function (p) { return [p[0], p[1]]; }).sort(function (x, y) { return x[0] - y[0]; }), out = [];
  all.forEach(function (p) { var l = out[out.length - 1]; if (l && p[0] <= l[1] + 1) l[1] = Math.max(l[1], p[1]); else out.push(p); });
  return out;
}
function libOf(cls) { for (var i = 0; i < ORDER.length; i++) if (D.libs[ORDER[i]].classes[cls]) return ORDER[i]; return null; }
function aliasOf(C, arg) { for (var k in C.alias) { var s = k.split(">"); if (s[0] === arg) return { to: s[1], r: C.alias[k] }; } return null; }
function pip(lib, tag) { return code('pip install -U "' + lib + ">=" + tag.replace(/^v/, "") + '"'); }
function whoHas(arg, skipCls) {
  var out = [];
  ORDER.forEach(function (lib) { var L = D.libs[lib]; Object.keys(L.classes).forEach(function (c) {
    if (c !== skipCls && L.classes[c].p[arg]) out.push({ lib: lib, cls: c, r: L.classes[c].p[arg] }); }); });
  var rank = function (x) { var i = D.main.indexOf(x.cls); return i < 0 ? 99 : i; };
  out.sort(function (a, b) { return rank(a) - rank(b) || (a.cls < b.cls ? -1 : 1); });
  return out;
}
// one (class, argument) pair -> a row
function verdict(cls, arg, mine, viaCls) {
  var lib = libOf(cls), row = { name: arg, on: viaCls || cls, lib: lib, cls: "", have: "", text: "", need: null };
  if (!lib) { row.cls = "n"; row.have = "none"; row.text = code(cls) + " is not a class this page tracks (PEFT configs, TRL configs and trainers, Transformers TrainingArguments and Trainer)."; return row; }
  var L = D.libs[lib], C = L.classes[cls], last = L.tags.length - 1, latest = L.tags[last], my = mine[lib];
  var mi = my ? idxOf(L, my) : null;
  var r = C.p[arg], al = aliasOf(C, arg);
  if (!r && !al) {
    var ext = Object.keys(C.ext || {})[0];
    if (ext && D.libs.transformers.classes[ext] && D.libs.transformers.classes[ext].p[arg]) {
      var sub = verdict(ext, arg, mine, cls);
      sub.text = sub.cls === "y" ? "Inherited from " + code(ext) + ". " + sub.text
        : code(arg) + " is not defined by " + code(cls) + " itself. It is a " + code(ext) + " argument that " + code(cls) + " inherits, so the installed Transformers version decides. " + sub.text;
      return sub;
    }
    row.cls = "n"; row.have = "none";
    row.text = "No " + NAME[lib] + " release from " + L.tags[0] + " to " + latest + " has an argument " + code(arg) + " on " + code(cls) + ".";
    var w = whoHas(arg, cls).slice(0, 3);
    if (w.length) row.text += " The name exists on " + w.map(function (x) { return code(x.cls) + " (" + NAME[x.lib] + " " + span(D.libs[x.lib], x.r) + ")"; }).join(", ") + ".";
    return row;
  }
  var acc = merge(r || [], al ? al.r : []);
  row.have = span(L, acc);
  var now = acc[acc.length - 1][1] === last, lastTag = L.tags[acc[acc.length - 1][1]], firstTag = L.tags[acc[0][0]];
  // a TRL config that once re-declared a TrainingArguments field still inherits it when its own declaration is gone
  var ext2 = Object.keys(C.ext || {})[0], TA = ext2 && D.libs.transformers.classes[ext2];
  if (TA && TA.p[arg] && (mi === null ? !now : (mi >= 0 && !inR(acc, mi)))) {
    var sub2 = verdict(ext2, arg, mine, cls);
    sub2.text = code(cls) + " declared " + code(arg) + " itself only in " + NAME[lib] + " " + row.have + "; in other releases it is the inherited " + code(ext2) + " argument, so the installed Transformers version decides. " + sub2.text;
    return sub2;
  }
  if (mi !== null && mi >= 0 && C.has && !inR(C.has, mi)) {
    row.cls = "n"; row.text = code(cls) + " does not exist in your " + NAME[lib] + " " + esc(my) + " (it exists in " + span(L, C.has) + ")."; return row;
  }
  var inMine = mi === null ? null : (mi >= 0 && inR(acc, mi));
  if (now) {
    row.cls = "y"; row.text = "Accepted by " + NAME[lib] + " " + latest + " (since " + firstTag + ").";
    if (inMine === false) { row.cls = "n"; row.need = firstTag; row.text = "Added in " + NAME[lib] + " " + firstTag + "; your " + esc(my) + " is older. " + pip(lib, firstTag) + ", or remove the argument."; }
  } else {
    row.cls = "n"; row.text = "Removed after " + NAME[lib] + " " + lastTag + ".";
    if (inMine === true) { row.cls = "y"; row.text = "Still accepted by your " + NAME[lib] + " " + esc(my) + "; removed after " + lastTag + "."; }
    else if (inMine === false && mi < acc[0][0]) { row.text = "Only in " + NAME[lib] + " " + row.have + "; your " + esc(my) + " is older."; }
  }
  if (al) {
    var alFrom = L.tags[al.r[0][0]], alTo = L.tags[al.r[al.r.length - 1][1]];
    row.text += " From " + alFrom + " to " + alTo + " it is only a deprecated alias" + (al.to ? " of " + code(al.to) : "") + ": accepted with a warning.";
    if (inMine === true && mi !== null && inR(al.r, mi)) row.text += " Your version is in that range.";
  }
  var h = D.hints[cls] && D.hints[cls][arg]; if (h) row.text += " " + h;
  return row;
}
function peftClass(pt) {
  if (D.ptype[pt]) return D.ptype[pt];
  return null;
}
function parse(txt) {
  var items = [], seen = {}, m, re, adapter = null, notes = [];
  function push(cls, arg) { var k = cls + "|" + arg; if (!seen[k] && /^[A-Za-z_][A-Za-z0-9_]*$/.test(arg)) { seen[k] = 1; items.push({ cls: cls, arg: arg }); } }
  // 1. TypeError with the class name (Python 3.10+)
  re = /([A-Za-z_][A-Za-z0-9_]*)\.__init__\(\) got an unexpected keyword argument '([^']+)'/g;
  while ((m = re.exec(txt))) push(m[1], m[2]);
  // 2. TypeError without the class name (Python 3.9 and older)
  re = /(^|[^.A-Za-z0-9_])__init__\(\) got an unexpected keyword argument '([^']+)'/g;
  while ((m = re.exec(txt))) push("?", m[2]);
  // 3. the PEFT warning of v0.14.0 and later
  re = /Unexpected keyword arguments \[([^\]]*)\] for class ([A-Za-z_0-9]+)/g;
  while ((m = re.exec(txt))) { var cl = m[2]; (m[1].match(/'([^']+)'/g) || []).forEach(function (s) { push(cl, s.slice(1, -1)); }); }
  // 4. adapter_config.json (or any JSON object with peft_type)
  var a = txt.indexOf("{"), b = txt.lastIndexOf("}");
  if (a >= 0 && b > a) {
    try {
      var o = JSON.parse(txt.slice(a, b + 1));
      if (o && typeof o === "object" && !Array.isArray(o) && (o.peft_type || o.lora_alpha !== undefined || o.target_modules !== undefined)) {
        var pt = String(o.peft_type || "LORA").toUpperCase(), pc = peftClass(pt);
        adapter = { type: pt, cls: pc, keys: Object.keys(o), saved: typeof o.peft_version === "string" ? o.peft_version : null };
      }
    } catch (e) { if (/"peft_type"/.test(txt)) notes.push("That looks like an adapter_config.json but it is not valid JSON; paste the whole file."); }
  }
  // 5. a Python call: SFTConfig(max_seq_length=512, ...)
  if (!adapter) {
    re = /\b([A-Z][A-Za-z0-9_]*(?:Config|Arguments|Trainer))\s*\(/g;
    while ((m = re.exec(txt))) {
      var depth = 1, i = re.lastIndex, start = i;
      for (; i < txt.length && depth > 0; i++) { var ch = txt.charAt(i); if (ch === "(") depth++; else if (ch === ")") depth--; }
      var bodyTxt = txt.slice(start, i - 1), top = "", d2 = 0;
      for (var j = 0; j < bodyTxt.length; j++) { var c2 = bodyTxt.charAt(j); if ("([{".indexOf(c2) >= 0) d2++; else if (")]}".indexOf(c2) >= 0) d2--; top += d2 === 0 ? c2 : " "; }
      var kre = /(^|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)/g, k;
      while ((k = kre.exec(top))) push(m[1], k[2]);
    }
  }
  return { items: items, adapter: adapter, notes: notes };
}
function run(push) {
  var txt = $("q").value, out = $("res"), st = $("status");
  var mine = { peft: $("vp").value.trim(), transformers: $("vt").value.trim(), trl: $("vr").value.trim() };
  out.innerHTML = ""; st.textContent = "";
  if (!txt.trim()) { st.textContent = "Paste a TypeError line, an adapter_config.json, or a call such as SFTConfig(max_seq_length=512)."; return; }
  var p = parse(txt), rows = [], head = "";
  if (p.adapter) {
    var A = p.adapter, L = D.libs.peft;
    if (!A.cls) { st.textContent = "peft_type " + A.type + " is not a config class this page tracks."; return; }
    var need = -1, needKey = null, unknown = [], C = L.classes[A.cls];
    A.keys.forEach(function (k) {
      var r = C.p[k];
      if (!r) { unknown.push(k); return; }
      if (r[r.length - 1][1] !== L.tags.length - 1) { rows.push(verdict(A.cls, k, mine)); return; }
      if (r[0][0] > need) { need = r[0][0]; needKey = k; }
    });
    var mi = mine.peft ? idxOf(L, mine.peft) : null, FC = L.tags.indexOf(D.forward);
    var newer = mi === null ? [] : A.keys.filter(function (k) { var r = C.p[k]; return r && !inR(r, mi) && r[0][0] > mi; });
    head = '<div class="verdict ' + (mi !== null && newer.length ? "v-bad" : mi !== null ? "v-ok" : "v-load") + '">This ' + esc(A.cls) + " file uses keys up to PEFT " + L.tags[need] + " (" + esc(needKey) + ")" +
      "<span>" + (A.saved ? "It says it was saved with PEFT " + esc(A.saved) + " (the " + code("peft_version") + " key, written from v0.18.0). " : "") +
      "Every key in it exists from " + L.tags[need] + " on, so that is the oldest PEFT that reads it without dropping anything: " + pip("peft", L.tags[need]) + ".";
    if (mi !== null && newer.length) {
      head += " Your PEFT " + esc(mine.peft) + " does not know " + newer.map(code).join(", ") + ". " +
        (mi < FC ? "Before " + D.forward + " that is a <code>TypeError: " + esc(A.cls) + ".__init__() got an unexpected keyword argument</code>."
                 : "From " + D.forward + " PEFT does not stop: it warns \"Unexpected keyword arguments ... these are ignored\" and loads the adapter without those settings, which changes the result unless each one is at its default.");
    } else if (mi !== null) head += " Your PEFT " + esc(mine.peft) + " knows every key.";
    head += "</span></div>";
    newer.forEach(function (k) { var rr = verdict(A.cls, k, mine); rr.text = rr.text.replace(", or remove the argument.", ". Deleting the key instead is safe only if it holds its default value."); rows.push(rr); });
    unknown.forEach(function (k) { rows.push({ name: k, on: A.cls, lib: "peft", cls: "", have: "none", text: "Not a " + code(A.cls) + " key in any PEFT release up to " + L.tags[L.tags.length - 1] + ". PEFT " + D.forward + " and later ignore it with a warning; older releases raise TypeError." }); });
    if (!rows.length && mi === null) {
      var newest = A.keys.filter(function (k) { return C.p[k]; }).sort(function (x, y) { return C.p[y][0][0] - C.p[x][0][0]; }).slice(0, 6);
      newest.forEach(function (k) { var r = verdict(A.cls, k, mine); r.cls = ""; r.text = "In PEFT since " + L.tags[C.p[k][0][0]] + "."; rows.push(r); });
    }
  }
  p.items.forEach(function (it) {
    if (it.cls === "?") {
      var w = whoHas(it.arg, null);
      if (!w.length) { rows.push({ name: it.arg, on: "?", lib: null, cls: "n", have: "none", text: "No tracked class in PEFT, TRL or Transformers has ever had an argument " + code(it.arg) + ". The line does not name the class (Python 3.9 and older); the frame above it in the traceback does." }); return; }
      w.slice(0, 3).forEach(function (x) { var r = verdict(x.cls, it.arg, mine); r.text = "The error line does not name the class; " + code(x.cls) + " is one that has had this argument. " + r.text; rows.push(r); });
      return;
    }
    rows.push(verdict(it.cls, it.arg, mine));
  });
  if (!rows.length && !head) { st.textContent = p.notes[0] || "Found no \"unexpected keyword argument\" line, adapter_config.json or Config(...)/Trainer(...) call in that text."; return; }
  if (!head) {
    var bad = rows.filter(function (r) { return r.cls === "n"; }).length, anyV = mine.peft || mine.transformers || mine.trl;
    head = bad ? '<div class="verdict v-bad">' + bad + " of " + rows.length + " arguments will not work" + (anyV ? " with the versions you entered" : " in the newest releases") + "<span>Releases and replacements below.</span></div>"
               : '<div class="verdict v-ok">All ' + rows.length + " arguments are accepted" + (anyV ? " by the versions you entered" : " by the newest releases") + "</div>";
  }
  out.innerHTML = head + (rows.length ? '<div class="tw"><table><thead><tr><th>Argument</th><th>Class</th><th>Releases that accept it</th><th>Verdict</th></tr></thead><tbody>' + rows.map(function (r) {
    return "<tr><td>" + code(r.name) + "</td><td>" + esc(r.on || "?") + (r.lib ? '<br><span class="note">' + NAME[r.lib] + "</span>" : "") + "</td><td>" + esc(r.have || "none") + "</td><td>" + (r.cls ? '<span class="s ' + r.cls + '">' + (r.cls === "y" ? "ok" : "problem") + "</span> " : "") + r.text + "</td></tr>";
  }).join("") + "</tbody></table></div>" : "");
  if (push) { try { var u = new URLSearchParams(); if (txt.length < 700) u.set("q", txt); if (mine.peft) u.set("peft", mine.peft); if (mine.transformers) u.set("transformers", mine.transformers); if (mine.trl) u.set("trl", mine.trl); history.replaceState(null, "", location.pathname + "?" + u.toString() + "#lookup"); } catch (e) {} }
}
window.ptRun = run; window.ptParse = parse; window.ptVerdict = verdict;
$("go").addEventListener("click", function () { run(true); });
var fi = $("filter");
if (fi) fi.addEventListener("input", function () { var v = fi.value.trim().toLowerCase(); document.querySelectorAll("table.full tbody tr").forEach(function (r) { r.style.display = !v || r.textContent.toLowerCase().indexOf(v) >= 0 ? "" : "none"; }); });
try { var sp = new URLSearchParams(location.search); if (sp.get("q")) { $("q").value = sp.get("q"); if (sp.get("peft")) $("vp").value = sp.get("peft"); if (sp.get("transformers")) $("vt").value = sp.get("transformers"); if (sp.get("trl")) $("vr").value = sp.get("trl"); run(false); } } catch (e) {}
})();
