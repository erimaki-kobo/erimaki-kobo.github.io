// GGUF file history on the Hugging Face Hub, read in the browser.
// - versions(repo, path): every version of one file (commit, date, title, sha256, size), newest first,
//   walking lastCommit through /api/models/{repo}/paths-info/{rev} (one request per version).
// - header(src): parse a GGUF header (metadata and tensor infos) from a URL (HTTP range) or a File.
// - diff(a, b): what changed between two headers.
// - sameData(srcA, hA, srcB, hB, n): compare n sampled 4 KiB ranges of tensor data at the same offsets.
// No dependencies. Exposes window.GH.
(function () {
  const HF = "https://huggingface.co";
  const TYPES = ["u8", "i8", "u16", "i16", "u32", "i32", "f32", "bool", "str", "arr", "u64", "i64", "f64"];
  const SIZE = { 0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8 };
  const GGML = { 0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S", 20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64", 29: "IQ1_M", 30: "BF16", 34: "TQ1_0", 35: "TQ2_0", 39: "MXFP4" };
  const enc = new TextEncoder(), dec = new TextDecoder();

  async function sha256hex(u8) {
    const d = await crypto.subtle.digest("SHA-256", u8);
    return [...new Uint8Array(d)].map(x => x.toString(16).padStart(2, "0")).join("");
  }
  function fileUrl(repo, rev, path) {
    return HF + "/" + repo + "/resolve/" + rev + "/" + path.split("/").map(encodeURIComponent).join("/");
  }
  // reader over a URL (range requests) or a File (slice)
  function source(src) {
    if (typeof src === "string") {
      return async (a, b) => {
        const r = await fetch(src, { headers: { Range: "bytes=" + a + "-" + (b - 1) } });
        if (r.status !== 206 && r.status !== 200) throw new Error("HTTP " + r.status + " reading " + src);
        const buf = new Uint8Array(await r.arrayBuffer());
        return r.status === 200 ? buf.slice(a, b) : buf;
      };
    }
    return async (a, b) => new Uint8Array(await src.slice(a, b).arrayBuffer());
  }

  async function header(src, opt = {}) {
    const read = source(src);
    let buf = await read(0, opt.first || 1 << 21);
    let pos = 0;
    async function need(n) {
      while (pos + n > buf.length) {
        const more = await read(buf.length, buf.length * 2);
        if (!more.length) throw new Error("file ends inside the header");
        const nb = new Uint8Array(buf.length + more.length); nb.set(buf); nb.set(more, buf.length); buf = nb;
      }
    }
    const dv = () => new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
    async function u32() { await need(4); const v = dv().getUint32(pos, true); pos += 4; return v; }
    async function u64() { await need(8); const v = dv().getBigUint64(pos, true); pos += 8; return Number(v); }
    async function str() { const n = await u64(); await need(n); const s = dec.decode(buf.subarray(pos, pos + n)); pos += n; return s; }
    async function scalar(t) {
      const n = SIZE[t]; await need(n); const d = dv(); let v;
      switch (t) {
        case 0: v = d.getUint8(pos); break; case 1: v = d.getInt8(pos); break; case 2: v = d.getUint16(pos, true); break;
        case 3: v = d.getInt16(pos, true); break; case 4: v = d.getUint32(pos, true); break; case 5: v = d.getInt32(pos, true); break;
        case 6: v = d.getFloat32(pos, true); break; case 7: v = d.getUint8(pos) !== 0; break; case 10: v = Number(d.getBigUint64(pos, true)); break;
        case 11: v = Number(d.getBigInt64(pos, true)); break; case 12: v = d.getFloat64(pos, true); break;
      }
      pos += n; return v;
    }
    await need(24);
    const magic = dec.decode(buf.subarray(0, 4));
    if (magic !== "GGUF") throw new Error("not a GGUF file (magic " + JSON.stringify(magic) + ")");
    pos = 4;
    const version = await u32(), nt = await u64(), nkv = await u64();
    const kv = {};
    for (let i = 0; i < nkv; i++) {
      const key = await str();
      const t = await u32();
      const start = pos;
      let e;
      if (t === 8) { const v = await str(); e = { type: "str", value: v }; }
      else if (t === 9) {
        const at = await u32(), n = await u64();
        if (at === 8) { for (let j = 0; j < n; j++) await str(); }
        else { await need(SIZE[at] * n); pos += SIZE[at] * n; }
        e = { type: "arr[" + TYPES[at] + "]", n, digest: (await sha256hex(buf.slice(start, pos))).slice(0, 16) };
        if (n <= 16 && at !== 8) { /* keep small numeric arrays readable */
          const vals = []; const d = dv(); let p = start + 12;
          for (let j = 0; j < n; j++) { vals.push(at === 6 ? d.getFloat32(p, true) : at === 5 ? d.getInt32(p, true) : at === 4 ? d.getUint32(p, true) : at === 7 ? d.getUint8(p) !== 0 : d.getUint8(p)); p += SIZE[at]; }
          e.value = vals;
        }
      } else e = { type: TYPES[t], value: await scalar(t) };
      kv[key] = e;
    }
    const tensors = [];
    for (let i = 0; i < nt; i++) {
      const name = await str(); const nd = await u32(); const dims = [];
      for (let j = 0; j < nd; j++) dims.push(await u64());
      const type = await u32(); const off = await u64();
      tensors.push({ name, dims, type: GGML[type] || String(type), off });
    }
    const align = kv["general.alignment"] ? kv["general.alignment"].value : 32;
    const dataStart = Math.ceil(pos / align) * align;
    return { version, kv, tensors, dataStart, headerBytes: pos, fingerprint: await sha256hex(buf.slice(0, pos)) };
  }

  function show(e) {
    if (!e) return null;
    if ("value" in e) { const s = typeof e.value === "string" ? e.value : JSON.stringify(e.value); return s; }
    return e.type + " x" + e.n + " #" + e.digest;
  }
  function diff(a, b) {
    const keys = [...new Set([...Object.keys(a.kv), ...Object.keys(b.kv)])].sort();
    const kv = [];
    for (const k of keys) {
      const x = show(a.kv[k]), y = show(b.kv[k]);
      if (x !== y) kv.push({ key: k, old: x, new: y, kind: x === null ? "added" : y === null ? "removed" : "changed" });
    }
    const ta = new Map(a.tensors.map(t => [t.name, t])), tb = new Map(b.tensors.map(t => [t.name, t]));
    const tensors = { added: [], removed: [], type: [], shape: [], moved: 0 };
    for (const [n, t] of tb) {
      const o = ta.get(n);
      if (!o) { tensors.added.push(n); continue; }
      if (o.type !== t.type) tensors.type.push({ name: n, old: o.type, new: t.type });
      if (o.dims.join("x") !== t.dims.join("x")) tensors.shape.push({ name: n, old: o.dims.join("x"), new: t.dims.join("x") });
      if (o.off !== t.off) tensors.moved++;
    }
    for (const n of ta.keys()) if (!tb.has(n)) tensors.removed.push(n);
    const layoutSame = !tensors.added.length && !tensors.removed.length && !tensors.type.length && !tensors.shape.length && !tensors.moved;
    return { kv, tensors, layoutSame };
  }

  // same tensor layout: compare n ranges of 4 KiB of tensor data, spread over the tensors
  async function sameData(srcA, hA, srcB, hB, n = 12) {
    const ra = source(srcA), rb = source(srcB);
    const T = hA.tensors;
    const picks = [];
    for (let i = 0; i < n; i++) {
      const t = T[Math.floor((i + 0.5) * T.length / n)];
      picks.push({ name: t.name, off: t.off });
    }
    const out = [];
    for (const p of picks) {
      const [x, y] = await Promise.all([ra(hA.dataStart + p.off, hA.dataStart + p.off + 4096), rb(hB.dataStart + p.off, hB.dataStart + p.off + 4096)]);
      let same = x.length === y.length;
      for (let i = 0; same && i < x.length; i++) if (x[i] !== y[i]) same = false;
      out.push({ name: p.name, same });
    }
    return out;
  }

  async function info(repo, rev, path) {
    const r = await fetch(HF + "/api/models/" + repo + "/paths-info/" + encodeURIComponent(rev), {
      method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "paths=" + encodeURIComponent(path) + "&expand=true" });
    if (!r.ok) throw new Error("HTTP " + r.status + " for paths-info " + repo + "@" + rev);
    const j = await r.json();
    return j.find(x => x.path === path) || null;
  }
  // commits on main, oldest last; fetched page by page as needed
  function commitList(repo) {
    const list = []; let next = HF + "/api/models/" + repo + "/commits/main?limit=100", done = false;
    return {
      async parentOf(id) {
        for (;;) {
          const i = list.findIndex(c => c.id === id);
          if (i >= 0 && i + 1 < list.length) return list[i + 1];
          if (i >= 0 && done) return null;
          if (done) return null;
          const r = await fetch(next);
          if (!r.ok) throw new Error("HTTP " + r.status + " for commits of " + repo);
          list.push(...await r.json());
          const m = /<([^>]+)>;\s*rel="next"/.exec(r.headers.get("link") || "");
          if (m) next = m[1]; else done = true;
        }
      }, list };
  }
  async function versions(repo, path, max = 40) {
    const out = [];
    let cur = await info(repo, "main", path);
    if (!cur) throw new Error(path + " is not in " + repo + " (main)");
    const cl = commitList(repo);
    while (cur && out.length < max) {
      const lc = cur.lastCommit;
      out.push({ commit: lc.id, date: lc.date, title: lc.title, sha256: cur.lfs ? cur.lfs.oid : null, size: cur.size });
      const parent = await cl.parentOf(lc.id);
      if (!parent) break;
      cur = await info(repo, parent.id, path);
    }
    return out;
  }
  async function ollamaDigest(repo, tag) {
    const r = await fetch(HF + "/v2/" + repo + "/manifests/" + encodeURIComponent(tag), { headers: { Accept: "application/vnd.docker.distribution.manifest.v2+json" } });
    if (!r.ok) return null;
    const j = await r.json();
    const l = (j.layers || []).find(x => x.mediaType === "application/vnd.ollama.image.model");
    return l ? { digest: l.digest.replace(/^sha256:/, ""), size: l.size } : null;
  }
  window.GH = { header, diff, sameData, versions, info, fileUrl, ollamaDigest, sha256hex };
})();
