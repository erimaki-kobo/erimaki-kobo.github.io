// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/vllm-import-name-version-lookup/";
// Expected strings were written by hand from anchors.py (the PyPI wheels) and the TRL source, not from tool.js.
const cases = [
  ["GuidedDecodingParams", "ImportError: cannot import name 'GuidedDecodingParams' from 'vllm.sampling_params' (/usr/local/lib/python3.12/dist-packages/vllm/sampling_params.py)", "0.12.0",
    ["gone in 0.12.0 (2025-12-03)", "through 0.11.2", '<0.12.0"', "StructuredOutputsParams", "Your vllm 0.12.0: does not have it."], ["dist-packages", "never there"]],
  ["old enough", "from vllm.sampling_params import GuidedDecodingParams", "0.10.2", ["Your vllm 0.10.2: has it."], []],
  ["get_open_port", "from vllm.utils import get_open_port", "0.14.0", ["gone in 0.14.0", "network_utils", "Your vllm 0.14.0: does not have it."], []],
  ["get_open_port alias", "from vllm.utils import get_open_port", "0.13.0", ["Your vllm 0.13.0: has it."], []],
  ["protocol", "from vllm.entrypoints.openai.protocol import ChatCompletionRequest", "", ["gone in 0.15.0", "chat_completion.protocol"], ["never there"]],
  ["new home", "cannot import name 'ChatCompletionRequest' from 'vllm.entrypoints.openai.chat_completion.protocol'", "0.14.1", ["from 0.15.0", "Your vllm 0.14.1: does not have it."], []],
  ["no module", "ModuleNotFoundError: No module named 'vllm.model_executor.guided_decoding'", "", ["module", "gone in 0.11.0"], []],
  ["LLM", "from vllm import LLM, SamplingParams", "", ["from 0.1.0"], ["never there"]],
  ["typo", "cannot import name 'SamplingParam' from 'vllm'", "", ["never there", "SamplingParams"], []],
  ["nothing", "FooBarBazQux", "", ["never there", "No release of vllm"], []],
  ["markup", "<img src=x onerror=alert(1)> cannot import name 'LLM' from 'vllm'", "", ["from 0.1.0"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  const ask = async (p, q, v) => {
    const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
    await p.fill("#q", q); await p.fill("#v", v); await p.click("#go");
    await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
  };
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.PTA_READY);
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 1 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, v, want, not] of cases) {
      n++;
      await ask(p, q, v);
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      const img = await p.evaluate(() => document.querySelectorAll("#res img").length);
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (miss.length || extra.length || img || over > 0) { fail++; console.log("FAIL", w, name, { miss, extra, img, over }, "|", t.slice(0, 700)); }
    }
    for (const ex of await p.$$("[data-ex]")) {
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await ex.click();
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      if (!/through|from /.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from vllm.sampling_params import GuidedDecodingParams") + "&v=0.11.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your vllm 0.11.0: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
