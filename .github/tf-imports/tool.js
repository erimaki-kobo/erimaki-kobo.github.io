(function () {
  "use strict";
  var D = null, HINTS = window.TF_HINTS, GROUPS = window.TF_GROUPS;
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  var MODS = {"transformers": "top", "transformers.utils": "utils", "transformers.file_utils": "file_utils"};
  var LABEL = {top: "transformers", utils: "transformers.utils", file_utils: "transformers.file_utils"};
  var STOP = {from: 1, "import": 1, transformers: 1, utils: 1, file_utils: 1, ImportError: 1, cannot: 1, name: 1, as: 1,
    unknown: 1, location: 1, py: 1, __init__: 1, site: 1, packages: 1, lib: 1, python: 1, usr: 1, local: 1, dist: 1};

  function parse(text) {
    var out = [], seen = {}, m;
    function add(name, mod) {
      var k = mod + ":" + name;
      if (!seen[k] && /^[A-Za-z_]\w*$/.test(name)) { seen[k] = 1; out.push({name: name, mod: mod}); }
    }
    var rest = text;
    var reErr = /cannot import name ['"`\u2018\u2019]?([A-Za-z_]\w*)['"`\u2018\u2019]?\s+from\s+['"`\u2018\u2019]?(transformers(?:\.\w+)*)/g;
    while ((m = reErr.exec(text))) add(m[1], MODS[m[2]] || "other:" + m[2]);
    rest = rest.replace(reErr, " ").replace(/\([^()]*site-packages[^()]*\)/g, " ");
    var reImp = /from\s+(transformers(?:\.\w+)*)\s+import\s+(\([^)]*\)|[^\n;]+)/g;
    while ((m = reImp.exec(rest))) {
      var mod = MODS[m[1]] || "other:" + m[1];
      m[2].replace(/[()\\]/g, " ").split(",").forEach(function (p) {
        var n = p.trim().split(/\s+as\s+/)[0].trim();
        if (n) add(n, mod);
      });
    }
    rest = rest.replace(reImp, " ");
    if (!out.length) {
      (rest.match(/[A-Za-z_]\w{2,}/g) || []).forEach(function (w) { if (!STOP[w] && !/^\d/.test(w)) add(w, "any"); });
    }
    return out.slice(0, 40);
  }

  function rel(i) { return D.releases[i]; }
  function vkey(v) { return v.split(".").map(function (x) { return parseInt(x, 10) || 0; }); }
  function cmp(a, b) { for (var i = 0; i < 3; i++) { if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) - (b[i] || 0); } return 0; }
  function indexOfVersion(v) {
    var k = vkey(v), idx = -1;
    for (var i = 0; i < D.releases.length; i++) if (cmp(vkey(rel(i)[0]), k) <= 0) idx = i;
    return idx;
  }
  function pairs(kind, name) {
    var r = D[kind][name];
    if (!r) return null;
    if (kind === "top") r = r.slice(1);
    var out = [];
    for (var i = 0; i < r.length; i += 2) out.push([r[i], r[i + 1]]);
    return out;
  }
  function inRange(ps, i) { return ps.some(function (p) { return p[0] <= i && (p[1] === 0 || i < p[1]); }); }
  function aliasAt(name, i) {
    var a = D.alias[name] || [];
    for (var k = 0; k < a.length; k++) if (a[k][0] <= i && (a[k][1] === 0 || i < a[k][1])) return a[k][2];
    return null;
  }
  function lastBefore(i) { return rel(i - 1)[2]; }
  function rangeText(p, aliased) {
    var a = rel(p[0]);
    if (p[1] === 0) return "from <strong>" + a[0] + "</strong> (" + a[1] + ") and still in " + D.latest;
    var b = rel(p[1]);
    return "<strong>" + a[0] + "</strong> (" + a[1] + ") through <strong>" + lastBefore(p[1]) + "</strong>; " + (aliased === true ? "left the lists in " : "gone in ") + b[0] + " (" + b[1] + ")";
  }
  function hintFor(name, kind, p) {
    if (p[1] === 0) return "";
    var h = HINTS[kind + ":" + name];
    if (h) return h;
    var goneIn = rel(p[1])[0];
    for (var i = 0; i < GROUPS.length; i++) {
      var g = GROUPS[i];
      if (g[0] === kind && g[1] === goneIn && new RegExp(g[2]).test(name)) return g[3];
    }
    return "";
  }
  function minor(v) { return v.split(".").slice(0, 2).join(".") + ".x"; }
  function usersOf(kind, name) {
    var u = (D.users || {})[kind + ":" + name];
    if (!u) return "";
    return "<br>Imported at module level by: " + Object.keys(u).sort().map(function (lib) {
      return u[lib].map(function (r) {
        return "<strong>" + esc(lib) + "</strong> " + r[0] + " to " + minor(r[1]) +
          (r[3] ? " (no longer from " + r[3] + ")" : " (still, in the newest release)") + ", in <code>" + esc(r[2]) + "</code>";
      }).join("; ");
    }).join("; ") + ".";
  }
  function near(name, kind) {
    var low = name.toLowerCase(), keys = Object.keys(D[kind]), exact = [], sub = [];
    keys.forEach(function (k) {
      var kl = k.toLowerCase();
      if (kl === low) exact.push(k);
      else if (low.length >= 5 && (kl.indexOf(low) >= 0 || low.indexOf(kl) >= 0 && kl.length >= 6)) sub.push(k);
    });
    sub.sort(function (a, b) { return Math.abs(a.length - name.length) - Math.abs(b.length - name.length); });
    return exact.concat(sub).slice(0, 6);
  }

  function answer(q, mine) {
    var name = q.name, kind = q.mod, h = "";
    if (kind.indexOf("other:") === 0) {
      return "<tr><td><code>" + esc(name) + "</code></td><td><span class=\"s p\">not covered</span></td><td>This page reads <code>transformers</code>, " +
        "<code>transformers.utils</code> and <code>transformers.file_utils</code>, not <code>" + esc(kind.slice(6)) + "</code>. " +
        (D.top[name] ? "The same name at the top level: " + pairs("top", name).map(rangeText).join("; ") + "." : "") + "</td></tr>";
    }
    var kinds = kind === "any" ? ["top", "utils", "file_utils"].filter(function (k) { return D[k][name]; }) : [kind];
    if (kind === "any" && !kinds.length) kinds = ["top"];
    kinds.forEach(function (k) {
      var ps = pairs(k, name), cell, status;
      var alias = k === "top" ? D.alias[name] : null;
      if (!ps && !alias) {
        var also = ["top", "utils", "file_utils"].filter(function (o) { return o !== k && D[o][name]; });
        var nn = near(name, k);
        status = "<span class=\"s n\">never there</span>";
        cell = "No release from " + rel(0)[0] + " to " + D.latest + " has this name in <code>" + LABEL[k] + "</code>." +
          (also.length ? " It is a name of " + also.map(function (o) { return "<code>" + LABEL[o] + "</code> (" + pairs(o, name).map(rangeText).join("; ") + ")"; }).join(" and ") + "." : "") +
          (nn.length ? " Close names: " + nn.map(function (x) { return "<code>" + esc(x) + "</code>"; }).join(", ") + "." : "") +
          " If another package asks for it, the name may come from a fork or from a release newer than " + D.latest + ".";
      } else {
        ps = ps || [];
        var last = ps.length ? ps[ps.length - 1] : null, now = last && last[1] === 0;
        var nowAlias = k === "top" ? aliasAt(name, D.releases.length - 1) : null;
        status = now ? "<span class=\"s y\">in " + D.latest + "</span>"
          : nowAlias ? "<span class=\"s y\">imports in " + D.latest + "</span>" : "<span class=\"s n\">gone</span>";
        cell = ps.map(function (p) { return rangeText(p, !!(alias && p[1] && aliasAt(name, p[1]))); }).join("<br>");
        if (alias) {
          cell += (cell ? "<br>" : "") + alias.map(function (a) {
            return "From " + rel(a[0])[0] + (a[1] ? " through " + lastBefore(a[1]) : " on") + " it is in no list but still imports: the lazy module hands back <code>" + esc(a[2]) + "</code>.";
          }).join("<br>");
        }
        if (last && !now && !nowAlias) {
          var hint = hintFor(name, k, last);
          cell += "<br><span class=\"pin\">Keep it: <code>pip install \"transformers&gt;=" + rel(last[0])[0] + ",&lt;" + rel(last[1])[0] + "\"</code></span>" +
            (hint ? "<br>Instead: " + hint : "") + usersOf(k, name);
        } else if (last && last[0] > 0 && (now || nowAlias)) {
          cell += "<br><span class=\"pin\">Needs: <code>pip install \"transformers&gt;=" + rel(last[0])[0] + "\"</code></span>";
        }
        if (k === "top" && ps.length) cell += "<br><span class=\"note\">" + (now ? "Lives in" : "Lived in") + " <code>transformers." + esc(D.modules[D.top[name][0]]) + "</code></span>";
        if (mine !== null) {
          var has = inRange(ps, mine) || (k === "top" && aliasAt(name, mine));
          cell += "<br><strong>Your " + esc($("v").value.trim()) + ": " + (has ? "has it" : "does not have it") + ".</strong>" +
            (has ? " If the error still names it, another copy of transformers is being imported: check <code>python -c \"import transformers; print(transformers.__version__, transformers.__file__)\"</code>." : "");
        }
      }
      h += "<tr><td><code>" + esc(name) + "</code><br><span class=\"note\">" + LABEL[k] + "</span></td><td>" + status + "</td><td>" + cell + "</td></tr>";
    });
    return h;
  }

  function run() {
    var qs = parse($("q").value), v = $("v").value.trim(), mine = null;
    $("status").textContent = "";
    if (!D) { $("status").textContent = "The data is still loading."; return; }
    if (v) {
      if (!/^v?\d+\.\d+(\.\d+)?/.test(v)) { $("status").textContent = "Version should look like 4.57.1."; return; }
      mine = indexOfVersion(v.replace(/^v/, ""));
      if (mine < 0) { $("status").textContent = "Releases before " + rel(0)[0] + " are not covered."; return; }
    }
    if (!qs.length) { $("res").innerHTML = "<p class=\"note\">Found no name. Paste the ImportError line, the import statement, or just the name.</p>"; return; }
    $("res").innerHTML = "<div class=\"tw\"><table><thead><tr><th>Name</th><th>Now</th><th>Releases that have it</th></tr></thead><tbody>" +
      qs.map(function (q) { return answer(q, mine); }).join("") + "</tbody></table></div>" +
      "<p class=\"note\">Read at the first release of every minor version (" + D.releases.length + " releases, " + rel(0)[0] + " to " + D.latest + "); patch releases in between are assumed to keep the names.</p>";
  }

  $("go").addEventListener("click", run);
  $("q").addEventListener("keydown", function (e) { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run(); });
  Array.prototype.forEach.call(document.querySelectorAll("[data-ex]"), function (b) {
    b.addEventListener("click", function () { $("q").value = b.getAttribute("data-ex"); $("v").value = b.getAttribute("data-v") || ""; run(); });
  });
  fetch("data.json").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
    D = d; window.TF_DATA = d;
    var q = new URLSearchParams(location.search).get("q");
    if (q) { $("q").value = q; $("v").value = new URLSearchParams(location.search).get("v") || ""; run(); }
  }).catch(function (e) { $("status").textContent = "Could not load data.json (" + e.message + "). The tables below still apply."; });
})();
