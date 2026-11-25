// Usage: node check_browser.js <base url>   (serve the site root, which has en/scipy-removed-name-lookup/)
// Expected strings were written by hand from the probe results and SciPy's messages, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/scipy-removed-name-lookup/";
const cases = [
  ["triu", "ImportError: cannot import name 'triu' from 'scipy.linalg' (/usr/lib/python3/dist-packages/scipy/linalg/__init__.py)", ["scipy.linalg.triu", "Removed in SciPy 1.13.0", "numpy", "1.3.3 to 1.12.0", "scipy<1.13.0"], ["dist-packages"]],
  ["simps", "ImportError: cannot import name 'simps' from 'scipy.integrate'", ["Removed in SciPy 1.14.0", "simpson"], []],
  ["A", "AttributeError: 'csr_matrix' object has no attribute 'A'", ["scipy.sparse.csr_matrix.A", ".toarray()"], []],
  ["imread", "from scipy.misc import imread, imresize", ["scipy.misc.imread", "Removed in SciPy 1.3.0", "imageio.imread", "scipy.misc.imresize", "Read from the source"], []],
  ["interp", "AttributeError: module 'scipy' has no attribute 'interp'", ["scipy.interp", "Removed in SciPy 1.12.0", "numpy.interp"], []],
  ["hann", "from scipy.signal import hann", ["Removed in SciPy 1.13.0", "scipy.signal.windows"], []],
  ["alive", "from scipy.special import comb", ["Not removed in any release read"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.SP_READY);
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 1 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, want, not] of cases) {
      n++;
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await p.fill("#q", q); await p.click("#go");
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      const t = (await p.evaluate(() => document.getElementById("res").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (miss.length || extra.length || over > 0) { fail++; console.log("FAIL", w, name, { miss, extra, over }, "|", t.slice(0, 600)); }
    }
    for (const ex of await p.$$("[data-ex]")) {
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await ex.click();
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      if (!/Removed in SciPy|Not removed/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from scipy.linalg import triu"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("numpy")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
