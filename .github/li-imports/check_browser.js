// Usage: node check_browser.js <base url>   (serve the site root, which has en/llama-index-import-name-version-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/llama-index-import-name-version-lookup/";
// Expected strings were written by hand from anchors.py (plain-text search of the wheels) and the release notes, not from tool.js.
const cases = [
  ["VSI old", "ImportError: cannot import name 'VectorStoreIndex' from 'llama_index' (unknown location)", "0.10.12",
    ["gone in 0.10.0", "from llama_index.core import VectorStoreIndex", "Your llama_index 0.10.12: does not have it."], ["never there"]],
  ["VSI old ok", "from llama_index import VectorStoreIndex", "0.9.48", ["Your llama_index 0.9.48: has it."], []],
  ["OpenAI", "from llama_index.llms import OpenAI", "0.10.30", ["gone in 0.10.0", "pip install llama-index-llms-openai", "from llama_index.llms.openai import OpenAI"], ["never there"]],
  ["core VSI", "from llama_index.core import VectorStoreIndex", "0.10.0", ["Your llama_index 0.10.0: has it."], []],
  ["Settings", "from llama_index.core import Settings", "0.10.0", ["from 0.10.1", "Your llama_index 0.10.0: does not have it."], []],
  ["ServiceContext", "from llama_index import ServiceContext", "", ["gone in 0.10.0", "Settings"], []],
  ["AgentRunner", "from llama_index.core.agent import AgentRunner", "0.13.0", ["gone in 0.13.0", "Your llama_index 0.13.0: does not have it.", "FunctionAgent"], []],
  ["FunctionAgent", "from llama_index.core.agent.workflow import FunctionAgent", "0.12.11", ["from 0.12.12", "Your llama_index 0.12.11: does not have it."], []],
  ["download_loader", "from llama_index.core import download_loader", "0.14.21", ["gone in 0.14.21", "Your llama_index 0.14.21: does not have it."], []],
  ["no module", "ModuleNotFoundError: No module named 'llama_index.core.query_pipeline'", "", ["module", "gone in 0.13.0"], []],
  ["nothing", "FooBarBazQux", "", ["never there"], []],
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from llama_index.core import Settings") + "&v=0.10.1", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your llama_index 0.10.1: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
