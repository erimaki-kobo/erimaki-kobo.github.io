// Usage: node check_browser.js <base url>   (serve the site root, which has en/networkx-removed-name-lookup/)
// Expected strings were written by hand from the probe results and networkx's warnings and migration guides, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/networkx-removed-name-lookup/";
const cases = [
  ["numpy", "AttributeError: module 'networkx' has no attribute 'from_numpy_matrix'", ["networkx.from_numpy_matrix", "Removed in networkx 3.0", "from_numpy_array", "networkx<3.0", "1.11 to 2.8.8"], []],
  ["gpickle", "AttributeError: module 'networkx' has no attribute 'read_gpickle'", ["Removed in networkx 3.0", "pickle.load"], []],
  ["node", "AttributeError: 'Graph' object has no attribute 'node'", ["G.node (Graph)", "Removed in networkx 2.4", "G.nodes[n]", "1.11 to 2.3"], ["not there</td></tr><tr><td>2.0"]],
  ["dinode", "AttributeError: 'DiGraph' object has no attribute 'node'", ["G.node (DiGraph)", "Removed in networkx 2.4"], []],
  ["ccs", "AttributeError: module 'networkx' has no attribute 'connected_component_subgraphs'", ["Removed in networkx 2.4", "connected_components(G)"], []],
  ["iter", "AttributeError: 'Graph' object has no attribute 'nodes_iter'", ["Removed in networkx 2.0", "G.nodes()", "our note"], []],
  ["edge", "AttributeError: 'MultiDiGraph' object has no attribute 'edge'", ["Removed in networkx 2.0", "G.adj"], []],
  ["info", "AttributeError: module 'networkx' has no attribute 'info'", ["Removed in networkx 3.0", "print(G)"], []],
  ["import", "ImportError: cannot import name 'from_scipy_sparse_matrix' from 'networkx' (/x/networkx/__init__.py)", ["Removed in networkx 3.0", "from_scipy_sparse_array"], []],
  ["mod", "ModuleNotFoundError: No module named 'networkx.readwrite.gpickle'", ["(module)", "Removed in networkx 3.0"], []],
  ["code", "G = nx.from_numpy_matrix(A)", ["Removed in networkx 3.0"], []],
  ["alive", "AttributeError: module 'networkx' has no attribute 'from_numpy_array'", ["Not removed in any release read"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.NX_READY);
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
      if (!/Removed in networkx|Not removed/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("networkx.read_gpickle"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("pickle.load")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
