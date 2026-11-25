// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/gradio-import-name-version-lookup/";
// Expected strings were written by hand from anchors.py (the PyPI wheels) and the quoted deprecation messages, not from tool.js.
const cases = [
  ["inputs", "ImportError: cannot import name 'inputs' from 'gradio' (/usr/local/lib/python3.10/site-packages/gradio/__init__.py)", "4.44.1",
    ["gone in 4.0.0 (2023-10-31)", "through 3.50.2", 'pip install "gradio<4.0.0"', "gr.Textbox()", "Your gradio 4.44.1: does not have it."], ["site-packages", "never there"]],
  ["old enough", "from gradio import inputs", "3.50.2", ["Your gradio 3.50.2: has it."], []],
  ["IOComponent", "from gradio.components import IOComponent", "", ["gone in 4.0.0", "gradio.components.Component"], ["never there"]],
  ["ChatInterface old", "from gradio import ChatInterface", "3.36.1", ["from 3.37.0", "Your gradio 3.36.1: does not have it."], []],
  ["ChatMessage", "cannot import name 'ChatMessage' from 'gradio'", "4.37.2", ["from 4.38.0", "Your gradio 4.37.2: does not have it."], []],
  ["make_waveform", "ImportError: cannot import name 'make_waveform' from 'gradio'", "5.4.0", ["gone in 5.0.0", "through 4.44.1"], []],
  ["Variable", "from gradio import Variable", "", ["gone in 4.0.0", "gr.State()"], []],
  ["no module", "ModuleNotFoundError: No module named 'gradio.inputs'", "", ["module", "gone in 4.0.0"], []],
  ["typo", "cannot import name 'Textbx' from 'gradio'", "", ["never there", "Textbox"], []],
  ["nothing", "FooBarBazQux", "", ["never there", "No release of gradio"], []],
  ["markup", "<img src=x onerror=alert(1)> cannot import name 'Blocks' from 'gradio'", "", ["from 3.0.1"], []],
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from gradio import inputs") + "&v=3.50.2", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your gradio 3.50.2: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
