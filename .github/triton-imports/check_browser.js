// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/triton-import-name-version-lookup/";
// Expected strings were written by hand from anchors.py (the git tags) and the bitsandbytes and PyTorch sources, not from tool.js.
const cases = [
  ["triton.ops", "ModuleNotFoundError: No module named 'triton.ops'", "3.2.0", ["module", "gone in 3.2.0 (2025-01-22)", "through 3.1.0"], ["never there"]],
  ["matmul_perf_model", "from triton.ops.matmul_perf_model import early_config_prune, estimate_matmul_time", "", ["gone in 3.2.0"], ["never there"]],
  ["libdevice", "ImportError: cannot import name 'libdevice' from 'triton.language.extra.cuda' (/usr/local/lib/python3.10/site-packages/triton/language/extra/cuda/__init__.py)", "2.3.1",
    ["from 3.0.0", "Your triton 2.3.1: does not have it."], ["site-packages", "never there"]],
  ["libdevice ok", "from triton.language.extra.cuda import libdevice", "3.0.0", ["Your triton 3.0.0: has it."], []],
  ["triton_key", "from triton.compiler.compiler import triton_key", "3.5.0", ["gone in 3.5.0", "through 3.4.0", "Your triton 3.5.0: does not have it."], []],
  ["old libdevice", "from triton.language import libdevice", "", ["gone in 2.1.0", "triton.language.math"], []],
  ["jit", "import triton; from triton import jit, Config, autotune", "", ["from 2.0.0"], ["never there"]],
  ["typo", "cannot import name 'autotunee' from 'triton'", "", ["never there", "autotune"], []],
  ["nothing", "FooBarBazQux", "", ["never there", "No release of triton"], []],
  ["markup", "<img src=x onerror=alert(1)> cannot import name 'jit' from 'triton'", "", ["from 2.0.0"], []],
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from triton.ops import matmul") + "&v=3.1.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your triton 3.1.0: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
