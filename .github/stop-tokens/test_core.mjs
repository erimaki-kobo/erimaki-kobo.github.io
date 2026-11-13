import { Template } from "./jinja-0.5.13.js";
import fs from "fs";
await import("./stopcheck.js");
const SC = globalThis.StopCheck;
const LL = JSON.parse(fs.readFileSync("out/llama_eog.json", "utf8"));
const render = (t, ctx) => new Template(t).render(ctx);
const L3T = "{% set loop_messages = messages %}{% for message in loop_messages %}{% set content = '<|start_header_id|>' + message['role'] + '<|end_header_id|>\n\n'+ message['content'] | trim + '<|eot_id|>' %}{% if loop.index0 == 0 %}{% set content = bos_token + content %}{% endif %}{{ content }}{% endfor %}{% if add_generation_prompt %}{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' }}{% endif %}";
const l3tok = (eos) => ({ eos_token: eos, bos_token: "<|begin_of_text|>", chat_template: L3T, added_tokens_decoder: { "128000": { content: "<|begin_of_text|>" }, "128001": { content: "<|end_of_text|>" }, "128006": { content: "<|start_header_id|>" }, "128007": { content: "<|end_header_id|>" }, "128008": { content: "<|eom_id|>" }, "128009": { content: "<|eot_id|>" } } });
const QT = "{% for m in messages %}{{ '<|im_start|>' + m.role + '\n' + m.content + '<|im_end|>' + '\n' }}{% endfor %}";
const qtok = { eos_token: "<|im_end|>", chat_template: QT, added_tokens_decoder: { "151643": { content: "<|endoftext|>" }, "151644": { content: "<|im_start|>" }, "151645": { content: "<|im_end|>" } } };
const cases = [
  ["llama3 original", { config: { eos_token_id: 128001 }, gen: { eos_token_id: [128001, 128009] }, tok: l3tok("<|end_of_text|>") },
    { marker: "<|eot_id|>", transformers: "stops", vllm: "stops", sglang: "stops", mlx: "stops", llamacpp: "stops" }],
  ["llama3 no gen config", { config: { eos_token_id: 128001 }, gen: null, tok: l3tok("<|end_of_text|>") },
    { marker: "<|eot_id|>", transformers: "runs-on", vllm: "runs-on", sglang: "runs-on", mlx: "runs-on", llamacpp: "stops" }],
  ["llama3 gen without eos", { config: { eos_token_id: 128001 }, gen: { do_sample: true }, tok: l3tok("<|end_of_text|>") },
    { transformers: "runs-on", vllm: "runs-on" }],
  ["qwen base-style eos", { config: { eos_token_id: 151643 }, gen: { eos_token_id: 151643 }, tok: Object.assign({}, qtok, { eos_token: "<|endoftext|>" }) },
    { marker: "<|im_end|>", transformers: "runs-on", vllm: "runs-on", sglang: "runs-on", mlx: "runs-on", llamacpp: "stops" }],
  ["qwen instruct", { config: { eos_token_id: 151645 }, gen: { eos_token_id: [151645, 151643] }, tok: qtok },
    { marker: "<|im_end|>", transformers: "stops", vllm: "stops", llamacpp: "stops" }],
  ["ollama string", { config: { eos_token_id: 151643 }, gen: null, tok: Object.assign({}, qtok, { eos_token: "<|endoftext|>" }), modelfile: 'PARAMETER stop "<|im_end|>"', llamalog: "load: printing all EOG tokens:\nload:   - 151643 ('<|endoftext|>')\n" },
    { llamacpp: "runs-on", ollama: "stops-string" }],
  ["multimodal text_config", { config: { text_config: { eos_token_id: 128009 } }, gen: null, tok: l3tok("<|end_of_text|>") },
    { transformers: "stops", vllm: "stops", sglang: "runs-on", mlx: "runs-on" }],
];
let fail = 0;
for (const [name, F, want] of cases) {
  const r = SC.analyze(F, LL, render);
  const got = { marker: r.marker && r.marker.text };
  for (const k of Object.keys(r.engines)) got[k] = r.engines[k].verdict;
  for (const [k, v] of Object.entries(want)) if (got[k] !== v) { fail++; console.log("FAIL", name, k, "want", v, "got", got[k], r.render); }
}
console.log(fail ? fail + " FAIL" : "ALL PASS");
