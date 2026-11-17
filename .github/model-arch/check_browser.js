// Usage: node check_browser.js <base url>   (serve the repository root; the page fetches data.json and the GGUF page's archs.json)
// Expected strings come from the registries read by hand for this release, not from the tool.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2];
// [name, pasted text, your Transformers, your vLLM, must appear, must not appear]
const cases = [
  ["qwen3 config", '{"architectures":["Qwen3ForCausalLM"],"model_type":"qwen3"}', "", "", ["v4.51.0", "v0.8.4", "b5092"], ["not in any release"]],
  ["new in vLLM 0.34.0 and TF 5.23.0", '{"architectures":["Lfm3ForCausalLM"],"model_type":"lfm3"}', "5.22.2", "0.33.0", ["v5.23.0", "v0.34.0", "too old"], ["not in any release"]],
  ["vLLM error text, new name", "ValueError: Model architectures ['ZayaForCausalLM'] are not supported for now.", "", "", ["v0.34.0"], ["not in any release"]],
  ["KeyError, new model_type", "KeyError: 'inkling2'", "", "", ["v5.23.0"], ["not in any release"]],
  ["moved to the Transformers backend in 0.34.0", '{"architectures":["GemmaForCausalLM"],"model_type":"gemma"}', "", "", ["v0.3.2", "v0.33.0", "Transformers"], ["was supported in vLLM until"]],
  ["removed in 0.34.0", '{"architectures":["KeyeForConditionalGeneration"],"model_type":"keye"}', "", "", ["v0.9.2 (2025-07-08) to v0.33.0", "was supported in vLLM until v0.33.0"], []],
  ["gone in 0.34.0", "PeagleLlamaForCausalLM", "", "", ["v0.33.0"], ["not in any release"]],
  ["Mistral Large 4, Transformers class", '{"architectures":["MistralLarge4ForConditionalGeneration"],"model_type":"mistral_large4"}', "", "", ["v5.22.0", "no native implementation", "v0.34.0"], []],
  ["Mistral Large 4, vLLM's own name", "MistralLarge4ForCausalLM", "", "", ["v0.34.0 (2026-11-16)"], ["not in any release"]],
  ["converter learned a class after b12352", '{"architectures":["Inkling2ForCausalLM"],"model_type":"inkling2"}', "", "", ["v5.23.0", "inkling2", "b12406"], []],
  ["old favourite still the same", '{"architectures":["Gemma4ForConditionalGeneration"],"model_type":"gemma4"}', "5.5.0", "0.19.0", ["v5.5.0", "v0.19.0", "b8637", "new enough"], ["too old"]],
  ["nonsense", "hello world", "", "", [], ["v0.34.0 (", "v5.23.0 ("]],
];
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + "/en/model-arch-min-version/", { waitUntil: "networkidle" });
    const st = await p.evaluate(() => ({ tft: document.querySelectorAll("#tft tbody tr").length, vlt: document.querySelectorAll("#vlt tbody tr").length,
      fam: document.querySelectorAll("#fam tbody tr").length, h1: document.querySelectorAll("h1").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].length,
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.tft !== 832 || st.vlt !== 487 || st.fam !== 30 || st.h1 !== 1 || st.ld < 4 || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, tv, vv, want, not] of cases) {
      n++;
      await p.fill("#q", q); await p.fill("#tv", tv); await p.fill("#vv", vv); await p.click("#go");
      await p.waitForTimeout(150);
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      if (miss.length || extra.length) { fail++; console.log("FAIL", w, name, { miss, extra }, "|", t.slice(0, 700)); }
      else if (w === 1200) console.log("ok", name, "=>", t.slice(0, 150));
    }
    await p.fill("#filter", "lfm3");
    const vis = await p.evaluate(() => [...document.querySelectorAll("#vlt tbody tr")].filter(r => r.offsetParent !== null).length);
    if (vis < 3 || vis > 10) { fail++; console.log("FAIL filter", w, vis); }
    await p.close();
  }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths)");
  process.exit(fail ? 1 : 0);
})();
