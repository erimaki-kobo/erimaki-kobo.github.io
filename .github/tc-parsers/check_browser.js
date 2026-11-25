// Usage: node check_browser.js <base url>   (serve the site root). Expected strings written by hand from the measurements.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/tool-call-parser-conformance-check/";
const cases = [
  ["?parser=qwen3_coder&vllm=v0.19.1", ["One call", "stays in reasoning, tool_calls empty", "\"tool_calls\""]],
  ["?parser=qwen3_coder&vllm=v0.34.0", ["comes out", "a cut call is returned as a call", "\"length\""]],
  ["?parser=pythonic&vllm=v0.34.0", ["the call is left in message.content"]],
  ["?parser=gemma4&vllm=v0.18.1", ["this release has no such parser"]],
  ["?parser=llama3_json&vllm=v0.33.0", ["the call comes out, the text before it is dropped"]],
  ["?parser=hermes&vllm=v0.23.0", ["comes out", "stays in reasoning"]],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    for (const [q, want] of cases) {
      n++;
      const p = await b.newPage({ viewport: { width: w, height: 900 } });
      p.on("pageerror", e => errs.push(String(e)));
      p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
      await p.goto(BASE + PATH + q, { waitUntil: "load" });
      await p.waitForFunction(() => window.TC_READY);
      const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, t: document.getElementById("res").innerText.replace(/\s+/g, " "),
        ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
        over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
      const miss = want.filter(x => !st.t.includes(x));
      if (miss.length || st.h1 !== 1 || st.over > 0 || st.ld !== "TechArticle,SoftwareApplication,Dataset,FAQPage,BreadcrumbList") { fail++; console.log("FAIL", w, q, { miss, h1: st.h1, over: st.over, ld: st.ld }, st.t.slice(0, 300)); }
      await p.close();
    }
  }
  const p = await b.newPage();
  const r = await p.goto(BASE + PATH + "toolcheck.py"); if (r.status() !== 200) { fail++; console.log("FAIL toolcheck.py", r.status()); }
  const r2 = await p.goto(BASE + PATH + "parser_results.json"); if (r2.status() !== 200) { fail++; console.log("FAIL json"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, files)");
  process.exit(fail ? 1 : 0);
})();
