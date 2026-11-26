const { chromium } = require("playwright"); const path = require("path");
(async () => { const b = await chromium.launch(); const errs = [];
  for (const w of [390, 1100]) { const p = await b.newPage({ viewport: { width: w, height: 900 } }); p.on("pageerror", e => errs.push(String(e)));
    await p.goto("file://" + path.resolve("out/index.html"));
    const sw = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    console.log(w, "overflow", sw, "h1", await p.$$eval("h1", x => x.length), "svrows", await p.$$eval("#sv tbody tr", x => x.length));
    if (w === 1100) await p.screenshot({ path: "/tmp/r1.png", fullPage: false });
    if (w === 390) { await p.evaluate(() => document.getElementById("survey").scrollIntoView()); await p.screenshot({ path: "/tmp/r2.png" }); } }
  console.log("errors", errs); await b.close(); })();
