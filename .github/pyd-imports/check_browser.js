// Usage: node check_browser.js <base url>   (serve the site root, which has en/pydantic-import-name-version-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/pydantic-import-name-version-lookup/";
// Expected strings were written by hand from anchors.py (text search at the tags) and the messages of pydantic/_migration.py, not from tool.js.
const cases = [
  ["BaseSettings", "ImportError: cannot import name 'BaseSettings' from 'pydantic' (/usr/lib/python3/site-packages/pydantic/__init__.py)", "2.10.0",
    ["gone in 2.0", "pydantic-settings", "from pydantic_settings import BaseSettings", "Your pydantic 2.10.0: does not have it."], ["never there", "site-packages"]],
  ["BaseSettings old", "from pydantic import BaseSettings", "1.10.0", ["Your pydantic 1.10.0: has it."], []],
  ["Required", "pydantic.errors.PydanticImportError: `pydantic:Required` has been removed in V2.", "", ["gone in 2.0", "has been removed in V2", "from pydantic.v1 import Required"], []],
  ["ModelMetaclass", "from pydantic.main import ModelMetaclass", "2.5.0", ["gone in 2.0", "_model_construction", "Your pydantic 2.5.0: does not have it."], []],
  ["field_validator", "from pydantic import field_validator", "1.10.0", ["from 2.0", "Your pydantic 1.10.0: does not have it."], []],
  ["validator", "from pydantic import validator", "2.14.4", ["Your pydantic 2.14.4: has it."], []],
  ["deep_update", "from pydantic.utils import deep_update", "2.5.0", ["Your pydantic 2.5.0: has it."], []],
  ["GenericModel", "from pydantic.generics import GenericModel", "2.0", ["Your pydantic 2.0: does not have it."], []],
  ["with_config", "from pydantic import with_config", "2.6.0", ["from 2.7.0", "Your pydantic 2.6.0: does not have it."], []],
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from pydantic import BaseSettings") + "&v=1.10.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your pydantic 1.10.0: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
