// Usage: node check_browser.js <base url>   (serve a directory that has en/peft-trl-accelerate-import-name-lookup/)
// Expected strings were written by hand from the release ranges and the quoted messages, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/peft-trl-accelerate-import-name-lookup/";
const cases = [
  ["collator", "ImportError: cannot import name 'DataCollatorForCompletionOnlyLM' from 'trl' (/usr/local/lib/python3.11/site-packages/trl/__init__.py)", "0.20.0",
    ["gone in 0.20.0", 'pip install "trl>=0.5.0,<0.20.0"', "completion_only_loss", "Your trl 0.20.0: does not have it."], ["site-packages", "never there"]],
  ["ppo moved", "from trl import PPOTrainer, PPOConfig", "", ["gone in 0.29.0", "still importable from trl.experimental.ppo"], ["never there"]],
  ["int8", "ImportError: cannot import name 'prepare_model_for_int8_training' from 'peft'", "0.9.0",
    ["gone in 0.10.0", "prepare_model_for_kbit_training", "Your peft 0.9.0: has it."], []],
  ["npu", "ImportError: cannot import name 'is_npu_available' from 'accelerate.utils'", "0.20.3",
    ["accelerate.utils", "from 0.21.0", 'pip install "accelerate>=0.21.0"', "Your accelerate 0.20.3: does not have it."], ["gone"]],
  ["partial", "cannot import name 'PartialState' from 'accelerate'", "0.16.0", ["from 0.17.0", "Your accelerate 0.16.0: does not have it."], []],
  ["tpu", "from accelerate.utils import is_tpu_available", "", ["gone in 0.28.0", "is_torch_xla_available", "accelerate.utils.imports"], []],
  ["chat format", "from trl import setup_chat_format", "", ["gone in 0.26.0", "clone_chat_template"], []],
  ["stale", "cannot import name 'PPOv2Trainer' from 'trl.trainer'", "", ["gone in 0.13.0", "lazy table still lists this name", "ppov2_trainer"], []],
  ["bare", "PPOv2Trainer", "", ["trl", "0.11.0"], ["never there"]],
  ["module", "ModuleNotFoundError: No module named 'trl.commands'", "", ["module", "gone in 0.13.0"], ["never there"]],
  ["attribute", "AttributeError: module 'trl' has no attribute 'SFTScriptArguments'", "", ["gone in 0.13.0", "ScriptArguments"], []],
  ["multi", "from peft import (\n  LoraConfig,  # adapter\n  get_peft_model as gpm,\n)", "0.3.0", ["LoraConfig", "get_peft_model", "Your peft 0.3.0: has it."], ["adapter", "gpm"]],
  ["typo", "cannot import name 'SFTTrainner' from 'trl'", "", ["never there", "SFTTrainer"], []],
  ["no module", "from trl.foo import Bar", "", ["no such module"], []],
  ["nothing", "FooBarBazQux", "", ["never there", "peft, trl, accelerate"], []],
  ["markup", "<img src=x onerror=alert(1)> cannot import name 'SFTTrainer' from 'trl'", "", ["from 0.5.0"], []],
  ["bad version", "SFTTrainer", "abc", ["Version should look like"], []],
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
    await p.waitForFunction(() => window.PTA_READY);
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 5 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, v, want, not] of cases) {
      n++;
      await ask(p, q, v);
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      const img = await p.evaluate(() => document.querySelectorAll("#res img").length);
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (miss.length || extra.length || img || over > 0) { fail++; console.log("FAIL", w, name, { miss, extra, img, over }, "|", t.slice(0, 700)); }
    }
    for (const ex of await p.$$("[data-ex]")) {
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await ex.click();
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      if (!/through|from /.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("from trl import DataCollatorForCompletionOnlyLM") + "&v=0.19.1", { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("Your trl 0.19.1: has it.")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
