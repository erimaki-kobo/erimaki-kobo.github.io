import fs from "fs";
await import("./stopcheck.js");
const LL = JSON.parse(fs.readFileSync("out/llama_eog.json", "utf8"));
const R = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = [];
for (const [m, d] of Object.entries(R)) {
  const atd = Object.fromEntries(Object.entries(d.toks).map(([t, i]) => [String(i), { content: t }]));
  const tab = StopCheck.table({ added_tokens_decoder: atd }, null);
  const after = d.after.replace(/^\s+/, "");
  let mk = null; for (const t of tab.byText.keys()) if (after.startsWith(t) && (!mk || t.length > mk.length)) mk = t;
  const cfg = {}; if (d.ce !== null) cfg.eos_token_id = d.ce; if (d.te !== null) cfg.text_config = { eos_token_id: d.te };
  const gen = d.ge === null ? null : (d.ge === "none" ? {} : { eos_token_id: d.ge });
  const r = StopCheck.analyze({ config: cfg, gen, tok: { eos_token: d.eos, added_tokens_decoder: atd }, marker: mk || "" }, LL, null);
  const v = {}; for (const k of ["transformers", "vllm", "sglang", "llamacpp", "ollama", "mlx"]) v[k] = mk ? r.engines[k].verdict : "no-marker";
  out.push({ model: m, marker: mk, gen: gen === null ? "missing" : "present", v });
}
console.log(JSON.stringify(out, null, 0));
