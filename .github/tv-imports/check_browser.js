// Usage: node check_browser.js <base url>   (serve the site root, which has en/torchvision-import-name-version-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/torchvision-import-name-version-lookup/";
// Expected strings were written by hand from anchors.py (plain-text search of the wheels) and the deprecation messages, not from tool.js.
const cases = [
  ["ft module", "ModuleNotFoundError: No module named 'torchvision.transforms.functional_tensor'", "0.17.1", ["module", "gone in 0.17.0"], ["never there"]],
  ["ft name", "from torchvision.transforms.functional_tensor import rgb_to_grayscale", "0.16.2",
    ["gone in 0.17.0", "from torchvision.transforms.functional import rgb_to_grayscale", "Your torchvision 0.16.2: has it."], ["never there"]],
  ["ft new", "from torchvision.transforms.functional_tensor import rgb_to_grayscale", "0.17.0", ["Your torchvision 0.17.0: does not have it."], []],
  ["read_video", "ImportError: cannot import name 'read_video' from 'torchvision.io'", "0.26.0", ["gone in 0.26.0", "torchcodec", "Your torchvision 0.26.0: does not have it."], []],
  ["VideoReader new", "from torchvision.io import VideoReader", "0.28.0", ["gone in 0.26.0", "Your torchvision 0.28.0: does not have it."], []],
  ["read_image", "from torchvision.io import read_image", "0.29.2", ["Your torchvision 0.29.2: has it."], []],
  ["models.utils", "from torchvision.models.utils import load_state_dict_from_url", "", ["torch.hub"], []],
  ["datapoints", "from torchvision.datapoints import BoundingBox", "", ["gone in 0.16.0"], []],
  ["weights", "from torchvision.models import ResNet50_Weights", "0.12.0", ["from 0.13.0", "Your torchvision 0.12.0: does not have it."], []],
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
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from torchvision.transforms.functional_tensor import rgb_to_grayscale") + "&v=0.16.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your torchvision 0.16.0: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
