// node test_parity.js <index.html> <cases.json> : the library inside the page vs kvplan.py's answers
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (scripts.length !== 1) throw new Error("expected one inline script");
const lib = scripts[0].slice(0, scripts[0].indexOf('})(typeof self !== "undefined" ? self : this);') + 46);
const mod = {exports: {}};
new Function("module", lib)(mod);
const K = mod.exports, data = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
let bad = 0, n = 0, uns = 0;
const close = (a, b) => Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b));
for (const c of data.cases) {
  n++;
  let got = {};
  try {
    const shape = K.readConfig(c.cfg);
    const layers = K.buildLayers(shape, {tensorParallel: c.tp, kvDtype: c.kvd, blockSize: c.bs});
    const avail = c.measured
      ? K.measuredKvMemoryBytes(Math.ceil(c.total * c.util), c.total, c.wts + c.oth - c.trn, c.trn)
      : K.kvMemoryBytes(c.total, c.util, c.wts + c.oth);
    got.avail = avail;
    if (avail > 0) {
      const o = {inFlightTokens: c.infl, disableHybrid: c.dis};
      const p = K.plan(layers, avail, c.L, o);
      got.plan = [p.numBlocks, p.blockBytes, p.blocksPerRequest, p.tokens, p.fits,
        p.estimatedMaxModelLen, p.numGroups, p.paddingLayers, p.concurrency];
      got.typ = K.requestsThatFit(layers, p.numBlocks, Math.min(4096, c.L), o);
    }
  } catch (e) { if (!e.unsupported) throw e; got.unsupported = true; }
  let ok = !!got.unsupported === !!c.unsupported;
  if (ok && !c.unsupported) {
    ok = got.avail === c.avail && (c.plan === undefined) === (got.plan === undefined);
    if (ok && c.plan) ok = c.plan.every((v, i) => i === 8 ? close(got.plan[8], v) : got.plan[i] === v) && got.typ === c.typ;
  }
  if (c.unsupported) uns++;
  if (!ok) { bad++; if (bad < 5) console.log("MISMATCH", JSON.stringify(c), JSON.stringify(got)); }
}
const camel = {bytes_per_token: "bytesPerToken"};
for (const l of data.logs) {
  n++;
  const d = K.parseLog(l.text), r = K.fromLog(d, l.a, l.l);
  const same = (a, b) => { const ka = Object.keys(a).sort(), kb = Object.keys(b).map(k => k).sort();
    return ka.length === kb.length && ka.every(k => { const x = a[k], y = b[camel[k] || k];
      return x === y || (typeof x === "number" && typeof y === "number" && close(y, x)) || (x === null && y === null); }); };
  if (!same(l.parsed, d) || !same(l.res, r)) { bad++; console.log("LOG MISMATCH", l.text.slice(0, 60), JSON.stringify(l.parsed), JSON.stringify(d), JSON.stringify(l.res), JSON.stringify(r)); }
}
console.log(JSON.stringify({inputs: n, unsupported: uns, mismatch: bad}));
process.exit(bad ? 1 : 0);
