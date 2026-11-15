// usage: node check_browser.js <index.html> <run dir with out/*.jsonl>
// Opens the built page and compares what the tool shows with the raw run_select.py output.
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");
const [page_path, run] = process.argv.slice(2);
function raw(tag, cap, scen) {
  for (const f of [`fix_${tag}.${cap}.jsonl`, `${tag}.${cap}.jsonl`]) {
    const p = path.join(run, "out", f);
    if (!fs.existsSync(p)) continue;
    for (const l of fs.readFileSync(p, "utf8").split("\n")) if (l.startsWith("{")) { const r = JSON.parse(l); if (r.scenario === scen && r.ok) return r; }
  }
  throw new Error("no raw record " + [tag, cap, scen]);
}
(async () => {
  const b = await chromium.launch(); let fail = 0; const errs = [];
  const ok = (name, cond, extra) => { console.log((cond ? "PASS " : "FAIL ") + name + (cond ? "" : " :: " + (extra || ""))); if (!cond) fail++; };
  for (const width of [1200, 375]) {
    const pg = await b.newPage({ viewport: { width, height: 900 } });
    pg.on("pageerror", e => errs.push(String(e))); pg.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
    await pg.goto("file://" + path.resolve(page_path));
    const cases = [["v0.33.0", 120, "nvfp4"], ["v0.33.0", 121, "ct_fp8_channel"], ["v0.15.0", 120, "nvfp4"], ["v0.15.1", 120, "modelopt_fp8"],
                   ["v0.16.0", 120, "mxfp4_gptoss"], ["v0.24.0", 90, "fp8_block"], ["v0.32.0", 100, "mxfp4_gptoss"], ["v0.20.0", 89, "fp8_tensor"], ["v0.33.0", 80, "ct_fp8_tensor_static"]];
    for (const [t, c, s] of cases) {
      await pg.selectOption("#gpu", String(c)); await pg.selectOption("#quant", s); await pg.selectOption("#ver", t);
      const shown = await pg.textContent("#out .big"); const r = raw(t, c, s);
      ok(`w${width} ${t} SM${c} ${s} = ${r.backend}`, shown === r.backend, shown);
      const usable = await pg.$$eval("#out table:first-of-type tbody tr", rows => rows.filter(x => x.children[1].textContent.trim() === "yes").map(x => x.querySelector("code").textContent));
      const want = Object.entries(r.candidates || {}).filter(([k, v]) => v === "ok").map(([k]) => k).sort();
      ok(`w${width} ${t} SM${c} ${s} usable list`, JSON.stringify(usable.slice().sort()) === JSON.stringify(want), JSON.stringify([usable, want]));
    }
    const over = await pg.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    ok(`w${width} no horizontal overflow`, over <= 0, over);
    if (width === 1200) {
      const det = async (cfg) => { await pg.evaluate(() => document.querySelectorAll("details").forEach(d => d.open = true)); await pg.fill("#cfg", cfg); await pg.click("#detbtn"); return [await pg.inputValue("#quant"), await pg.textContent("#det")]; };
      let r = await det('{"quantization_config":{"quant_method":"modelopt","quant_algo":"NVFP4"}}'); ok("detect modelopt NVFP4", r[0] === "nvfp4", r);
      r = await det('{"quantization_config":{"quant_method":"fp8","weight_block_size":[128,128]}}'); ok("detect fp8 block", r[0] === "fp8_block", r);
      r = await det('{"quantization_config":{"quant_method":"compressed-tensors","config_groups":{"group_0":{"weights":{"num_bits":8,"type":"float","strategy":"channel"},"input_activations":{"num_bits":8,"type":"float","strategy":"token","dynamic":true}}}}}'); ok("detect ct channel", r[0] === "ct_fp8_channel", r);
      r = await det('{"quantization_config":{"quant_method":"mxfp4"}}'); ok("detect mxfp4", r[0] === "mxfp4_gptoss", r);
      r = await det('{"quantization_config":{"quant_method":"awq"}}'); ok("awq refused", /not covered/.test(r[1]), r);
      r = await det('null'); ok("null JSON handled", /not a JSON object/.test(r[1]), r);
      r = await det('{"quantization_config":{"quant_method":"<img src=x onerror=window.__x=1>"}}'); ok("no HTML injection", !(await pg.evaluate(() => window.__x)) && !(await pg.$("#det img")), r);
      await pg.fill("#err", "ValueError: NvFp4 MoE backend 'FLASHINFER_CUTLASS' does not support the deployment configuration since kernel does not support current device."); await pg.click("#errbtn");
      let t = await pg.textContent("#errout"); ok("error explain nvfp4", /requested explicitly/.test(t) && /FLASHINFER_CUTLASS/.test(t) && (await pg.inputValue("#quant")) === "nvfp4", t);
      await pg.fill("#err", "ValueError: FP8 MoE backend VLLM_CUTLASS does not support the deployment configuration since kernel does not support current device cuda."); await pg.click("#errbtn");
      t = await pg.textContent("#errout"); ok("error explain fp8 (no quotes)", /VLLM_CUTLASS/.test(t) && /current device cuda/.test(t), t);
      await pg.fill("#err", "ValueError: vLLM CUTLASS FP8 MoE backend is disabled for this configuration."); await pg.click("#errbtn");
      t = await pg.textContent("#errout"); ok("error explain disabled", /allow_vllm_cutlass/.test(t), t);
      await pg.selectOption("#ver", "v0.16.0"); t = await pg.textContent("#out"); ok("no flag before v0.17.0", /no --moe-backend flag/.test(t), t.slice(0, 200));
    }
    await pg.close();
  }
  ok("no page errors", errs.length === 0, errs.join(" | "));
  await b.close(); console.log(fail ? `${fail} FAILED` : "ALL PASS"); process.exit(fail ? 1 : 0);
})();
