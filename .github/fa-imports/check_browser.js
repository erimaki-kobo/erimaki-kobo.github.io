// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/flash-attn-import-name-version-lookup/";
// Expected strings were written by hand from anchors.py (plain-text search of the tags), not from tool.js.
const cases = [
  ["unpadded", "ImportError: cannot import name 'flash_attn_unpadded_func' from 'flash_attn.flash_attn_interface' (/usr/local/lib/python3.10/site-packages/flash_attn/flash_attn_interface.py)", "2.5.8",
    ["gone in 2.0.1", "through 1.0.9", "flash_attn_varlen_func", "Your flash_attn 2.5.8: does not have it."], ["site-packages", "never there"]],
  ["old enough", "from flash_attn.flash_attn_interface import flash_attn_unpadded_func", "1.0.9", ["Your flash_attn 1.0.9: has it."], []],
  ["FlashMHA", "from flash_attn.flash_attention import FlashMHA", "", ["gone in 2.0.1", "modules.mha.MHA"], ["never there"]],
  ["top func", "from flash_attn import flash_attn_func", "1.0.9", ["from 2.0.1", "Your flash_attn 1.0.9: does not have it."], []],
  ["kvcache", "from flash_attn import flash_attn_with_kvcache", "2.1.1", ["from 2.2.0", "Your flash_attn 2.1.1: does not have it."], []],
  ["no module", "ModuleNotFoundError: No module named 'flash_attn.flash_attention'", "", ["module", "gone in 2.0.1"], []],
  ["typo", "cannot import name 'flash_attn_funcc' from 'flash_attn'", "", ["never there", "flash_attn_func"], []],
  ["nothing", "FooBarBazQux", "", ["never there", "No release of flash_attn"], []],
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from flash_attn import flash_attn_func") + "&v=2.0.1", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your flash_attn 2.0.1: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
