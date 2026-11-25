// Usage: node check_browser.js <base url>   (serve the site root, which has en/matplotlib-removed-name-lookup/)
// Expected strings were written by hand from the probe results and matplotlib's warnings, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/matplotlib-removed-name-lookup/";
const cases = [
  ["get_cmap", "AttributeError: module 'matplotlib.cm' has no attribute 'get_cmap'", ["matplotlib.cm.get_cmap", "Removed in matplotlib 3.11.0", "also missing in 3.9.0", "matplotlib.colormaps[name]", "3.9.2 to 3.10.9", "matplotlib<3.11.0"], []],
  ["tostring", "AttributeError: 'FigureCanvasAgg' object has no attribute 'tostring_rgb'", ["FigureCanvasAgg.tostring_rgb", "Removed in matplotlib 3.10.0", "buffer_rgba"], []],
  ["tkagg", "AttributeError: 'FigureCanvasTkAgg' object has no attribute 'tostring_rgb'", ["Removed in matplotlib 3.10.0"], []],
  ["seaborn", "OSError: 'seaborn-whitegrid' is not a valid package style, path of style file, URL of style file, or library style name (library styles are listed in `style.available`)", ["plt.style.use('seaborn-whitegrid')", "Removed in matplotlib 3.8.0", "seaborn-v0_8-whitegrid", "has it, warns"], []],
  ["oldstyle", "OSError: 'seaborn' not found in the style library and input is not a valid URL or path; see `style.available` for list of available styles", ["Removed in matplotlib 3.8.0", "seaborn-v0_8"], []],
  ["legend", "AttributeError: 'Legend' object has no attribute 'legendHandles'", ["Removed in matplotlib 3.9.0", "legend_handles", "3.1.2 to 3.8.4"], ["not there</td></tr><tr><td>3.7"]],
  ["subplot", "AttributeError: 'AxesSubplot' object has no attribute 'plot_date'", ["matplotlib.axes.Axes.plot_date", "Removed in matplotlib 3.11.0"], []],
  ["axes3d", "AttributeError: 'Axes3D' object has no attribute 'dist'", ["Removed in matplotlib 3.8.0", "deprecated in Matplotlib 3.6"], []],
  ["docstring", "AttributeError: module 'matplotlib' has no attribute 'docstring'", ["(module)", "Removed in matplotlib 3.8.0"], []],
  ["alive", "AttributeError: module 'matplotlib.pyplot' has no attribute 'get_cmap'", ["Not removed in any release read"], []],
  ["style-alive", "plt.style.use('ggplot')", ["Not removed in any release read", "a style name"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.MPL_READY);
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
      if (!/Removed in matplotlib|Not removed/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("matplotlib.cm.get_cmap"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("colormaps[name]")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
