// node check_browser.js out/index.html : runs the lookup on known inputs and checks layout (no horizontal overflow at 390px)
const { chromium } = require("playwright");
const path = require("path");
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1100, height: 900 } });
  const errs = [];
  p.on("pageerror", e => errs.push(String(e)));
  p.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
  await p.goto("file://" + path.resolve(process.argv[2]));
  const D = await p.evaluate(() => D);
  let fail = 0;
  async function run(q, b_, o, pp) {
    await p.fill("#q", q); await p.fill("#b", b_ || ""); await p.fill("#o", o || ""); await p.fill("#p", pp || "");
    await p.click("#go");
    return (await p.textContent("#res")) + " | " + (await p.textContent("#status"));
  }
  function expect(label, text, ...needles) {
    const ok = needles.every(n => text.includes(n));
    if (!ok) { fail++; console.log("FAIL", label, "\n  got:", text.slice(0, 500), "\n  want:", needles); }
    else console.log("ok  ", label);
  }
  const FORUM = "1444df51289cfa8063b96f0e62b1125440111bc79a52003ea14b6eac7016fd5f";
  const fr = D.h[FORUM];
  let t = await run("WARNING:hf-to-gguf:** chkhsh:  " + FORUM + "\nNotImplementedError: BPE pre-tokenizer was not recognized - update get_vocab_base_pre()", "b9000");
  expect("forum hash", t, "Recognized from llama.cpp " + fr[2], "qwen35", "older than " + fr[2], "Loading the result", D.n.qwen35[0]);
  t = await run("** chkhsh:  " + FORUM, "b9049");
  expect("forum hash at boundary", t, "yes", "b9049");
  t = await run("chkhsh: " + "0".repeat(64));
  expect("unknown hash", t, "is not recognized by any llama.cpp build up to " + D.head);
  t = await run("llama_model_load: error loading model: error loading model vocabulary: unknown pre-tokenizer type: 'domyn-edge'", "", "0.40.0", "0.3.38");
  expect("domyn-edge", t, "loads from llama.cpp " + D.n["domyn-edge"][0], "older than " + D.n["domyn-edge"][2], "llama-cpp-python 0.3.38 bundles it", "qwen2");
  t = await run("glm5");
  expect("glm5 rename", t, "--pre-tokenizer glm4");
  t = await run("unknown pre-tokenizer type: 'qwen2'", "b2812");
  expect("qwen2 old build", t, "older than " + D.n.qwen2[0]);
  t = await run("llm_load_vocab: missing pre-tokenizer type, using: 'default'");
  expect("missing", t, "has no tokenizer.ggml.pre");
  t = await run("jina-v2-en");
  expect("wordpiece", t, "WordPiece");
  t = await run("unknown pre-tokenizer type: 'dolphin12b'");
  expect("unknown name", t, "No llama.cpp build up to");
  t = await run("BPE pre-tokenizer was not recognized");
  expect("no hash", t, "Paste the whole warning block");
  t = await run("32d85c31273f8019248f2559fed492d929ea28b17e51d81d3bb36fff23ca72b3");
  expect("shared hash", t, "domyn-edge", "last entry wins");
  await p.fill("#fn", "glm");
  const vis = await p.$$eval("#nt tbody tr", rs => rs.filter(r => r.style.display !== "none").map(r => r.getAttribute("data-k")));
  expect("filter", vis.join(","), "glm4", "glm5");
  if (vis.some(v => !v.includes("glm"))) { fail++; console.log("FAIL filter extra", vis); }
  const rows = await p.$$eval("#ht tbody tr", r => r.length), nrows = await p.$$eval("#nt tbody tr", r => r.length);
  expect("row counts", rows + "/" + nrows, Object.keys(D.h).length + "/" + Object.keys(D.n).length);
  const ids = await p.$$eval("[id]", es => es.map(e => e.id));
  const dupIds = ids.filter((x, i) => ids.indexOf(x) !== i);
  if (dupIds.length) { fail++; console.log("FAIL duplicate ids", dupIds.slice(0, 5)); }
  const m = await b.newPage({ viewport: { width: 390, height: 800 } });
  await m.goto("file://" + path.resolve(process.argv[2]));
  const over = await m.evaluate(() => {
    const w = document.documentElement.clientWidth;
    return [...document.querySelectorAll("main > *:not(.tw)")].filter(e => e.getBoundingClientRect().right > w + 1).map(e => e.tagName + "#" + e.id).slice(0, 5);
  });
  const sw = await m.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (over.length || sw > 0) { fail++; console.log("FAIL overflow at 390px", over, sw); } else console.log("ok   no overflow at 390px");
  if (errs.length) { fail++; console.log("FAIL console errors", errs); }
  await b.close();
  console.log(fail ? "FAILURES " + fail : "ALL OK");
  process.exit(fail ? 1 : 0);
})();
