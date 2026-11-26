// Survey for en/gguf-redownload-check/: run in a browser console on any https page that can reach huggingface.co
// (we ran it on erimaki-kobo.github.io), after evaluating ggufhist.js. Writes window.__S3; copy
// JSON.stringify(summary()) into survey.json for build_page.py.
// 1) the 40 most downloaded GGUF repositories (one file each: Q4_K_M where there is one), 2) EXTRA older repositories.
const EXTRA = ['bartowski/Meta-Llama-3.1-8B-Instruct-GGUF', 'lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF', 'unsloth/gemma-3-12b-it-GGUF', 'Qwen/Qwen2.5-7B-Instruct-GGUF', 'TheBloke/Mistral-7B-Instruct-v0.2-GGUF', 'unsloth/Qwen3-30B-A3B-GGUF', 'unsloth/Qwen3-8B-GGUF', 'unsloth/gpt-oss-20b-GGUF', 'unsloth/DeepSeek-R1-Distill-Qwen-7B-GGUF', 'bartowski/google_gemma-3-12b-it-GGUF', 'ggml-org/gpt-oss-20b-GGUF', 'unsloth/Llama-3.2-3B-Instruct-GGUF', 'bartowski/Qwen2.5-Coder-7B-Instruct-GGUF', 'unsloth/phi-4-GGUF', 'unsloth/Qwen3.5-4B-GGUF', 'unsloth/GLM-4.7-Flash-GGUF', 'unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF'];
async function pickFile(id) {
  const m = await fetch('https://huggingface.co/api/models/' + id).then(r => r.json());
  const files = (m.siblings || []).map(s => s.rfilename).filter(f => f.endsWith('.gguf') && !/mmproj/i.test(f));
  return files.find(f => /Q4_K_M/.test(f) && !/-0000[2-9]-of-/.test(f)) || files.find(f => /Q4/.test(f) && !/-0000[2-9]-of-/.test(f)) || files[0] || null;
}
async function surveyOne(id, top) {
  const pick = await pickFile(id);
  if (!pick) return null;
  const v = await GH.versions(id, pick, 10);
  const rec = { id, top, file: pick, versions: v.map(x => ({ c: x.commit.slice(0, 8), d: x.date.slice(0, 10), sha: (x.sha256 || '').slice(0, 12), size: x.size })), steps: [] };
  const H = {};
  const hdr = async c => H[c] || (H[c] = await GH.header(GH.fileUrl(id, c, pick)));
  for (let i = 0; i < v.length - 1; i++) {
    const a = await hdr(v[i + 1].commit), b = await hdr(v[i].commit);
    const d = GH.diff(a, b);
    const r = d.layoutSame ? await GH.sameData(GH.fileUrl(id, v[i + 1].commit, pick), a, GH.fileUrl(id, v[i].commit, pick), b, 16) : null;
    const n = r ? r.length : 0, same = r ? r.filter(x => x.same).length : null;
    rec.steps.push({ to: v[i].commit.slice(0, 8), date: v[i].date.slice(0, 10), kind: !d.layoutSame ? 'tensors' : same < n ? 'weights' : d.kv.length ? 'metadata' : 'none',
      keys: d.kv.map(k => k.key), pre: d.kv.filter(k => k.key === 'tokenizer.ggml.pre').map(k => k.old + '>' + k.new)[0] || null,
      t: [d.tensors.added.length, d.tensors.removed.length, d.tensors.type.length, d.tensors.shape.length, d.tensors.moved], added: d.tensors.added.slice(0, 3), n, same,
      differ: r ? r.filter(x => !x.same).map(x => x.name).slice(0, 4) : [] });
    delete H[v[i].commit];
  }
  return rec;
}
async function survey(workers = 5) {
  const top = (await fetch('https://huggingface.co/api/models?filter=gguf&sort=downloads&direction=-1&limit=40').then(r => r.json())).map(m => m.id);
  const jobs = top.map(id => [id, true]).concat(EXTRA.filter(id => !top.includes(id)).map(id => [id, false]));
  const S = window.__S3 = { done: [], err: [], top: top.length };
  let k = 0;
  const w = async () => { while (k < jobs.length) { const [id, t] = jobs[k++]; try { const r = await surveyOne(id, t); if (r) S.done.push(r); } catch (e) { S.err.push(id + ': ' + e); } } };
  await Promise.all(Array.from({ length: workers }, w));
  return S;
}
function summary() {
  const S = window.__S3;
  return { run_date: new Date().toISOString().slice(0, 10), top_checked: S.top, single: S.done.filter(r => r.top && !r.steps.length).map(r => r.id),
    repos: S.done.filter(r => r.steps.length).map(r => ({ id: r.id, top: r.top, file: r.file, versions: r.versions.map(v => v.d), steps: r.steps.map(s => ({ date: s.date, kind: s.kind, keys: s.keys, pre: s.pre, t: s.t, added: s.added, n: s.n, same: s.same })) })) };
}
