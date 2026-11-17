// Usage: node check_browser.js <base url>   (serve a directory that has en/diffusers-import-name-version-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/diffusers-import-name-version-lookup/";
const LATEST = process.env.LATEST_RELEASE || "0.43.0";
const cases = [
  ["too old", "ImportError: cannot import name 'FluxPipeline' from 'diffusers' (/usr/local/lib/python3.11/site-packages/diffusers/__init__.py)", "0.29.2",
    ["from 0.30.0 (2024-08-07) and still in", 'pip install "diffusers>=0.30.0"', "Your 0.29.2: does not have it."], ["gone", "site", "never there"]],
  ["new enough", "from diffusers import FluxPipeline, StableDiffusionPipeline", "0.30.0", ["Your 0.30.0: has it.", "from 0.2.0", "another copy of diffusers"], ["does not have it"]],
  ["randn_tensor", "ImportError: cannot import name 'randn_tensor' from 'diffusers.utils'", "",
    ["diffusers.utils", "0.12.0", "through 0.20.2; gone in 0.21.0 (2023-09-13)", 'pip install "diffusers>=0.12.0,<0.21.0"', "defined in diffusers.utils.torch_utils in " + LATEST, "from diffusers.utils.torch_utils import randn_tensor"], ["never there"]],
  ["removed families", "from diffusers import OnnxStableDiffusionPipeline, FlaxStableDiffusionPipeline, StableDiffusionKDiffusionPipeline", LATEST,
    ["through 0.42.1; gone in 0.43.0 (2026-11-12)", "Please use Optimum for ONNX Runtime support.", 'pip install "diffusers>=0.6.0,<0.43.0"',
      "gone in 0.40.0", "Flax classes are deprecated and will be removed in Diffusers v0.40.0", "gone in 0.37.0", "0.33.1", "Your " + LATEST + ": does not have it."], ["has it."]],
  ["module that moved", "ModuleNotFoundError: No module named 'diffusers.models.unet_2d_condition'", "",
    ["module", "0.2.0", "gone in 0.29.0", "diffusers.models.unets.unet_2d_condition", 'pip install "diffusers>=0.2.0,<0.29.0"'], ["never there"]],
  ["old path, name", "from diffusers.models.unet_2d_condition import UNet2DConditionModel", "0.31.0",
    ["gone in 0.29.0", "from diffusers import UNet2DConditionModel", "top level, since 0.2.0", "diffusers.models.unets.unet_2d_condition", "Your 0.31.0: does not have it."], []],
  ["renamed class", "from diffusers.models.embeddings import PositionNet", "", ["0.20.0", "gone in 0.26.0", "GLIGENTextBoundingboxProjection"], ["never there"]],
  ["stale entry", "cannot import name 'OnnxStableDiffusionInpaintPipelineLegacy' from 'diffusers'", "0.31.0",
    ["0.8.0", "gone in 0.25.0", "lazy table still lists this name", "through 0.42.1", "Your 0.31.0: does not have it."], []],
  ["constant", "cannot import name 'HF_HUB_OFFLINE' from 'diffusers.utils'", "0.31.0", ["gone in 0.25.0", "huggingface_hub.constants", "Your 0.31.0: does not have it."], []],
  ["attribute error", "AttributeError: module diffusers has no attribute StableDiffusionKDiffusionPipeline", "", ["gone in 0.37.0", "through 0.36."], ["never there"]],
  ["failed to import", "RuntimeError: Failed to import diffusers.pipelines.stable_diffusion.pipeline_cycle_diffusion because of the following error (look up to see its traceback):", "",
    ["module", "gone in 0.25.0", "diffusers.pipelines.deprecated.stable_diffusion_variants.pipeline_cycle_diffusion"], ["never there"]],
  ["multi-line import", "from diffusers.utils import (\n    randn_tensor,  # noise\n    load_image as li,\n    logging,\n)", "0.21.0",
    ["randn_tensor", "load_image", "logging", "Your 0.21.0: does not have it.", "Your 0.21.0: has it."], ["noise", "li"]],
  ["cross attention", "from diffusers.models.cross_attention import CrossAttention", "", ["0.12.0", "gone in 0.20.0"], []],
  ["bare name, deep", "retrieve_timesteps", "", ["not top-level", "Never importable as from diffusers import retrieve_timesteps"], []],
  ["bare name, top", "WanPipeline", "0.32.0", ["from 0.33.0", "Your 0.32.0: does not have it."], ["not top-level"]],
  ["typo", "cannot import name 'FluxPipline' from 'diffusers'", "", ["never there", "Close names", "FluxPipeline"], ["Instead"]],
  ["no such module", "from diffusers.foo.bar import Baz", "", ["no such module", "diffusers.foo.bar"], []],
  ["never anywhere", "FooBarBazQux", "", ["never there", "any module"], []],
  ["foreign name", "from diffusers.models.embeddings import nn", "", ["in " + LATEST], ["never there"]],
  ["markup is text", "<img src=x onerror=alert(1)> cannot import name 'FluxPipeline' from 'diffusers'", "", ["from 0.30.0"], []],
  ["bad version", "FluxPipeline", "abc", ["Version should look like"], []],
  ["nothing", "???", "", ["Found no name"], []],
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
    await p.waitForFunction(() => window.DF_DATA);
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      latest: window.DF_DATA.latest, over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 4 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0 || st.latest !== LATEST) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, v, want, not] of cases) {
      n++;
      await ask(p, q, v);
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      const img = await p.evaluate(() => document.querySelectorAll("#res img").length);
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (miss.length || extra.length || img || over > 0) { fail++; console.log("FAIL", w, name, { miss, extra, img, over }, "|", t.slice(0, 900)); }
    }
    for (const ex of await p.$$("[data-ex]")) {
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await ex.click();
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      const t = await p.evaluate(() => document.getElementById("res").innerText);
      if (!/through|from /.test(t)) { fail++; console.log("FAIL example button", w, t.slice(0, 200)); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("cannot import name 'randn_tensor' from 'diffusers.utils'") + "&v=0.21.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your 0.21.0: does not have it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
