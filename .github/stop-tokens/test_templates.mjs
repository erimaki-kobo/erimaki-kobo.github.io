import { Template } from "./jinja-0.5.13.js";
import fs from "fs";
await import("./stopcheck.js");
const dir = process.argv[2]; let ok = 0, err = 0, none = 0;
for (const f of fs.readdirSync(dir).sort()) {
  const T = fs.readFileSync(dir + "/" + f, "utf8");
  // pseudo token table: every <...>-like literal in the template source
  const toks = [...new Set((T.match(/<[|｜\[]?[^<>\s'"{}]{1,40}[|｜\]]?>|\[[A-Z_~\[]{2,12}\]|\[e~\[|<\/s>/g) || []))];
  const tok = { eos_token: "</s>", bos_token: "<s>", chat_template: T, added_tokens_decoder: Object.fromEntries(toks.map((t, i) => [String(1000 + i), { content: t }])) };
  const r = StopCheck.analyze({ config: {}, gen: null, tok }, { tag: "b0", eot: [], eom: [], fim_pad: [], fim_rep: [], fim_sep: [], eog: [] }, (t, c) => new Template(t).render(Object.assign({}, c)));
  const after = r.render.after !== undefined ? JSON.stringify(r.render.after.slice(0, 24)) : r.render.why;
  const m = r.marker ? (r.marker.text || "(none)") + (r.marker.src === "harmony" ? " [harmony]" : "") : "-";
  if (r.render.status !== "ok") err++; else if (r.marker && r.marker.text) ok++; else none++;
  console.log(f.padEnd(52), m.padEnd(26), after);
}
console.log({ ok, none, err });
