// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/datasets-import-name-version-lookup/";
const cases = [
  ["load_metric", "ImportError: cannot import name 'load_metric' from 'datasets' (/usr/local/lib/python3.10/site-packages/datasets/__init__.py)", "3.0.1",
    ["gone in 3.0.0 (2024-09-11)", "through 2.21.0", 'pip install "datasets<3.0.0"', "evaluate.load", "Your datasets 3.0.1: does not have it."], ["site-packages", "never there"]],
  ["old enough", "from datasets import load_metric", "2.21.0", ["Your datasets 2.21.0: has it."], []],
  ["list_datasets", "from datasets import list_datasets, set_caching_enabled", "", ["huggingface_hub.list_datasets", "disable_caching", "gone in 3.0.0"], []],
  ["tasks module", "from datasets.tasks import TextClassification", "", ["gone in 3.0.0"], ["never there"]],
  ["arrow_writer", "ImportError: cannot import name 'SchemaInferenceError' from 'datasets.arrow_writer'", "2.6.1", ["from 2.7.0", "Your datasets 2.6.1: does not have it."], []],
  ["List", "from datasets import List", "3.6.0", ["from 4.0.0", "Your datasets 3.6.0: does not have it."], []],
  ["asdict", "cannot import name 'asdict' from 'datasets.utils.py_utils'", "", ["from 2.4.0"], ["never there"]],
  ["no module", "ModuleNotFoundError: No module named 'datasets.tasks'", "", ["module", "gone in 3.0.0"], []],
  ["typo", "cannot import name 'load_datset' from 'datasets'", "", ["never there", "load_dataset"], []],
  ["bare", "load_metric", "", ["gone in 3.0.0"], []],
  ["nothing", "FooBarBazQux", "", ["never there", "No release of datasets"], []],
  ["markup", "<img src=x onerror=alert(1)> cannot import name 'load_dataset' from 'datasets'", "", ["from 1.0.0"], []],
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from datasets import load_metric") + "&v=2.20.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your datasets 2.20.0: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
