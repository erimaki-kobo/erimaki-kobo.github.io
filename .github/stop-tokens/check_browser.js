// node check_browser.js URL TEMPLATE_DIR
const { chromium } = require(process.env.PW || "playwright");
const fs = require("fs");
const URL = process.argv[2], TD = process.argv[3];
const atd = (m) => Object.fromEntries(Object.entries(m).map(([k, v]) => [k, { content: v, special: true }]));
const L31 = fs.readFileSync(TD + "/meta-llama-Llama-3.1-8B-Instruct.jinja", "utf8");
const Q3 = fs.readFileSync(TD + "/Qwen-Qwen3-0.6B.jinja", "utf8");
const G4 = fs.readFileSync(TD + "/google-gemma-4-31B-it.jinja", "utf8");
const OSS = fs.readFileSync(TD + "/openai-gpt-oss-120b.jinja", "utf8");
const l3tok = { eos_token: "<|end_of_text|>", bos_token: "<|begin_of_text|>", chat_template: L31, added_tokens_decoder: atd({ 128000: "<|begin_of_text|>", 128001: "<|end_of_text|>", 128006: "<|start_header_id|>", 128007: "<|end_header_id|>", 128008: "<|eom_id|>", 128009: "<|eot_id|>" }) };
const qtok = { eos_token: "<|im_end|>", chat_template: Q3, added_tokens_decoder: atd({ 151643: "<|endoftext|>", 151644: "<|im_start|>", 151645: "<|im_end|>", 151662: "<|fim_pad|>", 151663: "<|repo_name|>", 151664: "<|file_sep|>" }) };
const cases = [
  ["llama3.1 full", { cfg: { eos_token_id: [128001, 128008, 128009] }, gen: { eos_token_id: [128001, 128008, 128009] }, tok: l3tok }, ["ends a turn with <|eot_id|>", "Transformers generate()stops", "vLLMstops", "llama.cppstops"]],
  ["llama3 no gen", { cfg: { eos_token_id: 128001 }, gen: null, tok: l3tok }, ["Transformers generate()does not stop", "vLLMdoes not stop", "stop_token_ids\": [128009]", "llama.cppstops"]],
  ["llama3 old build", { cfg: { eos_token_id: 128001 }, gen: null, tok: l3tok, lb: "b2000" }, ["llama.cppdoes not stop", "before b2702"]],
  ["qwen3 base eos", { cfg: { eos_token_id: 151643 }, gen: { eos_token_id: 151643 }, tok: Object.assign({}, qtok, { eos_token: "<|endoftext|>" }) }, ["<|im_end|>", "vLLMdoes not stop", "SGLangdoes not stop", "llama.cppstops", "--extra-eos-token"]],
  ["ollama modelfile + log", { cfg: { eos_token_id: 151643 }, gen: null, tok: Object.assign({}, qtok, { eos_token: "<|endoftext|>" }), log: "load: printing all EOG tokens:\nload:   - 151643 ('<|endoftext|>')\n", mf: 'FROM x\nPARAMETER stop "<|im_end|>"' }, ["llama.cppdoes not stop", "your llama.cpp load log", "stops (stop string)", "--override-kv tokenizer.ggml.eos_token_id=int:151645"]],
  ["gemma4 template", { cfg: { text_config: { eos_token_id: 106 } }, gen: { eos_token_id: [1, 106] }, tok: { eos_token: "<eos>", bos_token: "<bos>", chat_template: G4, added_tokens_decoder: atd({ 1: "<eos>", 2: "<bos>", 106: "<turn|>", 105: "<|turn>" }) } }, ["<turn|>", "vLLMstops", "llama.cppstops"]],
  ["gemma4 old ollama", { cfg: {}, gen: { eos_token_id: [1] }, tok: { eos_token: "<eos>", bos_token: "<bos>", chat_template: G4, added_tokens_decoder: atd({ 1: "<eos>", 2: "<bos>", 106: "<turn|>", 105: "<|turn>" }) }, ov: "0.24.0" }, ["Ollamadoes not stop", "bundles b7437"]],
  ["gpt-oss", { cfg: { eos_token_id: 200002 }, gen: { eos_token_id: [200002, 199999, 200012] }, tok: { eos_token: "<|return|>", chat_template: OSS, added_tokens_decoder: atd({ 199998: "<|startoftext|>", 199999: "<|endoftext|>", 200002: "<|return|>", 200005: "<|channel|>", 200006: "<|start|>", 200007: "<|end|>", 200008: "<|message|>", 200012: "<|call|>" }) } }, ["<|return|>", "vLLMstops", "llama.cppstops", "<|end|> removed"]],
  ["manual marker", { cfg: { eos_token_id: 5 }, gen: null, tok: { eos_token: "</s>", added_tokens_decoder: atd({ 5: "</s>", 9: "<|message_sep|>" }) }, mk: "<|message_sep|>" }, ["ends a turn with <|message_sep|>", "llama.cppdoes not stop"]],
  ["empty", { cfg: null, gen: null, tok: null }, ["Paste at least"]],
];
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome" });
  const errs = []; let fail = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(URL, { waitUntil: "networkidle" }); await p.waitForTimeout(400);
    for (const [name, c, want] of cases) {
      const s = (v) => v ? JSON.stringify(v) : "";
      await p.fill("#cfg", s(c.cfg)); await p.fill("#gen", s(c.gen)); await p.fill("#tok", s(c.tok)); await p.fill("#tmpl", "");
      await p.fill("#log", c.log || ""); await p.fill("#mf", c.mf || ""); await p.fill("#lb", c.lb || ""); await p.fill("#ov", c.ov || ""); await p.fill("#marker", c.mk || "");
      await p.click("#go");
      const t = ((await p.textContent("#res")) + " " + (await p.textContent("#status"))).replace(/\s+/g, " ").replace(/> (\w)/g, ">$1");
      const tt = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\t/g, "").replace(/\s+/g, " ");
      const miss = want.filter(x => !tt.includes(x) && !t.includes(x));
      if (miss.length) { fail++; console.log("FAIL", w, name, miss, "|", tt.slice(0, 500)); }
    }
    const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (over > 0) { fail++; console.log("FAIL overflow", w, over); }
  }
  if (errs.length) { fail++; console.log("errors", errs); }
  await b.close(); console.log(fail ? fail + " FAIL" : "ALL PASS"); process.exit(fail ? 1 : 0);
})();
