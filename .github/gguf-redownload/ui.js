// UI for the GGUF redownload check. Needs window.GH (ggufhist.js).
(function () {
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c]));
  const HF = "https://huggingface.co";
  let ST = null; // {repo, path, versions, headers:{commit:header}}
  const status = t => { $("status").textContent = t; };
  function parseRepo(s) {
    s = s.trim();
    let m = /huggingface\.co\/([^\/\s]+\/[^\/\s?#]+)(?:\/(?:blob|resolve|tree)\/[^\/]+\/([^\s?#]+))?/.exec(s);
    if (m) return { repo: m[1], path: m[2] ? decodeURIComponent(m[2]) : null };
    m = /^(?:hf\.co\/)?([^\/\s:]+\/[^\/\s:]+)(?::([^\s]+))?$/.exec(s);
    if (m) return { repo: m[1], tag: m[2] || null };
    return null;
  }
  async function listFiles(repo) {
    const r = await fetch(HF + "/api/models/" + repo);
    if (r.status === 401 || r.status === 403) throw new Error("This repository is gated or private; the check only works on public repositories.");
    if (!r.ok) throw new Error("HTTP " + r.status + ": repository " + repo + " not found");
    const j = await r.json();
    return (j.siblings || []).map(s => s.rfilename).filter(f => /\.gguf$/i.test(f));
  }
  async function loadRepo() {
    const p = parseRepo($("repo").value);
    $("res").innerHTML = ""; $("files").innerHTML = "";
    if (!p) { status("Enter a repository like bartowski/Meta-Llama-3.1-8B-Instruct-GGUF or a Hugging Face URL."); return; }
    status("Listing files...");
    try {
      const files = await listFiles(p.repo);
      if (!files.length) { status("No .gguf files in " + p.repo + "."); return; }
      const sel = $("files");
      for (const f of files) { const o = document.createElement("option"); o.value = o.textContent = f; sel.appendChild(o); }
      let want = p.path;
      if (!want && p.tag) want = files.find(f => f.toUpperCase().includes(p.tag.toUpperCase()) && !/-0000[2-9]-of-/.test(f));
      if (want && files.includes(want)) sel.value = want;
      if (p.tag) $("olltag").value = p.tag;
      $("step2").hidden = false;
      status(files.length + " GGUF files. Pick yours, then say what you have.");
      ST = { repo: p.repo };
    } catch (e) { status(String(e.message || e)); }
  }
  function fmtSize(n) { return n == null ? "" : (n / 1e9).toFixed(2) + " GB"; }
  function cmdsFor(d) {
    // commands that turn the old file's metadata into the new one, when only metadata changed
    const lines = [], cannot = [];
    for (const k of d.kv) {
      if (k.key === "tokenizer.chat_template") lines.push("--chat-template-file chat_template.jinja");
      else if (k.key === "tokenizer.ggml.pre" && k.kind === "changed") lines.push("--pre-tokenizer " + k.new);
      else if (k.key === "general.name" && k.new != null) lines.push("--general-name " + JSON.stringify(k.new));
      else if (k.key === "general.description" && k.new != null) lines.push("--general-description " + JSON.stringify(k.new));
      else if (/^tokenizer\.ggml\.(.+)_token_id$/.test(k.key) && k.new != null) lines.push("--special-token-by-id " + /^tokenizer\.ggml\.(.+)_token_id$/.exec(k.key)[1] + " " + k.new);
      else if (k.kind === "removed") lines.push("--remove-metadata " + k.key);
      else cannot.push(k);
    }
    const set = [];
    for (const k of cannot.slice()) {
      if (k.kind === "changed" && /^(true|false|-?\d+(\.\d+)?(e-?\d+)?)$/.test(String(k.new)) && /^(true|false|-?\d+(\.\d+)?(e-?\d+)?)$/.test(String(k.old))) {
        set.push("gguf-set-metadata --force fixed.gguf " + k.key + " " + (k.new === "false" ? "''" : k.new));
        cannot.splice(cannot.indexOf(k), 1);
      }
    }
    return { lines, set, cannot };
  }
  function kvTable(d) {
    if (!d.kv.length) return "<p>No metadata keys changed.</p>";
    return '<div class="tw"><table><thead><tr><th>Key</th><th>Your file</th><th>Newest file</th></tr></thead><tbody>' +
      d.kv.map(k => {
        const cut = v => v == null ? "<em>absent</em>" : (k.key === "tokenizer.chat_template" ? (v.length + " characters") : esc(String(v).length > 120 ? String(v).slice(0, 120) + "..." : v));
        return "<tr><td><code>" + esc(k.key) + "</code></td><td>" + cut(k.old) + "</td><td>" + cut(k.new) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }
  function tensorLine(t) {
    const p = [];
    if (t.added.length) p.push(t.added.length + (t.added.length > 1 ? " tensors" : " tensor") + " added (" + t.added.slice(0, 3).map(esc).join(", ") + (t.added.length > 3 ? ", ..." : "") + ")");
    if (t.removed.length) p.push(t.removed.length + (t.removed.length > 1 ? " tensors" : " tensor") + " removed");
    if (t.type.length) p.push(t.type.length + (t.type.length > 1 ? " tensors" : " tensor") + " changed quantization type (e.g. " + esc(t.type[0].name) + " " + t.type[0].old + " to " + t.type[0].new + ")");
    if (t.shape.length) p.push(t.shape.length + " changed shape");
    if (!p.length && t.moved) p.push(t.moved + " tensors moved inside the file");
    return p.join("; ");
  }
  async function hdr(commit) {
    ST.headers = ST.headers || {};
    if (!ST.headers[commit]) ST.headers[commit] = await GH.header(GH.fileUrl(ST.repo, commit, ST.path));
    return ST.headers[commit];
  }
  async function classify(oldC, newC, oldSrc, oldH) {
    const a = oldH || await hdr(oldC), b = await hdr(newC);
    const d = GH.diff(a, b);
    let same = null, n = 0, differ = [];
    if (d.layoutSame) {
      const r = await GH.sameData(oldSrc || GH.fileUrl(ST.repo, oldC, ST.path), a, GH.fileUrl(ST.repo, newC, ST.path), b, 16);
      n = r.length; same = r.filter(x => x.same).length; differ = r.filter(x => !x.same).map(x => x.name);
    }
    return { d, same, n, differ, kind: !d.layoutSame ? "tensors" : same < n ? "weights" : d.kv.length ? "metadata" : "none" };
  }
  function verdictHtml(c, yours, latest) {
    const when = "between your version (" + yours.date.slice(0, 10) + ") and the newest (" + latest.date.slice(0, 10) + ")";
    if (c.kind === "none") return '<div class="verdict v-ok">No difference found ' + when + '.<span>The metadata is identical and all ' + c.n + ' sampled tensors start with the same bytes, but the sha256 differs, so something changed outside the sampled bytes. If you want to be sure, redownload.</span></div>';
    if (c.kind === "metadata") {
      const k = cmdsFor(c.d);
      let h = '<div class="verdict v-load">Only metadata changed ' + when + '. You can patch your file instead of downloading ' + fmtSize(latest.size) + ".<span>The tensors have the same names, types and shapes, and the first 4 KiB of all " + c.n + " sampled tensors are identical.</span></div>" + kvTable(c.d);
      if (!k.cannot.length) {
        h += "<p><strong>Patch</strong> (<code>pip install gguf</code>):</p><pre><code>gguf-new-metadata --force your.gguf fixed.gguf " + esc(k.lines.join(" ")) + (k.set.length ? "\n" + esc(k.set.join("\n")) : "") + "</code></pre>";
        if (c.d.kv.some(x => x.key === "tokenizer.chat_template")) h += '<p><button type="button" id="tpl">Download the new chat template as chat_template.jinja</button></p>';
        h += '<p class="note">The patched file has the same metadata as the newest one but not the same sha256, because the keys are written in another order. Check the result with this tool by picking the patched file.</p>';
      } else {
        h += "<p>These keys cannot be set with the gguf tools: " + k.cannot.map(x => "<code>" + esc(x.key) + "</code>").join(", ") + ". Redownload, or keep your file if those keys do not matter to you.</p>";
      }
      return h;
    }
    if (c.kind === "weights") return '<div class="verdict v-bad">The weights changed ' + when + '. Redownload.<span>The tensors have the same names, types and shapes, but ' + (c.n - c.same) + " of " + c.n + " sampled tensors have different bytes (" + c.differ.slice(0, 3).map(esc).join(", ") + (c.differ.length > 3 ? ", ..." : "") + "): the file was quantized again, for example with a new importance matrix.</span></div>" + kvTable(c.d);
    return '<div class="verdict v-bad">The tensors changed ' + when + ". Redownload.<span>" + tensorLine(c.d.tensors) + ".</span></div>" + kvTable(c.d);
  }
  function versionTable(v, mark) {
    return '<div class="tw"><table id="vt"><thead><tr><th>#</th><th>Uploaded (UTC)</th><th>Commit</th><th>sha256</th><th>Size</th><th>What changed from the previous</th></tr></thead><tbody>' +
      v.map((x, i) => '<tr id="v-' + x.commit.slice(0, 8) + '"' + (x.commit === mark ? ' class="hit"' : "") + "><td>" + (v.length - i) + (x.commit === mark ? " <strong>yours</strong>" : "") + (i === 0 ? " <strong>newest</strong>" : "") + "</td><td>" + x.date.slice(0, 16).replace("T", " ") + '</td><td><a href="' + HF + "/" + ST.repo + "/commit/" + x.commit + '">' + x.commit.slice(0, 8) + "</a> " + esc(x.title) + "</td><td><code>" + (x.sha256 || "").slice(0, 12) + "</code></td><td>" + fmtSize(x.size) + '</td><td class="why" data-i="' + i + '">' + (i === v.length - 1 ? "first upload" : '<span class="meta">-</span>') + "</td></tr>").join("") + "</tbody></table></div>";
  }
  async function check() {
    if (!ST) { await loadRepo(); if (!ST) return; }
    ST.path = $("files").value;
    const res = $("res"); res.innerHTML = "";
    try {
      status("Reading the history of " + ST.path + "...");
      const v = await GH.versions(ST.repo, ST.path, 60);
      ST.versions = v; ST.headers = {};
      const latest = v[0];
      let yours = null, how = "", oldSrc = null, oldH = null;
      let sha = $("sha").value.trim().toLowerCase().replace(/^sha256[-:]/, "");
      const m = /[0-9a-f]{64}/.exec(sha); sha = m ? m[0] : "";
      const file = $("local").files[0];
      const tag = $("olltag").value.trim();
      if (sha) { yours = v.find(x => x.sha256 === sha); how = "sha256"; }
      else if (tag && !file) {
        status("Asking the Hugging Face registry what Ollama gets for " + tag + "...");
        const od = await GH.ollamaDigest(ST.repo, tag);
        if (!od) throw new Error("No Ollama manifest for " + ST.repo + ":" + tag + ".");
        res.innerHTML = '<p>Ollama pulls <code>hf.co/' + esc(ST.repo) + ":" + esc(tag) + "</code> as the file with sha256 <code>" + od.digest.slice(0, 12) + "...</code>" + (od.digest === latest.sha256 ? " (the newest version of " + esc(ST.path) + ")." : ".") + " Compare it with your copy: <code>ollama show --modelfile hf.co/" + esc(ST.repo) + ":" + esc(tag) + "</code> prints <code>FROM .../blobs/sha256-...</code>. Paste that hash above.</p>";
        status(""); $("vlist").innerHTML = versionTable(v, null); return;
      } else if (file) {
        how = "header";
        status("Reading the header of your file...");
        oldH = await GH.header(file); oldSrc = file;
        for (const x of v) {
          status("Comparing with version " + x.date.slice(0, 10) + "...");
          const h = await hdr(x.commit);
          if (h.fingerprint === oldH.fingerprint && x.size === file.size) { yours = x; break; }
        }
        if (!yours) {
          const c = await classify(null, latest.commit, file, oldH);
          res.innerHTML = '<div class="verdict v-load">Your file matches none of the ' + v.length + " uploaded versions exactly.<span>It may have been patched, converted by you, or come from another repository. Compared with the newest version:</span></div>" + verdictHtml(c, { date: "unknown" }, latest).replace(/^<div[^>]*>.*?<\/div>/, "");
          $("vlist").innerHTML = versionTable(v, null); status(""); return;
        }
      } else { status("Paste a sha256, pick your file, or give your Ollama tag."); $("vlist").innerHTML = versionTable(v, null); return; }
      $("vlist").innerHTML = versionTable(v, yours && yours.commit);
      if (!yours) {
        res.innerHTML = '<div class="verdict v-bad">This sha256 is not any version of ' + esc(ST.path) + " in " + esc(ST.repo) + ".<span>Check the repository and file name. Ollama and the Hugging Face cache name the blob by this sha256; LM Studio and others keep the file, so run <code>sha256sum</code> on it, or pick the file instead.</span></div>";
        status(""); return;
      }
      if (yours.commit === latest.commit) {
        res.innerHTML = '<div class="verdict v-ok">You have the newest version (' + latest.date.slice(0, 10) + ").<span>" + (v.length > 1 ? "The file was uploaded " + v.length + " times; yours is the last." : "The file was never replaced.") + "</span></div>";
        status(""); return;
      }
      const behind = v.indexOf(yours);
      status("Comparing your version with the newest...");
      const c = await classify(yours.commit, latest.commit, how === "header" ? oldSrc : null, how === "header" ? oldH : null);
      res.innerHTML = "<p>Your version is " + behind + " upload" + (behind > 1 ? "s" : "") + " behind (matched by " + (how === "sha256" ? "sha256" : "header and size") + ").</p>" + verdictHtml(c, yours, latest) + '<p><button type="button" id="each">Explain each re-upload</button></p>';
      const tb = $("tpl"); if (tb) tb.onclick = async () => {
        const h = await hdr(latest.commit);
        const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([h.kv["tokenizer.chat_template"].value], { type: "text/plain" })); a.download = "chat_template.jinja"; a.click();
      };
      $("each").onclick = explainEach;
      status("");
    } catch (e) { status(String(e.message || e)); }
  }
  async function explainEach() {
    const v = ST.versions;
    for (let i = 0; i < v.length - 1; i++) {
      const cell = document.querySelector('td.why[data-i="' + i + '"]');
      cell.textContent = "reading...";
      try {
        const c = await classify(v[i + 1].commit, v[i].commit);
        const keys = [...new Set(c.d.kv.map(k => /^quantize\.imatrix/.test(k.key) ? "imatrix" : /^general\./.test(k.key) ? "general.*" : k.key.replace(/^tokenizer\.ggml\./, "").replace(/^tokenizer\./, "")))].slice(0, 4).join(", ");
        cell.innerHTML = (c.kind === "metadata" ? '<span class="s y">metadata</span> ' : c.kind === "none" ? '<span class="s">no visible change</span> ' : '<span class="s n">' + (c.kind === "weights" ? "weights" : "tensors") + "</span> ") + esc(keys || "") + (c.kind === "tensors" ? " " + esc(tensorLine(c.d.tensors).replace(/\(.*?\)/g, "")) : "");
      } catch (e) { cell.textContent = String(e.message || e); }
      delete ST.headers[v[i].commit];
    }
  }
  $("load").addEventListener("click", loadRepo);
  $("repo").addEventListener("keydown", e => { if (e.key === "Enter") loadRepo(); });
  $("go").addEventListener("click", check);
  const q = new URLSearchParams(location.search);
  if (q.get("repo")) { $("repo").value = q.get("repo"); loadRepo().then(() => { if (q.get("file")) $("files").value = q.get("file"); if (q.get("sha")) { $("sha").value = q.get("sha"); check(); } }); }
})();
