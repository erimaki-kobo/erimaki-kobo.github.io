(function () {
  "use strict";
  var LIBS = window.LOOKUP_LIBS || ["peft", "trl", "accelerate"], DATA = {}, SEQ = 0, HINTS = window.PTA_HINTS;
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  function code(s) { return "<code>" + esc(s) + "</code>"; }
  var STOP = {from: 1, "import": 1, ImportError: 1, cannot: 1, name: 1, as: 1, unknown: 1, location: 1, py: 1, __init__: 1,
    site: 1, packages: 1, lib: 1, python: 1, usr: 1, local: 1, dist: 1, module: 1, has: 1, no: 1, attribute: 1,
    ModuleNotFoundError: 1, AttributeError: 1, RuntimeError: 1, No: 1, named: 1, Failed: 1, to: 1, because: 1, of: 1, the: 1,
    following: 1, error: 1, look: 1, up: 1, see: 1, its: 1, traceback: 1, most: 1, likely: 1, due: 1, circular: 1, partially: 1,
    initialized: 1, Did: 1, you: 1, mean: 1, File: 1, line: 1, "in": 1, transformers: 1};
  LIBS.forEach(function (l) { STOP[l] = 1; });
  var Q = "['\"`\u2018\u2019]?", LIBRX = "(" + LIBS.slice().sort(function (a, b) { return b.length - a.length; }).join("|") + ")(?!\\w)", ALL = LIBS.join(", ");

  function split(dotted) {
    var i = dotted.indexOf(".");
    return i < 0 ? {lib: dotted, mod: ""} : {lib: dotted.slice(0, i), mod: dotted.slice(i + 1)};
  }
  function label(lib, m) { return m ? lib + "." + m : lib; }

  function parse(text) {
    var out = [], seen = {}, m, rest = text;
    function add(name, dotted) {
      var s = typeof dotted === "string" ? split(dotted) : dotted, k = s.lib + ":" + s.mod + ":" + name;
      if (!seen[k] && (name === null || /^[A-Za-z_]\w*$/.test(name))) { seen[k] = 1; out.push({lib: s.lib, mod: s.mod, name: name}); }
    }
    var reErr = new RegExp("cannot import name " + Q + "([A-Za-z_]\\w*)" + Q + "\\s+from\\s+(?:partially initialized module\\s+)?" + Q + "(" + LIBRX + "(?:\\.\\w+)*)", "g");
    while ((m = reErr.exec(text))) add(m[1], m[2]);
    rest = rest.replace(reErr, " ").replace(/\([^()]*(?:site-packages|dist-packages|__init__\.py)[^()]*\)/g, " ");
    var reAttr = new RegExp("module " + Q + "(" + LIBRX + "(?:\\.\\w+)*)" + Q + " has no attribute " + Q + "([A-Za-z_]\\w*)", "g");
    while ((m = reAttr.exec(rest))) add(m[3], m[1]);
    rest = rest.replace(reAttr, " ");
    var reNoMod = new RegExp("(?:No module named|Failed to import)\\s+" + Q + "(" + LIBRX + "(?:\\.\\w+)+)", "g");
    while ((m = reNoMod.exec(rest))) add(null, m[1]);
    rest = rest.replace(reNoMod, " ");
    var reImp = new RegExp("from\\s+(" + LIBRX + "(?:\\.\\w+)*)\\s+import\\s+(\\([^)]*\\)|[^\\n;]+)", "g");
    while ((m = reImp.exec(rest))) {
      var where = m[1];
      m[3].replace(/#[^\n]*/g, " ").replace(/[()\\]/g, " ").split(",").forEach(function (p) {
        var n = p.trim().split(/\s+as\s+/)[0].trim();
        if (n) add(n, where);
      });
    }
    rest = rest.replace(reImp, " ");
    var rePlain = new RegExp("(?:^|\\n|;)\\s*import\\s+(" + LIBRX + "\\.\\w+(?:\\.\\w+)*)", "g");
    while ((m = rePlain.exec(rest))) add(null, m[1]);
    rest = rest.replace(rePlain, " ");
    if (!out.length) {
      var dotted = rest.match(new RegExp(LIBRX + "(?:\\.\\w+)+", "g")) || [];
      dotted.forEach(function (d) { add(null, d); });
      if (!dotted.length) (rest.match(/[A-Za-z_]\w{2,}/g) || []).forEach(function (w) { if (!STOP[w]) add(w, {lib: "?", mod: ""}); });
    }
    return out.slice(0, 30);
  }

  function vkey(v) { return v.split(".").map(function (x) { return parseInt(x, 10) || 0; }); }
  function cmp(a, b) { for (var i = 0; i < 3; i++) { if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) - (b[i] || 0); } return 0; }
  function indexOfVersion(D, v) {
    var k = vkey(v), idx = -1;
    for (var i = 0; i < D.releases.length; i++) if (cmp(vkey(D.releases[i][0]), k) <= 0) idx = i;
    return idx;
  }
  function pairs(D, ri) {
    var r = D.ranges[ri], out = [];
    for (var i = 0; i < r.length; i += 2) out.push([r[i], r[i + 1]]);
    return out;
  }
  function inRange(ps, i) { return ps.some(function (p) { return p[0] <= i && (p[1] === 0 || i < p[1]); }); }
  function modEver(D, m) { return m === "" || Object.prototype.hasOwnProperty.call(D.mods, m); }
  function modPairs(D, m) { return m === "" ? [[0, 0]] : pairs(D, D.mods[m]); }
  var PARTIAL = window.LOOKUP_PARTIAL || {};   // libraries whose first release read is not their first release
  function rangeText(D, p) {
    var a = D.releases[p[0]], early = p[0] === 0 && PARTIAL[D.lib] ? " or earlier (" + a[0] + " is the first release read)" : "";
    if (p[1] === 0) return "from <strong>" + a[0] + "</strong>" + (early || " (" + a[1] + ")") + " and still in " + D.latest;
    if (early) {
      var b0 = D.releases[p[1]];
      return "<strong>" + a[0] + "</strong>" + early + " through <strong>" + D.releases[p[1] - 1][2] + "</strong>; gone in " + b0[0] + " (" + b0[1] + ")";
    }
    var b = D.releases[p[1]];
    return "<strong>" + a[0] + "</strong> (" + a[1] + ") through <strong>" + D.releases[p[1] - 1][2] + "</strong>; gone in " + b[0] + " (" + b[1] + ")";
  }
  var PIP = window.LOOKUP_PIP || {};      // import name -> pip name, where they differ (sentence_transformers -> sentence-transformers)
  function pin(D, lib, p) {
    var lo = p[0] > 0 ? "&gt;=" + D.releases[p[0]][0] : "", pkg = PIP[lib] || lib;
    if (!p[1]) return lo ? "<span class=\"pin\">Needs: <code>pip install \"" + pkg + lo + "\"</code></span>" : "<span class=\"pin\">In every release read.</span>";
    return "<span class=\"pin\">Keep it: <code>pip install \"" + pkg + lo + (lo ? "," : "") + "&lt;" + D.releases[p[1]][0] + "\"</code></span>";
  }
  // other modules of the library that had the name in release i
  function alsoAt(D, lib, name, except, i) {
    var out = [];
    Object.keys(D.names).forEach(function (m) {
      var ri = D.names[m][name];
      if (m !== except && ri !== undefined && inRange(pairs(D, ri), i)) out.push(m);
    });
    out.sort(function (a, b) { return a.split(".").length - b.split(".").length || (a < b ? -1 : 1); });
    return out.slice(0, 4).map(function (m) { return code(label(lib, m)); });
  }
  function whereNow(D, lib, name, except) {
    var out = [], last = D.releases.length - 1;
    if (except !== "" && D.names[""][name] !== undefined && inRange(pairs(D, D.names[""][name]), last))
      out.push(code("from " + lib + " import " + name) + " (top level)");
    var w = D.where.names[name];
    if (w) {
      if (w[0] < 0) out.push("defined in " + (-w[0]) + " modules of " + lib + " " + D.latest);
      else {
        var ms = w.map(function (i) { return D.where.modules[i]; }).filter(function (m) { return m !== except; });
        if (ms.length) out.push("defined in " + ms.map(function (m) { return code(label(lib, m)); }).join(", ") + " in " + D.latest);
      }
    }
    return out;
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
  function mineText(has, lib, what) {
    return "<br><strong>Your " + lib + " " + esc($("v").value.trim()) + ": " + (has ? "has it" : "does not have it") + ".</strong>" +
      (has ? " If the error still names " + what + ", another copy of " + lib + " is being imported: check <code>python -c \"import " + lib + "; print(" + lib + ".__version__, " + lib + ".__file__)\"</code>." : "");
  }
  function row(nameHtml, sub, status, cell) {
    return "<tr><td>" + nameHtml + "<br><span class=\"note\">" + esc(sub) + "</span></td><td>" + status + "</td><td>" + cell + "</td></tr>";
  }
  function movedModule(D, m) {
    var leaf = m.split(".").pop(), last = D.releases.length - 1, out = [];
    Object.keys(D.mods).forEach(function (k) { if (k !== m && k.split(".").pop() === leaf && inRange(pairs(D, D.mods[k]), last)) out.push(k); });
    return out.slice(0, 4);
  }

  function answerModule(lib, m, mine) {
    var D = DATA[lib], cell, status;
    if (!modEver(D, m)) {
      var mv = movedModule(D, m);
      return row(code(label(lib, m)), "module", "<span class=\"s n\">never there</span>",
        "No release of " + lib + " from " + D.releases[0][0] + " to " + D.latest + " has this module." +
        (mv.length ? " Modules with the same last part in " + D.latest + ": " + mv.map(function (k) { return code(label(lib, k)); }).join(", ") + "." : ""));
    }
    var ps = modPairs(D, m), last = ps[ps.length - 1];
    status = last[1] === 0 ? "<span class=\"s y\">in " + D.latest + "</span>" : "<span class=\"s n\">gone</span>";
    cell = "The module exists " + ps.map(function (p) { return rangeText(D, p); }).join("<br>") + ".<br>" + pin(D, lib, last);
    if (last[1]) {
      var mv2 = movedModule(D, m);
      if (mv2.length) cell += "<br>Now: " + mv2.map(function (k) { return code(label(lib, k)); }).join(", ") + " (same file name, in " + D.latest + ").";
    }
    if (mine !== null) cell += mineText(inRange(ps, mine), lib, "the module");
    return row(code(label(lib, m)), "module", status, cell);
  }

  var SIB = window.LOOKUP_SIBLINGS || {};    // langchain -> [langchain_classic, langchain_core]: where a removed name went
  function siblingsNow(lib, m, name) {
    var out = [];
    (SIB[lib] || []).forEach(function (o) {
      var E = DATA[o];
      if (!E) return;
      var last = E.releases.length - 1, pkg = PIP[o] || o;
      if (E.names[m] && E.names[m][name] !== undefined && inRange(pairs(E, E.names[m][name]), last))
        out.push(code("from " + label(o, m) + " import " + name) + " (pip install " + pkg + ")");
      else {
        var w = E.where.names[name];
        if (w && w[0] >= 0) out.push(w.slice(0, 3).map(function (i) { return code("from " + label(o, E.where.modules[i]) + " import " + name); }).join(", ") + " (pip install " + pkg + ")");
        else if (E.names[""][name] !== undefined && inRange(pairs(E, E.names[""][name]), last)) out.push(code("from " + o + " import " + name) + " (pip install " + pkg + ")");
      }
    });
    return out;
  }
  function deferredNote(D, m, name) {
    var d = D.deferred && D.deferred[m] && D.deferred[m][name];
    if (d === undefined) return "";
    var via = D.via[m][name], top = via.split(".")[0], ps = pairs(D, d);
    return "<br><span class=\"note\">In " + ps.map(function (p) { return D.releases[p[0]][0] + (p[1] ? " to " + D.releases[p[1] - 1][2] : " on"); }).join(", ") +
      " this name is not defined here: the module forwards it to " + code(via) + " with a deprecation warning, so the import works only with " +
      code(PIP[top] || top.replace(/_/g, "-")) + " installed. Importing it from " + code(via) + " directly is the lasting fix.</span>";
  }
  // names that import but raise when used (openai 1.x keeps the 0.x names as APIRemovedInV1 proxies)
  function proxyPairs(D, m, name) {
    var x = D.proxies && D.proxies[m] && D.proxies[m][name];
    return x === undefined ? null : pairs(D, x);
  }
  function proxyNote(D, m, name) {
    var ps = proxyPairs(D, m, name);
    if (!ps) return "";
    return "<br><span class=\"note\">From " + ps.map(function (p) { return D.releases[p[0]][0] + (p[1] ? " to " + D.releases[p[1] - 1][2] : " on"); }).join(", ") +
      " the import succeeds but gives a placeholder: using it raises " + (window.LOOKUP_PROXY_MSG || "an error") + "</span>";
  }
  function answerName(lib, m, name, mine) {
    var D = DATA[lib];
    if (!modEver(D, m)) {
      var wn0 = whereNow(D, lib, name, null);
      return row(code(name), label(lib, m), "<span class=\"s n\">no such module</span>",
        "No release of " + lib + " from " + D.releases[0][0] + " to " + D.latest + " has a module " + code(label(lib, m)) + "." +
        (wn0.length ? " " + code(name) + ": " + wn0.join("; ") + "." : ""));
    }
    var table = D.names[m] || {}, ri = table[name], cell, status;
    if (ri === undefined) {
      var nn = near(name, Object.keys(table)), wn = whereNow(D, lib, name, m), mp = modPairs(D, m), ml = mp[mp.length - 1];
      var es = D.ext_star && D.ext_star[m];
      if (es) return row(code(name), label(lib, m), "<span class=\"s\">not listed</span>",
        code(label(lib, m)) + " passes along everything from " + es[1].map(code).join(" or ") + ", whose names this page does not list. The module exists " +
        pairs(D, es[0]).map(function (p) { return rangeText(D, p); }).join(", ") + ".");
      status = "<span class=\"s n\">never there</span>";
      cell = "No release of " + lib + " from " + D.releases[0][0] + " to " + D.latest + " lets you import this name from " + code(label(lib, m)) + "." +
        (ml[1] ? " The module itself is gone since " + D.releases[ml[1]][0] + "." : "") +
        (wn.length ? "<br>Now: " + wn.join("; ") + "." : "") +
        (nn.length ? "<br>Close names in this module: " + nn.map(code).join(", ") + "." : "") +
        (!wn.length && !nn.length ? " It may come from a fork, from the development branch, or from a release newer than " + D.latest + "." : "");
    } else {
      var ps = pairs(D, ri), last = ps[ps.length - 1];
      status = last[1] === 0 ? "<span class=\"s y\">in " + D.latest + "</span>" : "<span class=\"s n\">gone</span>";
      cell = ps.map(function (p) { return rangeText(D, p); }).join("<br>") + "<br>" + pin(D, lib, last);
      if (last[1]) {
        var at = alsoAt(D, lib, name, m, last[1]), wn2 = whereNow(D, lib, name, m), h = HINTS[lib + ":" + m + ":" + name];
        if (at.length) cell += "<br>In " + D.releases[last[1]][0] + ", the release that dropped it here, it was still importable from " + at.join(", ") + ".";
        if (wn2.length) cell += "<br>Now: " + wn2.join("; ") + ".";
        var sib = siblingsNow(lib, m, name);
        if (sib.length) cell += "<br>Now in another package: " + sib.join("; ") + ".";
        if (h) cell += "<br>Instead: " + h;
      }
      cell += deferredNote(D, m, name) + proxyNote(D, m, name);
      var pp = proxyPairs(D, m, name);
      if (pp && inRange(pp, D.releases.length - 1)) status = "<span class=\"s n\">placeholder</span>";
      var hp = HINTS[lib + ":" + m + ":" + name];
      if (pp && !last[1] && hp) cell += "<br>Instead: " + hp;
      if (mine !== null) cell += pp && inRange(pp, mine) ? "<br><strong>Your " + lib + " " + esc($("v").value.trim()) + ": has only the placeholder.</strong>" : mineText(inRange(ps, mine), lib, "it");
    }
    D.stale.forEach(function (s) {
      if (s[0] === m && s[1] === name)
        cell += "<br><span class=\"note\">From " + D.releases[s[4]][0] + (s[5] ? " through " + D.releases[s[5] - 1][2] : " on") +
          " the lazy table still lists this name, but the entry points to " + code(s[2]) + ", " +
          (s[3] === "nofile" ? "a file that is not there" : "which does not provide it") + ": the import fails.</span>";
    });
    return row(code(name), label(lib, m), status, cell);
  }

  function answerBare(name, mine) {
    var hits = [];
    LIBS.forEach(function (lib) {
      var D = DATA[lib];
      Object.keys(D.names).forEach(function (m) { if (D.names[m][name] !== undefined) hits.push([lib, m]); });
    });
    if (!hits.length) {
      var nn = [];
      LIBS.forEach(function (lib) { near(name, Object.keys(DATA[lib].names[""])).forEach(function (k) { nn.push(code(k) + " (" + lib + ")"); }); });
      return row(code(name), ALL, "<span class=\"s n\">never there</span>",
        "No release of " + ALL + " has this name in any module." + (nn.length ? " Close top-level names: " + nn.slice(0, 6).join(", ") + "." : "") +
        " If the error names another package, see the related pages at the bottom.");
    }
    hits.sort(function (a, b) { return (a[1] === "" ? 0 : 1) - (b[1] === "" ? 0 : 1) || a[1].split(".").length - b[1].split(".").length; });
    return hits.slice(0, 6).map(function (h) { return answerName(h[0], h[1], name, mine); }).join("") +
      (hits.length > 6 ? row(code(name), "", "", (hits.length - 6) + " more modules have this name; paste the import line to pick one.") : "");
  }

  function load(lib) {
    if (DATA[lib]) return Promise.resolve();
    return fetch(lib + ".json").then(function (r) { if (!r.ok) throw new Error(lib + ".json " + r.status); return r.json(); })
      .then(function (d) { DATA[lib] = d; });
  }
  function done() { $("res").setAttribute("data-done", String(++SEQ)); }
  function run() {
    var qs = parse($("q").value), v = $("v").value.trim(), want = {};
    $("status").textContent = "";
    if (v && !/^v?\d+\.\d+(\.\d+)?/.test(v)) { $("status").textContent = "Version should look like 0.13.2."; done(); return; }
    if (!qs.length) { $("res").innerHTML = "<p class=\"note\">Found no name. Paste the ImportError line, the import statement, or just the name.</p>"; done(); return; }
    qs.forEach(function (q) {
      if (q.lib === "?") LIBS.forEach(function (l) { want[l] = 1; });
      else { want[q.lib] = 1; (SIB[q.lib] || []).forEach(function (l) { want[l] = 1; }); }
    });
    $("status").textContent = "Loading the names...";
    Promise.all(Object.keys(want).map(load)).then(function () {
      $("status").textContent = "";
      var libsSeen = {};
      $("res").innerHTML = "<div class=\"tw\"><table><thead><tr><th>Name</th><th>Now</th><th>Releases that have it</th></tr></thead><tbody>" +
        qs.map(function (q) {
          if (q.lib === "?") return answerBare(q.name, null);
          var D = DATA[q.lib], mine = v ? indexOfVersion(D, v.replace(/^v/, "")) : null;
          libsSeen[q.lib] = 1;
          if (mine !== null && mine < 0) mine = null;
          return q.name === null ? answerModule(q.lib, q.mod, mine) : answerName(q.lib, q.mod, q.name, mine);
        }).join("") + "</tbody></table></div>" +
        "<p class=\"note\">" + Object.keys(want).map(function (l) {
          var D = DATA[l]; return l + ": " + D.releases.length + " releases read, " + D.releases[0][0] + " to " + D.latest +
            (D.every ? " (every tagged release)" : " (the first release of each minor version; patch releases in between are assumed to keep the names)");
        }).join("; ") + "." +
        (v && Object.keys(libsSeen).length > 1 ? " Your version was compared with every library named; give one library per lookup for a clean comparison." : "") + "</p>";
      done();
    }).catch(function (e) { $("status").textContent = "Could not load the names (" + e.message + "). The tables below still apply."; done(); });
  }
  $("go").addEventListener("click", run);
  $("q").addEventListener("keydown", function (e) { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run(); });
  Array.prototype.forEach.call(document.querySelectorAll("[data-ex]"), function (b) {
    b.addEventListener("click", function () { $("q").value = b.getAttribute("data-ex"); $("v").value = b.getAttribute("data-v") || ""; run(); });
  });
  window.PTA_READY = true;
  var p = new URLSearchParams(location.search);
  if (p.get("q")) { $("q").value = p.get("q"); $("v").value = p.get("v") || ""; run(); }
})();
