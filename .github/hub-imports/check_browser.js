// Usage: node check_browser.js <base url>   (serve a directory that has en/huggingface-hub-import-name-version-lookup/)
// Expected strings were written by hand from the release ranges and the deprecation messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/huggingface-hub-import-name-version-lookup/";
const LATEST = process.env.LATEST_RELEASE || "2.4.0";
const cases = [
  ["cached_download error", "ImportError: cannot import name 'cached_download' from 'huggingface_hub' (/usr/local/lib/python3.10/site-packages/huggingface_hub/__init__.py)", "",
    ["through 0.25.2; gone in 0.26.0 (2024-10-18)", "hf_hub_download", 'pip install "huggingface_hub<0.26.0"', "diffusers 0.1.0 to 0.28.x (no longer from 0.29.0", "sentence-transformers 2.0.0 to 2.2.x (no longer from 2.3.0"], ["never there", "site"]],
  ["old app on 1.0.0", "from huggingface_hub import HfFolder, Repository, hf_hub_url, cached_download", "1.0.0",
    ["through 0.36.2; gone in 1.0.0", "login()", "HfApi", "gradio 4.9.0 to 5.7.x (no longer from 5.8.0", "datasets 1.13.0 to 2.15.x (no longer from 2.16.0", "Your 1.0.0: does not have it.", "Your 1.0.0: has it."], []],
  ["same app on 0.25.2", "from huggingface_hub import HfFolder, Repository, hf_hub_url, cached_download", "0.25.2", ["Your 0.25.2: has it."], ["does not have it"]],
  ["utils, hub too old", "cannot import name 'OfflineModeIsEnabled' from 'huggingface_hub.utils'", "0.19.4", ["huggingface_hub.utils", "from 0.20.0", "Your 0.19.4: does not have it.", 'pip install "huggingface_hub>=0.20.0"'], ["gone"]],
  ["pinned too low", "cannot import name 'DDUFEntry' from 'huggingface_hub'", "0.25.2", ["from 0.27.0", "Your 0.25.2: does not have it."], ["gone"]],
  ["ModelFilter", "ModelFilter", "", ["gone in 0.24.0", "list_models"], []],
  ["errors module", "from huggingface_hub.errors import EntryNotFoundError", "0.24.7", ["huggingface_hub.errors", "from 0.25.0", "does not have it"], []],
  ["typo", "cannot import name 'hub_hub_download' from 'huggingface_hub'", "", ["never there", "Close names"], ["Instead"]],
  ["never a name", "from huggingface_hub import FooBarBazQux", "", ["never there"], []],
  ["submodule not covered", "cannot import name 'HF_HUB_CACHE' from 'huggingface_hub.constants'", "", ["not covered"], []],
  ["markup is text", "<img src=x onerror=alert(1)> cannot import name 'cached_download' from 'huggingface_hub'", "", ["gone in 0.26.0"], []],
  ["nothing", "???", "", ["Found no name"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.TF_DATA);
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      latest: window.TF_DATA.latest, over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 3 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0 || st.latest !== LATEST) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, v, want, not] of cases) {
      n++;
      await p.fill("#q", q); await p.fill("#v", v); await p.click("#go");
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      const img = await p.evaluate(() => document.querySelectorAll("#res img").length);
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (miss.length || extra.length || img || over > 0) { fail++; console.log("FAIL", w, name, { miss, extra, img, over }, "|", t.slice(0, 800)); }
    }
    for (const ex of await p.$$("[data-ex]")) {
      await ex.click();
      const t = await p.evaluate(() => document.getElementById("res").innerText);
      if (!/through|from /.test(t)) { fail++; console.log("FAIL example button", w, t.slice(0, 200)); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=cached_download&v=0.26.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").innerText.length > 0);
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your 0.26.0: does not have it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
