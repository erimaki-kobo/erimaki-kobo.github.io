// Usage: node check_browser.js <base url>   (serve the site root, which has en/numpy-removed-attribute-lookup/)
// Expected strings were written by hand from the probe results and NumPy's messages, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/numpy-removed-attribute-lookup/";
const cases = [
  ["float", "AttributeError: module 'numpy' has no attribute 'float'.", ["np.float", "1.25.0 to 2.5.5", "AttributeError with a message", "1.20.0 to 1.23.0", "works, warns (DeprecationWarning)"], []],
  ["float_", "AttributeError: `np.float_` was removed in the NumPy 2.0 release. Use `np.float64` instead.", ["Use `np.float64` instead.", "2.0.0 to 2.5.5", "1.19.5 to 1.26.0"], []],
  ["NaN", "x = np.NaN", ["Use `np.nan` instead.", "2.0.0 to 2.5.5"], []],
  ["product", "module 'numpy' has no attribute 'product'", ["Please use `prod` instead.", "2.0.0 to 2.5.5"], []],
  ["trapz", "np.trapz(y, x)", ["Use `trapezoid` instead", "2.4.1 to 2.5.5", "1.19.5 to 2.3.0"], []],
  ["bool", "np.bool", ["1.24.0", "2.0.0 to 2.5.5", "works"], []],
  ["two", "np.float_ and np.Inf", ["np.float_", "np.Inf", "Use `np.inf` instead."], []],
  ["unknown", "np.foobarbaz", ["Not one of the"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.NP_READY);
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
      if (!/AttributeError|works/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("np.float_"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("np.float64")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
