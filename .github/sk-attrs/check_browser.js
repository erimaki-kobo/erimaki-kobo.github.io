// Usage: node check_browser.js <base url>   (serve the site root, which has en/sklearn-removed-name-lookup/)
// Expected strings were written by hand from the probe results and scikit-learn's messages, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/sklearn-removed-name-lookup/";
const cases = [
  ["boston", "ImportError: cannot import name 'load_boston' from 'sklearn.datasets' (/usr/local/lib/python3.11/site-packages/sklearn/datasets/__init__.py)", ["sklearn.datasets.load_boston", "Removed in scikit-learn 1.2.0", "ethical problem", "0.22 to 1.1.0", "scikit-learn<1.2.0"], ["site-packages"]],
  ["plot_cm", "cannot import name 'plot_confusion_matrix' from 'sklearn.metrics'", ["Removed in scikit-learn 1.2.0", "ConfusionMatrixDisplay"], []],
  ["forest", "ModuleNotFoundError: No module named 'sklearn.ensemble.forest'", ["sklearn.ensemble.forest", "(module)", "Removed in scikit-learn 0.24.0", "sklearn.ensemble"], []],
  ["joblib", "from sklearn.externals import joblib", ["Removed in scikit-learn 0.23.0", "joblib"], []],
  ["cv", "from sklearn.cross_validation import train_test_split", ["sklearn.cross_validation", "Removed in scikit-learn 0.20.0", "model_selection"], []],
  ["imputer", "from sklearn.preprocessing import Imputer", ["Removed in scikit-learn 0.22", "SimpleImputer"], []],
  ["alive", "from sklearn.model_selection import train_test_split", ["Not removed in any release read"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.SK_READY);
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
      if (!/Removed in scikit-learn|Not removed/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from sklearn.datasets import load_boston"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("fetch_california_housing")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
