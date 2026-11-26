// node test_parser.mjs : parser, diff and data sampling on the files from make_test_files.py,
// and the metadata round trip with gguf-new-metadata / gguf-set-metadata (run test_roundtrip.sh first).
import fs from "fs"; import assert from "assert";
globalThis.window = globalThis; await import("./ggufhist.js");
const f = p => new File([fs.readFileSync(p)], p);
const [a, b, c] = ["a.gguf", "b.gguf", "c.gguf"].map(f);
const ha = await GH.header(a, { first: 1024 }), hb = await GH.header(b), hc = await GH.header(c);
assert.equal(ha.tensors.length, 20); assert.equal(ha.kv["tokenizer.chat_template"].value, "{{ x }}");
const d = GH.diff(ha, hb);
assert.deepEqual(d.kv.map(k => k.key), ["tokenizer.chat_template", "tokenizer.ggml.add_bos_token"]); assert.ok(d.layoutSame);
assert.ok((await GH.sameData(a, ha, b, hb)).every(x => x.same));
assert.ok((await GH.sameData(a, ha, c, hc)).every(x => !x.same));
if (fs.existsSync("a3.gguf")) {
  const p = f("a3.gguf"), hp = await GH.header(p);
  assert.equal(GH.diff(hp, hb).kv.length, 0, "patched file still differs");
  assert.ok((await GH.sameData(p, hp, b, hb)).every(x => x.same));
  console.log("round trip ok");
}
console.log("parser tests ok");
