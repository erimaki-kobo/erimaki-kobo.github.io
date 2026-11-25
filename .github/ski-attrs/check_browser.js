// Usage: node check_browser.js <base url>   (serve the site root, which has en/scikit-image-removed-name-lookup/)
// Expected strings were written by hand from the probe results and scikit-image's own messages, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/scikit-image-removed-name-lookup/";
const cases = [
  ["ssim", "ImportError: cannot import name 'compare_ssim' from 'skimage.measure' (/x/skimage/measure/__init__.py)", ["skimage.measure.compare_ssim", "Removed in scikit-image 0.18.0", "skimage.metrics.structural_similarity", "scikit-image<0.18.0", "0.16.2 to 0.17.2", "Same result"], []],
  ["grey", "AttributeError: module 'skimage.feature' has no attribute 'greycomatrix'", ["Removed in scikit-image 0.20.0", "graycomatrix", "0.19.0 to 0.19.3"], []],
  ["mc", "TypeError: gaussian() got an unexpected keyword argument 'multichannel'", ["gaussian(multichannel=)", "TypeError from scikit-image 0.20.0", "channel_axis=", "0.19.0 to 0.19.3 still accept", "channel_axis=-1", "scikit-image<0.20.0"], []],
  ["selem", "TypeError: binary_erosion() got an unexpected keyword argument 'selem'", ["TypeError from scikit-image 0.20.0", "footprint="], []],
  ["viewer", "ModuleNotFoundError: No module named 'skimage.viewer'", ["skimage.viewer", "(module)", "Removed in scikit-image 0.20.0"], []],
  ["selemmod", "ModuleNotFoundError: No module named 'skimage.morphology.selem'", ["Removed in scikit-image 0.20.0", "skimage.morphology.footprints"], []],
  ["circle", "from skimage.draw import circle", ["skimage.draw.circle", "Removed in scikit-image 0.19.0", "draw.disk"], []],
  ["rgb2grey", "AttributeError: module 'skimage.color' has no attribute 'rgb2grey'", ["Removed in scikit-image 0.19.0", "rgb2gray"], []],
  ["neighbors", "TypeError: label() got an unexpected keyword argument 'neighbors'", ["TypeError from scikit-image 0.18.0", "connectivity"], []],
  ["graph", "ModuleNotFoundError: No module named 'skimage.future.graph'", ["Removed in scikit-image 0.20.0", "moved to `skimage.graph`"], []],
  ["alive", "ImportError: cannot import name 'structural_similarity' from 'skimage.measure'", ["Not removed in any release read", "skimage.metrics"], ["Removed in scikit-image"]],
  ["indices", "TypeError: peak_local_max() got an unexpected keyword argument 'indices'", ["TypeError from scikit-image 0.20.0"], []],
  ["code", "img = filters.gaussian(img, sigma=2, multichannel=True)", ["TypeError from scikit-image 0.20.0", "channel_axis"], []],
  ["code2", "from skimage.measure import compare_ssim, compare_psnr", ["skimage.measure.compare_ssim", "skimage.measure.compare_psnr", "peak_signal_noise_ratio"], []],
  ["unknownarg", "TypeError: resize() got an unexpected keyword argument 'foo'", ["lost an argument named foo"], ["TypeError from scikit-image"]],
  ["tifffile", "ModuleNotFoundError: No module named 'skimage.external'", ["Removed in scikit-image 0.17.1", "import tifffile"], []],
  ["present", "AttributeError: module 'skimage.metrics' has no attribute 'structural_similarity'", ["Not removed: skimage.metrics.structural_similarity is there in 0.26.0"], []],
  ["winsize", "ValueError: win_size exceeds image extent. Either ensure that your images are at least 7x7; or pass win_size explicitly in the function call", ["From scikit-image 0.20.0", "channel_axis=-1"], []],
  ["output", "TypeError: gaussian() got an unexpected keyword argument 'output'", ["TypeError from scikit-image 0.25.0", "out="], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.SKI_READY);
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 3 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, want, not] of cases) {
      n++;
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await p.fill("#q", q); await p.click("#go");
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      const t = (await p.evaluate(() => document.getElementById("res").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (miss.length || extra.length || over > 0) { fail++; console.log("FAIL", w, name, { miss, extra, over }, "|", t.slice(0, 700)); }
    }
    for (const ex of await p.$$("[data-ex]")) {
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await ex.click();
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      if (!/Removed in scikit-image|TypeError from scikit-image/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("skimage.measure.compare_ssim"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("structural_similarity")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
