// usage: node check.js <index.html> <workdir with pypi.json>
// Opens the built page and compares what the tool shows with an answer worked out here, a second time,
// straight from the raw wheel scan (pypi.json) and a rule table typed from the Triton sources.
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");
const [page_path, run] = process.argv.slice(2);
const P = JSON.parse(fs.readFileSync(path.join(run, "pypi.json"), "utf8"));
const vk = v => v.split(".").map(Number), cmp = (a, b) => { const x = vk(a), y = vk(b); for (let i = 0; i < 3; i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) - (y[i] || 0); return 0; };
const ge = (a, b) => cmp(a, b) >= 0;
// second derivation of the rules (release ranges typed by hand from compiler.py / knobs.py)
function expect(t, cap) {
  const two = (ge(t, "3.3.0") && !ge(t, "3.4.0")) || ge(t, "3.6.0");
  const th = ge(t, "3.9.0") ? 90 : 100;
  const tool = two && cap >= th ? "ptxas-blackwell" : "ptxas";
  const name = ge(t, "3.3.0") ? "sm_" + cap + (cap >= 90 ? "a" : "") : "sm_" + cap + (cap === 90 ? "a" : "");
  const arch = P.triton[t].arch.x86_64, banner = arch.tools[tool].banner, ok = arch.tools[tool].sm.includes(name);
  let env = tool === "ptxas" ? "TRITON_PTXAS_PATH" : (ge(t, "3.6.0") ? "TRITON_PTXAS_BLACKWELL_PATH" : "TRITON_PTXAS-BLACKWELL_PATH");
  const accepts = m => { const [a, b] = m.split(".").map(Number); if (a >= 13) return ge(t, "3.5.0"); if (t === "3.2.0") return b <= 6; return true; };
  const minors = [...new Set(Object.keys(P.nvcc).map(v => v.split(".").slice(0, 2).join(".")))].sort(cmp);
  const cuda = minors.filter(m => accepts(m) && Object.keys(P.nvcc).some(v => v.startsWith(m + ".") && P.nvcc[v].arch.x86_64.sm.includes(name)));
  return { tool, name, banner, ok, env, cuda };
}
(async () => {
  const b = await chromium.launch(); let fail = 0, n = 0; const errs = [];
  const ok = (name, cond, extra) => { n++; if (!cond) { fail++; console.log("FAIL " + name + " :: " + (extra || "")); } };
  const tritons = Object.keys(P.triton).filter(v => ge(v, "3.0.0")).sort(cmp);
  for (const width of [1200, 375]) {
    const pg = await b.newPage({ viewport: { width, height: 900 } });
    pg.on("pageerror", e => errs.push(String(e))); pg.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
    await pg.goto("file://" + path.resolve(page_path));
    for (const t of tritons) for (const cap of [80, 86, 89, 90, 100, 103, 110, 120, 121]) {
      await pg.selectOption("#gpu", String(cap)); await pg.selectOption("#ver", "triton|" + t);
      const big = await pg.textContent("#out .big"), txt = await pg.textContent("#out"); const x = expect(t, cap), id = `w${width} triton ${t} cap ${cap}`;
      ok(id + " verdict", big === (x.ok ? "Bundled ptxas knows " : "Bundled ptxas does not know ") + x.name, big);
      ok(id + " command", txt.includes(`${x.tool} --gpu-name=${x.name}`) && txt.includes(`CUDA ${x.banner} build`), txt.slice(0, 300));
      if (!x.ok) {
        ok(id + " error line", txt.includes(`${x.tool} fatal   : Value '${x.name}' is not defined for option 'gpu-name'`), "");
        if (x.cuda.length) {
          ok(id + " env", txt.includes(x.env + "=/usr/local/cuda/bin/ptxas"), txt);
          ok(id + " cuda range", txt.includes(x.cuda.length === 1 ? `CUDA ${x.cuda[0]} (` : `CUDA ${x.cuda[0]} to ${x.cuda[x.cuda.length - 1]} (`), JSON.stringify(x.cuda));
          ok(id + " hyphen note", txt.includes("contains a hyphen") === x.env.includes("-"), "");
          ok(id + " ignored note", txt.includes("TRITON_PTXAS_PATH has no effect here") === (x.tool === "ptxas-blackwell"), "");
        } else ok(id + " no fix", txt.includes("No environment-variable fix on Triton " + t) && !txt.includes("Fix 2"), txt);
      } else ok(id + " no fix shown when ok", !txt.includes("Fix 1") && !txt.includes("Fix 2"), "");
    }
    // torch and vllm entries resolve to the Triton that PyPI metadata / the page's own table says
    for (const [kind, ver, t] of [["torch", "2.9.0", "3.5.0"], ["torch", "2.6.0", "3.2.0"], ["torch", "2.14.1", "3.8.0"], ["torch", "2.15.0", "3.9.0"], ["vllm", "0.12.0", "3.5.0"], ["vllm", "0.34.0", "3.8.0"], ["vllm", "0.9.0", "3.3.0"]]) {
      await pg.selectOption("#gpu", "121"); await pg.selectOption("#ver", kind + "|" + ver);
      const txt = await pg.textContent("#out"); ok(`w${width} ${kind} ${ver} -> Triton ${t}`, txt.includes("Triton " + t + ". For compute capability 12.1"), txt.slice(0, 200));
      if (kind === "torch") ok(`w${width} torch ${ver} pin in PyPI metadata`, P.torch[ver].triton.replace(/[()\s]/g, "").startsWith("triton" + (t === "3.8.0" || t === "3.9.0" ? "~=" : "==") + t), P.torch[ver].triton);
    }
    // first-fix line for DGX Spark on PyTorch 2.9.0
    await pg.selectOption("#gpu", "121"); await pg.selectOption("#ver", "torch|2.9.0");
    let txt = await pg.textContent("#out");
    ok(`w${width} first fix line`, txt.includes("Triton 3.6.0 is the first release whose bundled binary knows this GPU. That is PyTorch 2.10.0 or newer, or vLLM 0.17.0 or newer."), txt);
    // pasted errors
    const paste = async s => { await pg.evaluate(() => document.querySelector("details").open = true); await pg.fill("#err", s); await pg.click("#errbtn"); return [await pg.inputValue("#gpu"), await pg.inputValue("#ver"), await pg.textContent("#errmsg")]; };
    await pg.selectOption("#ver", "torch|2.9.0");
    let r = await paste("ptxas-blackwell fatal : Value ‘sm_121a’ is not defined for option ‘gpu-name’");
    ok(`w${width} paste curly quotes sm_121a`, r[0] === "121" && r[2].includes("ptxas-blackwell"), JSON.stringify(r));
    r = await paste("ERROR 11-03 18:27:57 [core.py:843] ptxas fatal   : Value 'sm_110a' is not defined for option 'gpu-name'");
    ok(`w${width} paste sm_110a`, r[0] === "110" && r[1] === "torch|2.9.0", JSON.stringify(r));
    r = await paste("ptxas fatal : Value 'sm_120' is not defined for option 'gpu-name'\nRuntimeError: ptxas failed with error code 4294967295");
    ok(`w${width} paste sm_120 without a -> Triton 3.2.0`, r[0] === "120" && r[1] === "triton|3.2.0" && r[2].includes("3.2.0 or older"), JSON.stringify(r));
    r = await paste("Repro command: /usr/local/lib/python3.12/dist-packages/triton/backends/nvidia/bin/ptxas -lineinfo -v --gpu-name=sm_121a /tmp/x.ptx -o /tmp/x.o");
    ok(`w${width} paste repro command`, r[0] === "121", JSON.stringify(r));
    r = await paste("nothing here"); ok(`w${width} paste nothing`, r[2].includes("No sm_NNN"), JSON.stringify(r));
    r = await paste("Value 'sm_75' is not defined"); ok(`w${width} paste unknown gpu`, r[2].includes("not one of the GPUs"), JSON.stringify(r));
    const over = await pg.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    ok(`w${width} no horizontal overflow`, over <= 0, String(over));
    await pg.close();
  }
  ok("no console errors", errs.length === 0, errs.join(" | "));
  console.log(`${n - fail}/${n} checks passed`);
  await b.close(); process.exit(fail ? 1 : 0);
})();
