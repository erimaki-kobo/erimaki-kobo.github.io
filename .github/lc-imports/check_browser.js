// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/langchain-import-name-version-lookup/";
const cases = [
  ["llmchain", "ImportError: cannot import name 'LLMChain' from 'langchain.chains' (/usr/lib/python3/site-packages/langchain/chains/__init__.py)", "1.0.0",
    ["gone in 1.0.0 (2025-10-17)", "0.1.0 or earlier", 'pip install "langchain<1.0.0"', "from langchain_classic.chains import LLMChain", "pip install langchain-classic", "Your langchain 1.0.0: does not have it."], ["site-packages"]],
  ["schema module", "ModuleNotFoundError: No module named 'langchain.schema'", "", ["module", "gone in 1.0.0"], ["never there"]],
  ["chatopenai", "from langchain.chat_models import ChatOpenAI", "1.5.0", ["gone in 1.0.0", "langchain_community.chat_models", "langchain-community", "langchain_openai"], []],
  ["memory", "from langchain.memory import ConversationBufferMemory", "", ["gone in 1.0.0", "langchain_classic.memory"], []],
  ["classic loader", "from langchain_classic.document_loaders import PyPDFLoader", "", ["from 1.0.0", "langchain_community.document_loaders"], ["never there"]],
  ["core content", "ImportError: cannot import name 'content' from 'langchain_core.messages'", "0.3.79", ["from 1.0.0", "Your langchain_core 0.3.79: does not have it."], []],
  ["create_agent", "from langchain.agents import create_agent", "0.3.27", ["from 1.0.0", "Your langchain 0.3.27: does not have it."], []],
  ["core memory", "No module named 'langchain_core.memory'", "", ["module", "gone in 1.0.0", "0.1.47 or earlier"], []],
  ["pydantic_v1", "from langchain_core.pydantic_v1 import BaseModel", "", ["not listed", "pydantic"], ["never there"]],
  ["messages new", "from langchain.messages import HumanMessage", "", ["from 1.0.0"], []],
  ["bare", "RecursiveCharacterTextSplitter", "", ["langchain_classic", "text_splitter"], []],
  ["typo", "from langchain.agents import create_agnt", "", ["never there", "create_agent"], []],
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
    if (st.h1 !== 1 || st.tables !== 2 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from langchain.chains import LLMChain") + "&v=0.3.27", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your langchain 0.3.27: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
