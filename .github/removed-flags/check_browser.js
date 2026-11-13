const { chromium } = require(process.env.PW || "playwright");
const URL = process.argv[2];
const cases = [
  ["serve old", "VLLM_ATTENTION_BACKEND=FLASHINFER vllm serve Qwen/Qwen3-8B --task generate --disable-log-requests --guided-decoding-backend xgrammar --max_model_len 8192", "auto", "", ["--task", "--runner pooling", "VLLM_ATTENTION_BACKEND", "--attention-backend", "--max_model_len", "Current in v0.33.0", "4 of 5 names will not work"]],
  ["old version ok", "vllm serve m --speculative-model x --num-speculative-tokens 5", "auto", "0.6.3", ["Still there in your 0.6.3", "All 2 names are valid"]],
  ["too new", "vllm serve m --speculative-config '{}'", "auto", "0.7.3", ["Added in v0.8.2", "1 of 1"]],
  ["negated", "vllm serve m --no-enable-chunked-prefill", "auto", "", ["negated form of --enable-chunked-prefill"]],
  ["dotted", "vllm serve m --compilation-config.level 3", "auto", "", ["Read as --compilation-config"]],
  ["request json", '{"model":"m","messages":[],"guided_json":{"type":"object"},"best_of":2,"top_k":5}', "auto", "", ["guided_json", "structured_outputs", "No error", "best_of", "top_k", "2 of 3"]],
  ["ignored log", "WARNING The following fields were present in the request but ignored: {'guided_regex'}", "auto", "", ["guided_regex", "Removed after v0.11.2"]],
  ["sampling", "SamplingParams(temperature=0.7, use_beam_search=True, best_of=4)", "auto", "", ["SamplingParams argument", "BeamSearchParams", "TypeError"]],
  ["typeerror", "TypeError: SamplingParams.__init__() got an unexpected keyword argument 'guided_decoding'", "auto", "", ["StructuredOutputsParams"]],
  ["sglang", "python -m sglang.launch_server --model-path m --enable-ep-moe --cuda-graph-max-bs 64 --tp-size 2", "auto", "", ["--ep-size", "--cuda-graph-max-bs-decode", "SGLang argument"]],
  ["typo", "vllm serve m --max-model-lenght 4096", "vllm", "", ["Not a name in any vLLM release"]],
  ["vllm flag on sglang", "python -m sglang.launch_server --gpu-memory-utilization 0.9", "auto", "", ["It is a vLLM argument"]],
  ["env silent", "export VLLM_USE_V1=0", "auto", "", ["No error", "Unknown vLLM environment variable detected"]],
  ["nothing", "hello", "auto", "", ["Found no"]],
];
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome" });
  const errs = []; let fail = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(URL, { waitUntil: "networkidle" });
    for (const [name, q, eng, v, want] of cases) {
      await p.fill("#q", q); await p.selectOption("#eng", eng); await p.fill("#v", v); await p.click("#go");
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x));
      if (miss.length) { fail++; console.log("FAIL", w, name, miss, "|", t.slice(0, 600)); }
    }
    const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (over > 0) { fail++; console.log("FAIL overflow", w, over); }
    await p.fill("#filter", "guided");
    const vis = await p.evaluate(() => [...document.querySelectorAll("table.full tbody tr")].filter(r => r.style.display !== "none").length);
    if (!(vis >= 5 && vis < 40)) { fail++; console.log("FAIL filter", vis); }
    const p2 = await b.newPage({ viewport: { width: w, height: 900 } });
    await p2.goto(URL + "?q=" + encodeURIComponent("vllm serve m --task embed") + "&v=0.12.0#lookup", { waitUntil: "networkidle" });
    const t2 = await p2.textContent("#res"); if (!t2.includes("Still there in your 0.12.0")) { fail++; console.log("FAIL url", t2.slice(0, 200)); }
  }
  if (errs.length) { fail++; console.log("errors", errs); }
  await b.close(); console.log(fail ? fail + " FAIL" : "ALL PASS"); process.exit(fail ? 1 : 0);
})();
