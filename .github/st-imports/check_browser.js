// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/sentence-transformers-import-name-version-lookup/";
const cases = [
  ["bert", "ImportError: cannot import name 'BERT' from 'sentence_transformers.models'", "2.2.2", ["gone in 2.0.0 (2021-06-24)", "models.Transformer", "Your sentence_transformers 2.2.2: does not have it.", 'pip install "sentence-transformers<2.0.0"'], []],
  ["snapshot", "from sentence_transformers.util import snapshot_download", "5.1.0", ["gone in 5.1.0", "huggingface_hub", "Your sentence_transformers 5.1.0: does not have it."], []],
  ["sparse", "from sentence_transformers import SparseEncoder", "4.1.0", ["from 5.0.0", "Your sentence_transformers 4.1.0: does not have it."], []],
  ["old path ok", "from sentence_transformers.models import Transformer, Pooling", "6.3.0", ["Transformer", "Pooling", "Your sentence_transformers 6.3.0: has it."], ["gone", "never there"]],
  ["old module ok", "No module named 'sentence_transformers.losses'", "6.3.0", ["module", "Your sentence_transformers 6.3.0: has it."], ["gone"]],
  ["cached", "cannot import name 'cached_download' from 'sentence_transformers.util'", "", ["gone in 2.3.0"], []],
  ["new path", "from sentence_transformers.sentence_transformer.modules import Pooling", "5.3.0", ["from 5.4.0", "Your sentence_transformers 5.3.0: does not have it."], []],
  ["typo", "from sentence_transformers import SentenceTransfomer", "", ["never there", "SentenceTransformer"], []],
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
    if (st.h1 !== 1 || st.tables !== 3 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from sentence_transformers.models import BERT") + "&v=1.2.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your sentence_transformers 1.2.0: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
