// Usage: node check_browser.js <base url>   (serve the site root, which has en/pandas-removed-attribute-lookup/)
// Expected strings were written by hand from the probe results and pandas' messages, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/pandas-removed-attribute-lookup/";
const cases = [
  ["append", "AttributeError: 'DataFrame' object has no attribute 'append'", ["DataFrame.append", "Removed in pandas 2.0.0", "pandas.concat", "0.25.3 to 1.5.0", "pandas<2.0.0"], ["Series.append"]],
  ["series append", "AttributeError: 'Series' object has no attribute 'append'", ["Series.append", "Removed in pandas 2.0.0"], []],
  ["iteritems", "AttributeError: 'DataFrame' object has no attribute 'iteritems'", ["Use .items instead.", "2.0.0 to 3.1.1"], []],
  ["applymap", "'DataFrame' object has no attribute 'applymap'", ["Removed in pandas 3.0.0", "DataFrame.map"], []],
  ["ix", "df.ix[0, 'a']", ["DataFrame.ix", "Removed in pandas 1.0.0", ".loc for labels", "our note"], []],
  ["Int64Index", "AttributeError: module 'pandas' has no attribute 'Int64Index'", ["pd.Int64Index", "Removed in pandas 2.0.0", "pandas.Index", "warns on access"], []],
  ["exists", "AttributeError: 'Series' object has no attribute 'map'", ["Not removed in any release read"], []],
  ["column", "AttributeError: 'DataFrame' object has no attribute 'price'", ["df['price']"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.PD_READY);
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
      if (!/Removed in pandas/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("df.append(row)"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("pandas.concat")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
