// Usage: node check_browser.js <url of the page>
// Smoke test after patch_v0.34.0.py: the newest release is listed first, selected by default,
// and gets the same answers as v0.33.0 and v0.32.0 for schemas whose answers are known from the page's own tables.
const { chromium } = require(process.env.PW || "playwright");
const URL = process.argv[2];
const NEW = "v0.34.0", SAME = ["v0.33.0", "v0.32.0"];
const schemas = [
  ['{"type":"object","properties":{"a":{"type":"string"}},"required":["a"]}', "xgrammar"],
  ['{"type":"object","properties":{"n":{"type":"number","multipleOf":0.5}}}', "guidance"],
  ['{"type":"object","properties":{"s":{"type":"string","format":"email"}}}', null],
  ['{"type":"array","items":{"type":"integer"},"uniqueItems":true}', null],
  ['{"response_format":{"type":"json_schema","json_schema":{"name":"x","schema":{"type":"object","patternProperties":{"^a":{"type":"string"}}}}}}', null],
  ['{"model":"m","messages":[],"guided_json":{"type":"object"}}', null],
];
(async () => {
  const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome" });
  const errs = []; let fail = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    await p.goto(URL, { waitUntil: "load" });
    const st = await p.evaluate(() => ({ first: document.querySelector("#ver option").value, sel: document.getElementById("ver").value, n: document.querySelectorAll("#ver option").length,
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.first !== NEW || st.sel !== NEW || st.n !== 46 || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [q, want] of schemas) {
      const got = {};
      for (const v of [NEW].concat(SAME)) {
        await p.fill("#q", q); await p.selectOption("#ver", v); await p.click("#go");
        got[v] = (await p.evaluate(() => document.getElementById("res").innerText)).replace(/\s+/g, " ");
      }
      const norm = (t, v) => t.split("Across versions")[0].split(v).join("V") + (t.split("Across versions")[1] || "");
      const a = norm(got[NEW], NEW);
      if (!a.trim() || SAME.some(v => norm(got[v], v) !== a) || (want && !got[NEW].toLowerCase().includes(want))) {
        fail++; console.log("FAIL", w, q.slice(0, 50), "|", got[NEW].slice(0, 300), "|", got[SAME[0]].slice(0, 300));
      } else if (w === 1200) console.log("ok", q.slice(0, 44), "=>", got[NEW].slice(0, 110));
    }
    await p.close();
  }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS");
  process.exit(fail ? 1 : 0);
})();
