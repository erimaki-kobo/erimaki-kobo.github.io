// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/timm-import-name-version-lookup/";
const cases = [
  ["norm", "ModuleNotFoundError: No module named 'timm.models.layers.norm'", "", ["(every tagged release)", "module", "0.4.9", "gone in 0.9.0 (2023-05-12)", "timm.layers.norm", 'pip install "timm>=0.4.9,<0.9.0"'], ["never there"]],
  ["layers old", "ModuleNotFoundError: No module named 'timm.layers'", "0.6.13", ["from 0.9.0", "Your timm 0.6.13: does not have it."], []],
  ["mapping", "from timm.models.layers import DropPath, use_fused_attn", "1.0.31", ["DropPath", "from 0.2.1", "Your timm 1.0.31: has it.", "never there", "timm.layers"], []],
  ["blocks", "from timm.models.efficientnet_blocks import SqueezeExcite", "", ["gone in 0.9.0", "timm.models._efficientnet_blocks"], []],
  ["resample", "ImportError: cannot import name 'resample_abs_pos_embed' from 'timm.layers'", "0.9.0", ["from 0.9.0", "Your timm 0.9.0: has it."], []],
  ["helpers path", "from timm.models.helpers import build_model_with_cfg", "", ["from 0.2.1"], ["gone"]],
  ["top", "from timm import create_model", "0.1.1", ["from 0.1.1", "Your timm 0.1.1: has it."], []],
  ["typo", "from timm.layers import DropPth", "", ["never there", "DropPath"], []],
  ["no module", "from timm.foo import Bar", "", ["no such module"], []],
  ["nothing", "FooBarBazQux", "", ["never there", "No release of timm"], []],
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("No module named 'timm.models.layers.norm'") + "&v=0.6.13", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your timm 0.6.13: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
