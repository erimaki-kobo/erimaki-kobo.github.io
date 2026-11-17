(function () {
  var D = JSON.parse(document.getElementById("la-data").textContent);
  var L = D.latest[0], FIRST = D.first[0];
  var BIN = { srv: "llama-server", cli: "llama-cli", cmp: "llama-completion" };
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function code(s) { return "<code>" + esc(s) + "</code>"; }
  function bd(b) { return "b" + b + (D.dates[b] ? " (" + D.dates[b] + ")" : ""); }
  /* logic-begin */
  function rng(f, k) { var r = f[k]; return r === 1 ? f.any : r; }
  function inR(r, b) { for (var i = 0; i < r.length; i++) { if (b >= r[i][0] && (r[i][1] === null || b < r[i][1])) return true; } return false; }
  function norm(t) { t = t.replace(/=.*$/, ""); return t.slice(0, 2) === "--" ? t.replace(/_/g, "-") : t; }
  function detectBin(text) {
    if (/llama-completion/.test(text)) return "cmp";
    if (/llama-cli|(^|[\s\/\\])main(\.exe)?\s+-/.test(text)) return "cli";
    if (/llama-server|(^|[\s\/\\])server(\.exe)?\s+-/.test(text)) return "srv";
    return null;
  }
  function tokens(text) {
    var out = [], seen = {}, m;
    function add(kind, name) { var k = kind + name; if (!seen[k]) { seen[k] = 1; out.push({ kind: kind, name: name }); } }
    var re = /(?:invalid argument|unknown argument):\s*(-[^\s"']+)|error while handling argument "(-[^"]+)"|error while handling environment variable "([^"]+)"/g;
    while ((m = re.exec(text))) { if (m[3]) add("env", m[3]); else add("flag", norm(m[1] || m[2])); }
    re = /\bLLAMA_[A-Z0-9_]+\b/g;
    while ((m = re.exec(text))) add("env", m[0]);
    var parts = text.split(/[\s]+/);
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i].replace(/^["'`(\[]+|["'`,;:)\]]+$/g, "");
      if (/^--?[A-Za-z][\w-]*(=.*)?$/.test(p)) add("flag", norm(p));
    }
    return out;
  }
  function near(name, k) {
    function dist(a, b) {
      var p = [], i, j; for (j = 0; j <= b.length; j++) p[j] = j;
      for (i = 1; i <= a.length; i++) { var q = [i]; for (j = 1; j <= b.length; j++) q[j] = Math.min(p[j] + 1, q[j - 1] + 1, p[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); p = q; }
      return p[b.length];
    }
    var bare = name.replace(/^-+/, ""), c = [];
    for (var n in D.flags) {
      if (!inR(rng(D.flags[n], k), L)) continue;
      var d = n.replace(/^-+/, "") === bare ? 0 : dist(name, n);
      if (d <= (name.length > 8 ? 2 : 1)) c.push([d, n]);
    }
    c.sort(function (a, b) { return a[0] - b[0] || (a[1] < b[1] ? -1 : 1); });
    return c.slice(0, 3).map(function (x) { return x[1]; });
  }
  function judgeFlag(name, k, mine) {
    var f = D.flags[name], r = { name: name, level: "ok", head: "", body: "" };
    if (!f) {
      if (D.old[name]) {
        r.level = "bad"; r.head = "removed before " + bd(FIRST);
        r.body = "Last seen in " + bd(D.old[name][0]) + ", gone by " + bd(D.old[name][1]) + ". Builds of that time said " + code("error: unknown argument: " + name) + ".";
        return r;
      }
      var s = near(name, k);
      r.level = "bad"; r.head = "not an option in any build read";
      r.body = "No build from b" + D.old_snapshots[0] + " to b" + L + " has this name." + (s.length ? " Closest names " + BIN[k] + " takes now: " + s.map(code).join(", ") + "." : "");
      return r;
    }
    var rr = rng(f, k), now = inR(rr, L), anyNow = inR(f.any, L);
    var mineTxt = "";
    if (mine) mineTxt = " Your b" + mine + ": " + (mine < FIRST ? "older than the option table (b" + FIRST + "); not covered." : inR(rr, mine) ? "accepted." : inR(f.any, mine) ? "the option exists, but not for " + BIN[k] + "." : "not accepted.");
    if (f.stub) {
      r.level = "bad"; r.head = "removed; a stub answers since " + bd(f.stub[0]);
      r.body = "The name is still registered so that it can stop with " + code('error while handling argument "' + name + '": the argument has been removed. ' + f.stub[1]) + "." + mineTxt;
      return r;
    }
    if (now) {
      var a = rr[rr.length - 1][0];
      r.head = "accepted by " + BIN[k] + " in b" + L;
      r.body = (a <= FIRST ? "Present since the option table was created (" + bd(FIRST) + ")." : "Since " + bd(a) + ".") +
        (f.al && f.al.length ? " Same option: " + f.al.map(code).join(", ") + "." : "") +
        (f.dep ? ' <span class="s p">deprecated</span> ' + esc(f.hint || "") : "") + mineTxt;
      if (f.dep) r.level = "warn";
      return r;
    }
    if (anyNow) {
      var who = ["srv", "cli", "cmp"].filter(function (x) { return inR(rng(f, x), L); }).map(function (x) { return BIN[x]; });
      r.level = "bad"; r.head = "exists in b" + L + ", but not for " + BIN[k];
      var last = rr.length ? rr[rr.length - 1] : null;
      r.body = (last ? BIN[k] + " took it from " + bd(last[0]) + " and stopped in " + bd(last[1]) + ". " : BIN[k] + " never took it. ") +
        (who.length ? "Accepted now by: " + who.map(code).join(", ") + "." : "Registered now only for other tools" + (f.ex ? " (" + esc(f.ex.join(", ").toLowerCase()) + ")" : "") + ".") + mineTxt;
      return r;
    }
    r.level = "bad"; r.head = "removed in " + bd(f.rm[0]);
    r.body = (rr.length ? BIN[k] + " took it from " + bd(rr[0][0]) + ". " : BIN[k] + " never took it; other tools did from " + bd(f.any[0][0]) + ". ") +
      'Removed by <a href="https://github.com/ggml-org/llama.cpp/commit/' + esc(f.rm[1]) + '">' + esc(f.rm[2]) + "</a>." +
      (f.hint ? " Its last warning or help text: " + code(f.hint) : "") + mineTxt;
    return r;
  }
  function judgeEnv(name, mine) {
    var e = D.envs[name], r = { name: name, level: "ok", head: "", body: "" };
    if (!e) {
      r.level = "warn"; r.head = "not read by any build since b" + FIRST;
      r.body = "No option has registered this variable since " + bd(FIRST) + ". Setting it is not an error; it does nothing.";
      return r;
    }
    var now = inR(e.r, L), mineTxt = mine ? " Your b" + mine + ": " + (inR(e.r, mine) ? "read." : "not read.") : "";
    if (e.stub) {
      r.level = "bad"; r.head = "stops startup since " + bd(e.stub[0]);
      r.body = "The variable still belongs to a removed option, so setting it ends with " + code('error while handling environment variable "' + name + '": the argument has been removed. ' + e.stub[1]) + "." + mineTxt;
      return r;
    }
    if (now) {
      r.head = "read in b" + L; r.body = "Sets " + code(e.opt) + (e.derived ? " to off (any value; kept for compatibility with the older LLAMA_ARG_NO_ names)" : "") + ". Since " + bd(e.r[e.r.length - 1][0]) + "." + mineTxt;
      return r;
    }
    r.level = "warn"; r.head = "ignored since " + bd(e.rm[0]);
    r.body = "No error and no warning: llama.cpp only reads the variables of options it still has. It belonged to " + code(e.opt) +
      ' until <a href="https://github.com/ggml-org/llama.cpp/commit/' + esc(e.rm[1]) + '">' + esc(e.rm[2]) + "</a>." + mineTxt;
    return r;
  }
  /* logic-end */
  var OLL = null;
  function ollamaBuild(v, cb) {
    function find() { for (var i = 0; i < OLL.length; i++) { if (OLL[i].release === "v" + v) return OLL[i]; } return null; }
    if (OLL) return cb(find());
    fetch("/en/gguf-arch-min-build-lookup/archs.json").then(function (r) { return r.json(); }).then(function (j) { OLL = j.ollama_releases || []; cb(find()); })
      .catch(function () { OLL = []; cb(null); });
  }
  function render(text, k, auto, mine, mineNote) {
    var toks = tokens(text);
    if (!toks.length) { $("status").textContent = "Found no option (-x, --name) or LLAMA_ variable in that text."; $("res").innerHTML = ""; return; }
    $("status").textContent = "";
    var rows = [], stop = 0, warn = 0;
    toks.forEach(function (t) {
      var r = t.kind === "env" ? judgeEnv(t.name, mine) : judgeFlag(t.name, k, mine);
      if (r.level === "bad") stop++; else if (r.level === "warn") warn++;
      rows.push("<tr><td>" + code(r.name) + '</td><td><span class="s ' + { ok: "y", bad: "n", warn: "p" }[r.level] + '">' + esc(r.head) + "</span></td><td>" + r.body + "</td></tr>");
    });
    var head = stop ? '<div class="verdict v-bad">' + stop + " of " + toks.length + " names will stop " + BIN[k] + " b" + L + "<span>Each stops with " + code("error: invalid argument: NAME") + ", or with the stub's own message.</span></div>"
      : warn ? '<div class="verdict v-load">Nothing here stops ' + BIN[k] + " b" + L + ", but " + warn + " of " + toks.length + " names are ignored or deprecated</div>"
        : '<div class="verdict v-ok">All ' + toks.length + " names are valid for " + BIN[k] + " b" + L + "</div>";
    var notes = [];
    if (auto) notes.push("No binary name found in the text, so this is for " + code("llama-server") + ". Choose another above if needed.");
    if (mineNote) notes.push(mineNote);
    $("res").innerHTML = head + '<div class="tw"><table><thead><tr><th>Name</th><th>In b' + L + " for " + BIN[k] + "</th><th>Details</th></tr></thead><tbody>" + rows.join("") + "</tbody></table></div>" +
      (notes.length ? '<p class="note">' + notes.join(" ") + "</p>" : "");
  }
  function run() {
    var text = $("q").value, sel = $("bin").value, v = $("v").value.trim();
    var det = detectBin(text), k = sel === "auto" ? (det || "srv") : sel, auto = sel === "auto" && !det;
    try {
      var q = "?q=" + encodeURIComponent(text.slice(0, 1500)) + (sel !== "auto" ? "&bin=" + sel : "") + (v ? "&v=" + encodeURIComponent(v) : "");
      history.replaceState(null, "", location.pathname + q + "#lookup");
    } catch (err) {}
    var m;
    if (!v) return render(text, k, auto, null, null);
    if ((m = v.match(/^b?(\d{3,5})$/i))) return render(text, k, auto, parseInt(m[1], 10), null);
    if ((m = v.match(/^(?:ollama\s*)?v?(\d+\.\d+\.\d+)$/i))) {
      return ollamaBuild(m[1], function (rel) {
        if (rel && rel.llama_cpp_build) render(text, k, auto, parseInt(rel.llama_cpp_build.slice(1), 10), "Ollama " + esc(rel.release) + " bundles llama.cpp " + esc(rel.llama_cpp_build) + ".");
        else render(text, k, auto, null, "Could not find Ollama v" + esc(m[1]) + " in the release table; showing the newest build only.");
      });
    }
    render(text, k, auto, null, "Could not read the version. Use a build number like b10091, or an Ollama release like 0.32.5.");
  }
  $("go").addEventListener("click", run);
  try {
    var sp = new URLSearchParams(location.search);
    if (sp.get("bin") && BIN[sp.get("bin")]) $("bin").value = sp.get("bin");
    if (sp.get("v")) $("v").value = sp.get("v");
    if (sp.get("q")) { $("q").value = sp.get("q"); run(); }
  } catch (err) {}
  var filt = $("filter");
  if (filt) filt.addEventListener("input", function () {
    var w = filt.value.trim().toLowerCase();
    Array.prototype.forEach.call(document.querySelectorAll("table.flt tbody tr"), function (tr) {
      tr.style.display = !w || tr.textContent.toLowerCase().indexOf(w) >= 0 ? "" : "none";
    });
  });
})();
