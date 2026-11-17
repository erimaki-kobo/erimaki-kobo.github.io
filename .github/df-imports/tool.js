(function () {
  "use strict";
  var SEQ = 0, D = null, CH = {}, W = null, HINTS = window.DF_HINTS, GROUPS = window.DF_GROUPS;
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  var STOP = {from: 1, "import": 1, diffusers: 1, ImportError: 1, cannot: 1, name: 1, as: 1, unknown: 1, location: 1, py: 1,
    __init__: 1, site: 1, packages: 1, lib: 1, python: 1, usr: 1, local: 1, dist: 1, module: 1, has: 1, no: 1, attribute: 1,
    ModuleNotFoundError: 1, AttributeError: 1, RuntimeError: 1, No: 1, named: 1, Failed: 1, to: 1, because: 1, of: 1, the: 1,
    following: 1, error: 1, look: 1, up: 1, see: 1, its: 1, traceback: 1, most: 1, likely: 1, due: 1, circular: 1, partially: 1,
    initialized: 1, Did: 1, you: 1, mean: 1, File: 1, line: 1, "in": 1};
  var Q = "['\"`\u2018\u2019]?";

  function modOf(dotted) { return dotted === "diffusers" ? "" : dotted.replace(/^diffusers\./, ""); }
  function label(m) { return m ? "diffusers." + m : "diffusers"; }

  function parse(text) {
    var out = [], seen = {}, m;
    function add(name, mod) {
      var k = mod + ":" + name;
      if (!seen[k] && (name === null || /^[A-Za-z_]\w*$/.test(name))) { seen[k] = 1; out.push({name: name, mod: mod}); }
    }
    var rest = text;
    var reErr = new RegExp("cannot import name " + Q + "([A-Za-z_]\\w*)" + Q + "\\s+from\\s+(?:partially initialized module\\s+)?" + Q + "(diffusers(?:\\.\\w+)*)", "g");
    while ((m = reErr.exec(text))) add(m[1], modOf(m[2]));
    rest = rest.replace(reErr, " ").replace(/\([^()]*(?:site-packages|dist-packages|__init__\.py)[^()]*\)/g, " ");
    var reAttr = new RegExp("module " + Q + "(diffusers(?:\\.\\w+)*)" + Q + " has no attribute " + Q + "([A-Za-z_]\\w*)", "g");
    while ((m = reAttr.exec(rest))) add(m[2], modOf(m[1]));
    rest = rest.replace(reAttr, " ");
    var reNoMod = new RegExp("(?:No module named|Failed to import)\\s+" + Q + "(diffusers(?:\\.\\w+)+)", "g");
    while ((m = reNoMod.exec(rest))) add(null, modOf(m[1]));
    rest = rest.replace(reNoMod, " ");
    var reImp = /from\s+(diffusers(?:\.\w+)*)\s+import\s+(\([^)]*\)|[^\n;]+)/g;
    while ((m = reImp.exec(rest))) {
      var mod = modOf(m[1]);
      m[2].replace(/#[^\n]*/g, " ").replace(/[()\\]/g, " ").split(",").forEach(function (p) {
        var n = p.trim().split(/\s+as\s+/)[0].trim();
        if (n) add(n, mod);
      });
    }
    rest = rest.replace(reImp, " ");
    var rePlain = /(?:^|\n|;)\s*import\s+(diffusers(?:\.\w+)+)/g;
    while ((m = rePlain.exec(rest))) add(null, modOf(m[1]));
    rest = rest.replace(rePlain, " ");
    if (!out.length) {
      var dotted = rest.match(/diffusers(?:\.\w+)+/g) || [];
      dotted.forEach(function (d) { add(null, modOf(d)); });
      if (!dotted.length) (rest.match(/[A-Za-z_]\w{2,}/g) || []).forEach(function (w) { if (!STOP[w]) add(w, "?"); });
    }
    return out.slice(0, 30);
  }

  function rel(i) { return D.releases[i]; }
  function vkey(v) { return v.split(".").map(function (x) { return parseInt(x, 10) || 0; }); }
  function cmp(a, b) { for (var i = 0; i < 3; i++) { if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) - (b[i] || 0); } return 0; }
  function indexOfVersion(v) {
    var k = vkey(v), idx = -1;
    for (var i = 0; i < D.releases.length; i++) if (cmp(vkey(rel(i)[0]), k) <= 0) idx = i;
    return idx;
  }
  function pairsOf(ri) {
    var r = D.ranges[ri], out = [];
    for (var i = 0; i < r.length; i += 2) out.push([r[i], r[i + 1]]);
    return out;
  }
  function chunkOf(m) {
    var head = m.split(".")[0];
    return head === "pipelines" ? "pipelines" : head === "modular_pipelines" ? "modular" : "core";
  }
  function namesOf(m) { return m === "" ? D.top : (CH[chunkOf(m)] || {})[m] || null; }
  function modEver(m) { return m === "" || Object.prototype.hasOwnProperty.call(D.mods, m); }
  function modPairs(m) { return m === "" ? [[0, 0]] : pairsOf(D.mods[m]); }
  function inRange(ps, i) { return ps.some(function (p) { return p[0] <= i && (p[1] === 0 || i < p[1]); }); }
  function lastBefore(i) { return rel(i - 1)[2]; }
  function rangeText(p) {
    var a = rel(p[0]);
    if (p[1] === 0) return "from <strong>" + a[0] + "</strong> (" + a[1] + ") and still in " + D.latest;
    var b = rel(p[1]);
    return "<strong>" + a[0] + "</strong> (" + a[1] + ") through <strong>" + lastBefore(p[1]) + "</strong>; gone in " + b[0] + " (" + b[1] + ")";
  }
  function staleFor(m, name) {
    return D.stale.filter(function (s) { return s[0] === m && s[1] === name; });
  }
  function hintFor(m, name, p) {
    var h = HINTS[m + ":" + name];
    if (h) return h;
    if (p && p[1]) {
      var goneIn = rel(p[1])[0];
      for (var i = 0; i < GROUPS.length; i++) {
        var g = GROUPS[i];
        if (g[0] === goneIn && new RegExp(g[1]).test(name)) return g[2];
      }
    }
    return "";
  }
  function dist(a, b) {
    var prev = [], i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      var cur = [i];
      for (j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      prev = cur;
    }
    return prev[b.length];
  }
  function near(name, keys) {
    var low = name.toLowerCase(), exact = [], sub = [];
    keys.forEach(function (k) {
      var kl = k.toLowerCase();
      if (k === name) return;
      if (kl === low) exact.push(k);
      else if (low.length >= 6 && (kl.indexOf(low) >= 0 || low.indexOf(kl) >= 0 && kl.length >= 8)) sub.push(k);
      else if (low.length >= 6 && Math.abs(kl.length - low.length) <= 2 && dist(kl, low) <= 2) exact.push(k);
    });
    sub.sort(function (a, b) { return Math.abs(a.length - name.length) - Math.abs(b.length - name.length); });
    return exact.concat(sub).slice(0, 6);
  }
  function code(s) { return "<code>" + esc(s) + "</code>"; }

  // where a name can be imported from in the newest release, apart from module `except`
  function whereNow(name, except) {
    var out = [];
    if (except !== "" && D.top[name]) {
      var tp = pairsOf(D.top[name]), tl = tp[tp.length - 1];
      if (tl[1] === 0) out.push(code("from diffusers import " + name) + " (top level, since " + rel(tl[0])[0] + ")");
    }
    var w = W && W.names[name];
    if (w) {
      if (w[0] < 0) out.push("defined in " + (-w[0]) + " modules of " + W.release);
      else {
        var ms = w.map(function (i) { return W.modules[i]; }).filter(function (m) { return m !== except; });
        if (ms.length) out.push("defined in " + ms.map(function (m) { return code(label(m)); }).join(", ") + " in " + W.release);
      }
    }
    return out;
  }
  function movedModule(m) {
    var leaf = m.split(".").pop(), last = D.releases.length - 1, out = [];
    Object.keys(D.mods).forEach(function (k) {
      if (k !== m && k.split(".").pop() === leaf && inRange(pairsOf(D.mods[k]), last)) out.push(k);
    });
    return out.slice(0, 5);
  }
  function mineText(has, what) {
    return "<br><strong>Your " + esc($("v").value.trim()) + ": " + (has ? "has it" : "does not have it") + ".</strong>" +
      (has ? " If the error still names " + what + ", another copy of diffusers is being imported: check <code>python -c \"import diffusers as d; print(d.__version__, d.__file__)\"</code>." : "");
  }
  function row(nameHtml, modLabel, status, cell) {
    return "<tr><td>" + nameHtml + "<br><span class=\"note\">" + esc(modLabel) + "</span></td><td>" + status + "</td><td>" + cell + "</td></tr>";
  }

  function answerModule(m, mine) {
    var cell, status;
    if (!modEver(m)) {
      var mv = movedModule(m);
      status = "<span class=\"s n\">never there</span>";
      cell = "No release from " + rel(0)[0] + " to " + D.latest + " has a module " + code(label(m)) + "." +
        (mv.length ? " Modules with the same last part in " + D.latest + ": " + mv.map(function (k) { return code(label(k)); }).join(", ") + "." : "");
      return row(code(label(m)), "module", status, cell);
    }
    var ps = modPairs(m), last = ps[ps.length - 1], now = last[1] === 0;
    status = now ? "<span class=\"s y\">in " + D.latest + "</span>" : "<span class=\"s n\">gone</span>";
    cell = "The module exists " + ps.map(rangeText).join("<br>") + ".";
    if (!now) {
      var mv2 = movedModule(m);
      cell += "<br><span class=\"pin\">Keep it: <code>pip install \"diffusers" + (last[0] > 0 ? "&gt;=" + rel(last[0])[0] + "," : "") + "&lt;" + rel(last[1])[0] + "\"</code></span>" +
        (mv2.length ? "<br>Now: " + mv2.map(function (k) { return code(label(k)); }).join(", ") + " (same file name, in " + D.latest + ")." : "");
    } else if (last[0] > 0) {
      cell += "<br><span class=\"pin\">Needs: <code>pip install \"diffusers&gt;=" + rel(last[0])[0] + "\"</code></span>";
    }
    if (mine !== null) cell += mineText(inRange(ps, mine), "the module");
    return row(code(label(m)), "module", status, cell);
  }

  function answerName(m, name, mine) {
    if (!modEver(m)) {
      var wn0 = whereNow(name, null);
      return row(code(name), label(m), "<span class=\"s n\">no such module</span>",
        "No release from " + rel(0)[0] + " to " + D.latest + " has a module " + code(label(m)) + "." +
        (wn0.length ? " " + code(name) + ": " + wn0.join("; ") + "." : ""));
    }
    var table = namesOf(m) || {}, ri = table[name], cell, status;
    var st = staleFor(m, name);
    if (ri === undefined) {
      var nn = near(name, Object.keys(table)), wn = whereNow(name, m), mp = modPairs(m), mlast = mp[mp.length - 1];
      status = "<span class=\"s n\">never there</span>";
      cell = "No release from " + rel(0)[0] + " to " + D.latest + " lets you import this name from " + code(label(m)) + "." +
        (mlast[1] ? " The module itself is gone since " + rel(mlast[1])[0] + "." : "") +
        (wn.length ? "<br>Now: " + wn.join("; ") + "." : "") +
        (nn.length ? "<br>Close names in this module: " + nn.map(code).join(", ") + "." : "") +
        (!wn.length && !nn.length ? " It may come from a fork, from the development branch, or from a release newer than " + D.latest + "." : "");
    } else {
      var ps = pairsOf(ri), last = ps[ps.length - 1], now = last[1] === 0;
      status = now ? "<span class=\"s y\">in " + D.latest + "</span>" : "<span class=\"s n\">gone</span>";
      cell = ps.map(rangeText).join("<br>");
      if (!now) {
        var hint = hintFor(m, name, last), wn2 = whereNow(name, m);
        cell += "<br><span class=\"pin\">Keep it: <code>pip install \"diffusers" + (last[0] > 0 ? "&gt;=" + rel(last[0])[0] + "," : "") + "&lt;" + rel(last[1])[0] + "\"</code></span>" +
          (wn2.length ? "<br>Now: " + wn2.join("; ") + "." : "") + (hint ? "<br>Instead: " + hint : "");
      } else if (last[0] > 0) {
        cell += "<br><span class=\"pin\">Needs: <code>pip install \"diffusers&gt;=" + rel(last[0])[0] + "\"</code></span>";
      }
      if (mine !== null) cell += mineText(inRange(ps, mine), "it");
    }
    st.forEach(function (s) {
      cell += "<br><span class=\"note\">From " + rel(s[4])[0] + (s[5] ? " through " + lastBefore(s[5]) : " on") + " the module's lazy table still lists this name, but the entry points to " +
        code(s[2]) + ", " + (s[3] === "nofile" ? "a file that is not there" : "which does not provide it") +
        ": the import fails (ImportError, or \"RuntimeError: Failed to import ...\")." +
        (m === "" ? " Without the optional backend installed, the same import hands back a placeholder instead." : "") + "</span>";
    });
    return row(code(name), label(m), status, cell);
  }

  function answerBare(name, mine) {
    if (D.top[name]) return answerName("", name, mine);
    var hits = [];
    ["core", "pipelines", "modular"].forEach(function (c) {
      var t = CH[c] || {};
      Object.keys(t).forEach(function (m) { if (t[m][name] !== undefined) hits.push(m); });
    });
    var w = W && W.names[name], defs = {};
    if (w && w[0] >= 0) w.forEach(function (i) { defs[W.modules[i]] = 1; });
    hits.sort(function (a, b) { return (defs[b] || 0) - (defs[a] || 0) || a.split(".").length - b.split(".").length || (a < b ? -1 : 1); });
    if (!hits.length) {
      var nn = near(name, Object.keys(D.top));
      return row(code(name), "any module", "<span class=\"s n\">never there</span>",
        "No release from " + rel(0)[0] + " to " + D.latest + " has this name at the top level or in any module of diffusers." +
        (nn.length ? " Close top-level names: " + nn.map(code).join(", ") + "." : "") +
        " It may come from a fork, from the development branch, or from a release newer than " + D.latest + ".");
    }
    var head = row(code(name), "diffusers", "<span class=\"s n\">not top-level</span>",
      "Never importable as " + code("from diffusers import " + name) + ". It is in " + hits.length + " module" + (hits.length > 1 ? "s" : "") +
      (hits.length > 6 ? "; the first 6 follow (the modules that define it come first)." : ":"));
    return head + hits.slice(0, 6).map(function (m) { return answerName(m, name, mine); }).join("");
  }

  function load(file) {
    return fetch(file).then(function (r) { if (!r.ok) throw new Error(file + " " + r.status); return r.json(); });
  }
  function need(qs) {
    var want = {}, jobs = [];
    qs.forEach(function (q) {
      if (q.mod === "?") { if (!D.top[q.name]) { want.core = want.pipelines = want.modular = 1; } }
      else if (q.mod !== "" && q.name !== null) want[chunkOf(q.mod)] = 1;
    });
    Object.keys(want).forEach(function (c) {
      if (!CH[c]) jobs.push(load(D.files[c]).then(function (d) { CH[c] = d; }));
    });
    if (!W) jobs.push(load(D.files.where).then(function (d) { W = d; }));
    return Promise.all(jobs);
  }

  function done() { $("res").setAttribute("data-done", String(++SEQ)); }
  function run() {
    var qs = parse($("q").value), v = $("v").value.trim(), mine = null;
    $("status").textContent = "";
    if (!D) { $("status").textContent = "The data is still loading."; return; }
    if (v) {
      if (!/^v?\d+\.\d+(\.\d+)?/.test(v)) { $("status").textContent = "Version should look like 0.31.0."; done(); return; }
      mine = indexOfVersion(v.replace(/^v/, ""));
      if (mine < 0) { $("status").textContent = "Releases before " + rel(0)[0] + " are not covered."; done(); return; }
    }
    if (!qs.length) { $("res").innerHTML = "<p class=\"note\">Found no name. Paste the ImportError line, the import statement, or just the name.</p>"; done(); return; }
    $("status").textContent = "Loading the names...";
    need(qs).then(function () {
      $("status").textContent = "";
      $("res").innerHTML = "<div class=\"tw\"><table><thead><tr><th>Name</th><th>Now</th><th>Releases that have it</th></tr></thead><tbody>" +
        qs.map(function (q) {
          return q.name === null ? answerModule(q.mod, mine) : q.mod === "?" ? answerBare(q.name, mine) : answerName(q.mod, q.name, mine);
        }).join("") + "</tbody></table></div>" +
        "<p class=\"note\">Read at the first release of every minor version (" + D.releases.length + " releases, " + rel(0)[0] + " to " + D.latest +
        "); patch releases in between are assumed to keep the names. \"Has it\" means the import statement succeeds with the optional backends installed.</p>";
      done();
    }).catch(function (e) { $("status").textContent = "Could not load the names (" + e.message + "). The tables below still apply."; done(); });
  }

  $("go").addEventListener("click", run);
  $("q").addEventListener("keydown", function (e) { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run(); });
  Array.prototype.forEach.call(document.querySelectorAll("[data-ex]"), function (b) {
    b.addEventListener("click", function () { $("q").value = b.getAttribute("data-ex"); $("v").value = b.getAttribute("data-v") || ""; run(); });
  });
  load("data.json").then(function (d) {
    D = d; window.DF_DATA = d;
    var q = new URLSearchParams(location.search).get("q");
    if (q) { $("q").value = q; $("v").value = new URLSearchParams(location.search).get("v") || ""; run(); }
  }).catch(function (e) { $("status").textContent = "Could not load data.json (" + e.message + "). The tables below still apply."; });
})();
