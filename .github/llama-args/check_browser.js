// Usage: node check_browser.js <base url>   (serve the repository root)
// Expected strings were worked out from the removal commits and the option table by hand, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2];
// The newest build the page read; pass LATEST_BUILD when testing a rebuilt page (run.sh does).
const LATEST = "b" + (process.env.LATEST_BUILD || "12465");
// [name, text, binary select, version, must appear, must not appear]
const cases = [
  ["classic server line", "llama-server -m model.gguf --mlock --no-mmap --defrag-thold 0.1 -ngl 99", "auto", "",
    ["3 of 5 names will stop llama-server", "removed in b10875 (2026-09-09)", "use --load-mode mlock instead", "removed in b12347 (2026-11-12)", "no longer necessary", "accepted by llama-server"], ["not an option in any build"]],
  ["error text only", "error: invalid argument: --direct-io", "auto", "", ["removed in b10875", "use --load-mode dio instead", "this is for llama-server"], []],
  ["own build still had it", "llama-server --mlock", "auto", "b10091", ["Your b10091: accepted."], []],
  ["Ollama release to build", "llama-server process has terminated: exit status 1: error: invalid argument: --load-mode", "auto", "0.32.5",
    ["accepted by llama-server in b12465", "Since b10105", "Your b10091: not accepted.", "Ollama v0.32.5 bundles llama.cpp b10091"], []],
  ["llama-cli lost -no-cnv", "llama-cli -m m.gguf -no-cnv -p hi", "auto", "", ["but not for llama-cli", "stopped in b10584 (2026-08-22)", "llama-completion"], ["this is for llama-server"]],
  ["same flag on llama-completion", "llama-completion -m m.gguf -no-cnv -p hi", "auto", "", ["All 3 names are valid for llama-completion"], []],
  ["server never took -p after b4443", "llama-server -p hello", "auto", "", ["but not for llama-server", "stopped in b4443"], []],
  ["stub", "llama-server --draft-max 16", "auto", "", ["a stub answers since b8955 (2026-04-28)", "the argument has been removed. use --spec-draft-n-max or --spec-ngram-mod-n-max"], []],
  ["misspelled", "llama-server --ngl 99", "auto", "", ["not an option in any build read", "-ngl"], []],
  ["underscore form", "llama-server --ctx_size 4096", "auto", "", ["--ctx-size", "accepted by llama-server"], ["not an option"]],
  ["renamed", "llama-server --clear-idle --tensor-read-lazy", "auto", "", ["removed in b8852", "rename --clear-idle to --cache-idle-slots", "removed in b10700", "rename --tensor-read-lazy to --lazy-mode"], []],
  ["old era", "./main -m m.gguf --instruct --chatml -ins", "auto", "", ["removed before b3716", "Last seen in b3001", "gone by b3250", "error: unknown argument: --instruct"], []],
  ["env silently ignored", "LLAMA_ARG_MLOCK=1 LLAMA_ARG_N_GPU_LAYERS=99 llama-server", "auto", "", ["ignored since b10875", "No error and no warning", "read in b12465", "Nothing here stops llama-server"], []],
  ["env that stops startup", "export LLAMA_ARG_DRAFT_MAX=8", "auto", "", ["stops startup since b8955", "error while handling environment variable"], []],
  ["chosen binary overrides", "--interactive-first", "cli", "", ["but not for llama-cli", "stopped in b7348 (2025-12-10)", "llama-completion"], []],
  ["nothing", "hello world", "auto", "", ["Found no option"], ["names"]],
];
for (const c of cases) for (const i of [4, 5]) c[i] = c[i].map(x => x.replace("b12465", LATEST));
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + "/en/llama-cpp-removed-args-lookup/", { waitUntil: "load" });
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      gone: document.querySelectorAll("#removed + p + div tbody tr").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 6 || st.gone !== 19 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, bin, v, want, not] of cases) {
      n++;
      await p.fill("#q", q); await p.selectOption("#bin", bin); await p.fill("#v", v); await p.click("#go");
      await p.waitForTimeout(v && !/^b?\d+$/.test(v) ? 600 : 80);
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      if (miss.length || extra.length) { fail++; console.log("FAIL", w, name, { miss, extra }, "|", t.slice(0, 900)); }
    }
    await p.fill("#filter", "mmap");
    const vis = await p.evaluate(() => [...document.querySelectorAll("table.flt tbody tr")].filter(r => r.offsetParent !== null).length);
    if (vis < 2 || vis > 8) { fail++; console.log("FAIL filter", w, vis); }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + "/en/llama-cpp-removed-args-lookup/?q=" + encodeURIComponent("llama-server --mlock") + "#lookup", { waitUntil: "load" });
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("removed in b10875")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, deep link)");
  process.exit(fail ? 1 : 0);
})();
