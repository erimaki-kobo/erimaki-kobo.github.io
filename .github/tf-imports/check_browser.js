// Usage: node check_browser.js <base url>   (serve a directory that has en/transformers-import-name-version-lookup/)
// Expected strings were written from the release ranges and the deprecation messages by hand, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2];
const LATEST = process.env.LATEST_RELEASE || "5.23.0";
// [label, text, version, must appear, must not appear]
const cases = [
  ["AdamW error", "ImportError: cannot import name 'AdamW' from 'transformers' (/usr/local/lib/python3.11/dist-packages/transformers/__init__.py)", "",
    ["2.0.0 (2019-09-26) through 4.49.0; gone in 4.50.0", "torch.optim.AdamW", 'pip install "transformers>=2.0.0,<4.50.0"', "transformers.optimization"], ["never there", "dist"]],
  ["old tutorial on a v5 install", "from transformers import TFBertModel, BertTokenizerFast, AutoModelWithLMHead", "5.23.0",
    ["through 4.57.6; gone in 5.0.0", "v5 removed TensorFlow support", "Your 5.23.0: does not have it.", "hands back BertTokenizer", "Your 5.23.0: has it.", "AutoModelForCausalLM"], []],
  ["same on 4.57.6", "from transformers import TFBertModel, BertTokenizerFast", "4.57.6", ["Your 4.57.6: has it."], ["does not have it"]],
  ["utils module", "cannot import name 'FLAX_WEIGHTS_NAME' from 'transformers.utils'", "", ["transformers.utils", "4.18.0", "through 4.57.6; gone in 5.0.0"], ["never there"]],
  ["agents", "from transformers import ReactCodeAgent, Tool, load_tool", "", ["smolagents", 'pip install "transformers>=4.41.0,<4.52.1"', 'pip install "transformers>=4.29.0,<4.52.1"', "through 4.51.3"], []],
  ["newer name on an old install", "AutoModelForImageTextToText", "4.44.2", ["from 4.46.1", "Your 4.44.2: does not have it.", 'pip install "transformers>=4.46.1"'], ["gone"]],
  ["never a name", "from transformers import FooBarBazQux", "", ["never there"], ["Instead"]],
  ["wrong capitals", "AutoModelForCausalLm", "", ["never there", "Close names", "AutoModelForCausalLM"], []],
  ["in another module", "cannot import name 'torch_int' from 'transformers'", "", ["never there", "It is a name of transformers.utils", "from 4.42.0"], []],
  ["file_utils shim", "cannot import name 'cached_path' from 'transformers.file_utils'", "", ["transformers.file_utils", "through 4.21.3; gone in 4.22.0"], []],
  ["submodule not covered", "ImportError: cannot import name 'PreTrainedModel' from 'transformers.modeling_utils'", "", ["not covered", "The same name at the top level"], []],
  ["checkpoint lists", "BERT_PRETRAINED_MODEL_ARCHIVE_LIST", "", ["gone in 4.41.0", "lists of checkpoint names"], []],
  ["multi-line import", "from transformers import (\n    AutoTokenizer,\n    Trainer as T,\n    glue_convert_examples_to_features,\n)", "", ["AutoTokenizer", "Trainer", "gone in 5.20.0", "Datasets library"], ["never there"]],
  ["markup is text", "<img src=x onerror=alert(1)> cannot import name 'AdamW' from 'transformers'", "", ["gone in 4.50.0"], []],
  ["nothing", "???", "", ["Found no name"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + "/en/transformers-import-name-version-lookup/", { waitUntil: "load" });
    await p.waitForFunction(() => window.TF_DATA);
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      latest: window.TF_DATA.latest, over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 2 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0 || st.latest !== LATEST) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, v, want, not] of cases) {
      n++;
      await p.fill("#q", q); await p.fill("#v", v); await p.click("#go");
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      const img = await p.evaluate(() => document.querySelectorAll("#res img").length);
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (miss.length || extra.length || img || over > 0) { fail++; console.log("FAIL", w, name, { miss, extra, img, over }, "|", t.slice(0, 700)); }
    }
    for (const ex of await p.$$("[data-ex]")) {
      await ex.click();
      const t = await p.evaluate(() => document.getElementById("res").innerText);
      if (!/through|from /.test(t)) { fail++; console.log("FAIL example button", w, t.slice(0, 200)); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + "/en/transformers-import-name-version-lookup/?q=" + encodeURIComponent("AdamW") + "&v=4.50.0", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").innerText.length > 0);
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your 4.50.0: does not have it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
