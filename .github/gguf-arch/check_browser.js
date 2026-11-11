// Browser checks of the built page. Usage: node check_browser.js out/index.html out/archs.json
// Expected values are derived from archs.json (not from the page's own JS).
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const html = path.resolve(process.argv[2]);
  const data = JSON.parse(fs.readFileSync(path.resolve(process.argv[3]), 'utf8'));
  const by = {}; for (const a of data.architectures) by[a.architecture] = a;
  const url = 'file://' + html;
  const b = await chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome' });
  let fail = 0;
  const ok = (n, c, x) => { console.log((c ? 'ok   ' : 'FAIL ') + n + (c ? '' : ' :: ' + (x || ''))); if (!c) fail++; };
  const p = await b.newPage({ viewport: { width: 1200, height: 900 } });
  const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(url);
  ok('one h1', await p.locator('h1').count() === 1);
  ok('table rows = archs.json', await p.locator('#archs tbody tr').count() === data.architectures.length);
  const run = async (q, bld, ol) => { await p.fill('#q', q); await p.fill('#b', bld || ''); await p.fill('#o', ol || ''); await p.click('#go'); return (await p.locator('#res').innerText()).replace(/\s+/g, ' '); };
  // 1) error line -> min build, for 6 archs spread over the years
  for (const a of ['gemma4', 'qwen35', 'kimi-k31', 'mistral3', 'lfm2', 'llama']) {
    const t = await run("llama_model_load: error loading model: unknown model architecture: '" + a + "'");
    ok(a + ' min build ' + by[a].llama_cpp_first_build, t.includes(a + ' needs llama.cpp ' + by[a].llama_cpp_first_build + ' or newer'), t.slice(0, 300));
    const o = by[a].ollama_first_release_bundled_llama_cpp;
    if (o) ok(a + ' ollama ' + o, t.includes(o.replace(/^v/, '')), t.slice(0, 400));
    else ok(a + ' not in any ollama release', t.includes('no release bundles it yet'), t.slice(0, 400));
  }
  // 2) verdicts for the user's own versions (hand-computed)
  let t = await run('gemma4', 'b8636', '0.24.0');   // one below b8637 -> too old; 0.24.0 is Go-engine era, bundled b7437
  ok('b8636 too old for gemma4', t.includes('Your build b8636 is too old'), t);
  ok('0.24.0 own engine + b7437', t.includes('registers it in its own engine') && t.includes('b7437'), t);
  t = await run('gemma4', 'b8637', '0.30.0');       // exactly the minimum -> ok; 0.30.0 bundles it
  ok('b8637 knows gemma4', t.includes('Your build b8637 already knows'), t);
  ok('0.30.0 can load gemma4', t.includes('Ollama 0.30.0 can load it'), t);
  t = await run('qwen35', '7989', '0.40.16');
  ok('b7989 too old for qwen35', t.includes('Your build b7989 is too old'), t);
  ok('0.40.16 can load qwen35', t.includes('Ollama 0.40.16 can load it'), t);
  t = await run('kimi-k31', 'b12180', '0.40.16');   // b12180 >= b12180 ok; ollama latest pins b12177 < b12180
  ok('b12180 knows kimi-k31', t.includes('Your build b12180 already knows'), t);
  ok('0.40.16 cannot load kimi-k31', t.includes('Ollama 0.40.16 cannot load it'), t);
  t = await run('qwen9');
  ok('unknown arch message', t.includes('"qwen9" is not an architecture in upstream llama.cpp as of ' + data.llama_cpp_head), t);
  // 3) mobile width, JS errors
  const m = await b.newPage({ viewport: { width: 390, height: 800 } });
  await m.goto(url + '?arch=gemma4&build=8500&ollama=0.24.0');
  const ow = await m.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok('no horizontal overflow at 390px', ow <= 0, String(ow));
  const t2 = (await m.locator('#res').innerText()).replace(/\s+/g, ' ');
  ok('restore from URL', t2.includes('Your build b8500 is too old'), t2);
  ok('no JS errors', errs.length === 0, errs.join(' | '));
  await b.close(); console.log(fail ? 'FAIL ' + fail : 'ALL PASS'); process.exit(fail ? 1 : 0);
})();
