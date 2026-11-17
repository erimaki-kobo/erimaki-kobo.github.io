// Usage: node check_browser.js <url of the built page>
// Expected answers below were worked out by hand from the table, not from tool.js.
const { chromium } = require(process.env.PW || "playwright");
const URL = process.argv[2];
const LATEST = "0.34.0", NREL = 51;
// [name, driver, gpu, python, glibc, strings that must appear, strings that must not appear, expected "Your system" cell for the latest row]
const cases = [
  ["new driver", "580.65.06", "8.9", "", "", ["v" + LATEST + " (the latest release) installs from PyPI", "uv pip install vllm==" + LATEST, "vllm/vllm-openai:v" + LATEST], ["cu129"], "PyPI"],
  ["R570", "570.133.07", "8.9", "", "", ["Newest release with a prebuilt wheel for this system: v0.32.0 (the +cu129 wheel)", "v" + LATEST + " does not fit: driver 570.133.07 is below 580", "vllm-0.32.0+cu129-cp38-abi3-manylinux_2_28_x86_64.whl", "download.pytorch.org/whl/cu129", "vllm/vllm-openai:v0.32.0-cu129", "Driver branch 570"], [], "no driver"],
  ["R535 data center", "535.183.01", "9.0", "", "", ["v0.32.0 (the +cu129 wheel)", "Driver branch 535", "VLLM_ENABLE_CUDA_COMPATIBILITY=1"], [], "no driver"],
  ["R560 has no compat note", "560.35.03", "12.0", "", "", ["v0.32.0 (the +cu129 wheel)", "Blackwell GPUs also need a driver"], ["Driver branch"], "no driver"],
  ["below CUDA 12 floor", "470.256.02", "8.6", "", "", ["v0.10.1.1 (the +cu118 wheel)", "only the CUDA 11.8 wheels"], [], "no driver"],
  ["V100", "580.95.05", "7.0", "", "", ["Newest release with a prebuilt wheel for this system: v0.19.1", "compute capability 7.0 is not covered by this release's build", "uv pip install vllm==0.19.1"], ["wheel)"], "no gpu"],
  ["Pascal", "580.95.05", "6.x", "", "", ["No prebuilt vLLM wheel from v0.8.0 to v" + LATEST + " fits this system"], ["Install"], "no gpu"],
  ["RTX 50", "580.95.05", "12.0", "", "", ["v" + LATEST + " (the latest release) installs from PyPI", "Blackwell GPUs also need a driver"], [], "PyPI"],
  ["Python 3.10", "580.95.05", "8.9", "3.10", "", ["Newest release with a prebuilt wheel for this system: v0.31.0", "Python 3.10 is outside"], [], "no python"],
  ["old glibc", "580.95.05", "8.9", "", "2.27", ["glibc 2.27 is older than the wheel tag manylinux_2_28"], ["(the latest release) installs"], "no glibc"],
  ["bad driver", "abc", "8.9", "", "", ["Enter the driver version as nvidia-smi prints it"], ["Install"], null],
];
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(URL, { waitUntil: "load" });
    const st = await p.evaluate(() => ({
      rows: document.querySelectorAll("#matrix tbody tr").length,
      first: document.querySelector("#matrix tbody tr").getAttribute("data-v"),
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      h1: document.querySelectorAll("h1").length,
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    }));
    if (st.rows !== NREL || st.first !== LATEST || st.h1 !== 1 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [name, drv, gpu, py, glibc, want, not, cell] of cases) {
      n++;
      await p.fill("#drv", drv); await p.selectOption("#gpu", gpu); await p.selectOption("#py", py); await p.fill("#glibc", glibc); await p.click("#go");
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      let cellBad = null;
      if (cell !== null) {
        const c = (await p.evaluate(v => document.querySelector('#matrix tr[data-v="' + v + '"] .you').innerText, LATEST)).replace(/\s+/g, " ").trim();
        if (c !== cell) cellBad = c;
      }
      if (miss.length || extra.length || cellBad !== null) { fail++; console.log("FAIL", w, name, { miss, extra, cellBad }, "|", t.slice(0, 500)); }
    }
    await p.close();
  }
  // a link with ?driver= runs the lookup on load
  const p = await b.newPage();
  await p.goto(URL + "?driver=570.133.07&gpu=8.9#lookup", { waitUntil: "load" });
  const t = await p.evaluate(() => document.getElementById("res").innerText);
  if (!t.includes("v0.32.0 (the +cu129 wheel)")) { fail++; console.log("FAIL deep link", t.slice(0, 200)); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, deep link)");
  process.exit(fail ? 1 : 0);
})();
