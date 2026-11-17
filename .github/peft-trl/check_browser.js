// Browser checks. usage: node check_browser.js file:///.../index.html
// Expected release numbers were written by hand from an earlier, separately produced table (not from this page's data).
const { chromium } = require(process.env.PW || "playwright");
const URL = process.argv[2];
const J = '{"peft_type":"LORA","r":8,"lora_alpha":16,"use_dora":false,"use_rslora":false,"layer_replication":null,"target_modules":["q_proj"]}';
const J15 = '{"peft_type":"LORA","r":8,"lora_alpha":16,"use_dora":false,"corda_config":null,"trainable_token_indices":null,"lora_bias":false}';
const cases = [   // [name, text, peft, transformers, trl, [must contain], [must not contain]]
  ["lora key, old peft", "TypeError: LoraConfig.__init__() got an unexpected keyword argument 'use_dora'", "0.8.2", "", "", ["Added in PEFT v0.9.0; your 0.8.2 is older", 'pip install -U "peft>=0.9.0"', "1 of 1 arguments will not work"], []],
  ["lora key, new enough", "TypeError: LoraConfig.__init__() got an unexpected keyword argument 'use_dora'", "0.10.0", "", "", ["Accepted by PEFT v0.21.3 (since v0.9.0)", "All 1 arguments are accepted"], ["problem"]],
  ["lora key, no version", "LoraConfig.__init__() got an unexpected keyword argument 'layer_replication'", "", "", "", ["since v0.10.0"], []],
  ["removed lora key", "LoraConfig.__init__() got an unexpected keyword argument 'enable_lora'", "", "", "", ["Removed after PEFT v0.2.0", "Delete the key"], []],
  ["evaluation_strategy", "TypeError: TrainingArguments.__init__() got an unexpected keyword argument 'evaluation_strategy'", "", "", "", ["Removed after Transformers v4.50.3", "eval_strategy", "from v4.41.0"], []],
  ["evaluation_strategy, old tf", "TrainingArguments.__init__() got an unexpected keyword argument 'evaluation_strategy'", "", "4.44.0", "", ["Still accepted by your Transformers 4.44.0"], ["problem"]],
  ["eval_strategy too new", "TrainingArguments.__init__() got an unexpected keyword argument 'eval_strategy'", "", "4.40.0", "", ["Added in Transformers v4.41.0; your 4.40.0 is older"], []],
  ["sft tokenizer", "TypeError: SFTTrainer.__init__() got an unexpected keyword argument 'tokenizer'", "", "", "", ["Removed after TRL v0.15.2", "From v0.12.0 to v0.15.2 it is only a deprecated alias of processing_class", "Use processing_class (from v0.12.0)"], []],
  ["sft dataset_text_field old", "SFTTrainer.__init__() got an unexpected keyword argument 'dataset_text_field'", "", "", "0.11.4", ["Still accepted by your TRL 0.11.4", "removed after v0.12.2"], ["problem"]],
  ["sft dataset_text_field", "SFTTrainer.__init__() got an unexpected keyword argument 'dataset_text_field'", "", "", "", ["Removed after TRL v0.12.2", "SFTConfig"], []],
  ["sftconfig max_seq_length", "TypeError: SFTConfig.__init__() got an unexpected keyword argument 'max_seq_length'", "", "", "", ["Removed after TRL v0.19.1", "max_length", "from v0.16.0"], []],
  ["python call, inherited", 'args = SFTConfig(output_dir="out", evaluation_strategy="steps", max_seq_length=512, learning_rate=2e-4)', "", "", "", ["is not defined by SFTConfig itself", "TrainingArguments argument that SFTConfig inherits", "Removed after Transformers v4.50.3", "Removed after TRL v0.19.1", "2 of 4 arguments will not work", "Inherited from TrainingArguments. Accepted by Transformers"], []],
  ["re-declared then inherited", "SFTConfig.__init__() got an unexpected keyword argument 'neftune_noise_alpha'", "", "", "", ["declared neftune_noise_alpha itself only in TRL v0.9.3 to v0.11.4", "Accepted by Transformers", "since v4.35.0"], ["problem"]],
  ["adapter json", J, "", "", "", ["This LoraConfig file uses keys up to PEFT v0.10.0 (layer_replication)", 'pip install -U "peft>=0.10.0"'], []],
  ["adapter json, old peft", J, "0.8.0", "", "", ["Your PEFT 0.8.0 does not know use_dora, layer_replication", "Before v0.14.0 that is a TypeError", "Added in PEFT v0.9.0", "Added in PEFT v0.10.0", "safe only if it holds its default value"], ["use_rslora", "or remove the argument"]],
  ["adapter json, lenient peft", J15, "0.14.0", "", "", ["uses keys up to PEFT v0.15.0", "Your PEFT 0.14.0 does not know corda_config, trainable_token_indices", "From v0.14.0 PEFT does not stop", "these are ignored"], ["lora_bias"]],
  ["adapter json, ok", J15, "0.15.2", "", "", ["Your PEFT 0.15.2 knows every key"], ["problem"]],
  ["peft warning", "UserWarning: Unexpected keyword arguments ['corda_config', 'trainable_token_indices'] for class LoraConfig, these are ignored.", "0.14.0", "", "", ["Added in PEFT v0.15.0; your 0.14.0 is older", "2 of 2 arguments will not work"], []],
  ["no class name", "TypeError: __init__() got an unexpected keyword argument 'use_rslora'", "", "", "", ["The error line does not name the class", "LoraConfig", "since v0.8.0"], []],
  ["unknown name", "LoraConfig.__init__() got an unexpected keyword argument 'foo_bar'", "", "", "", ["No PEFT release from v0.0.1 to v0.21.3 has an argument foo_bar on LoraConfig"], []],
  ["trainer tokenizer alias", "Trainer.__init__() got an unexpected keyword argument 'tokenizer'", "", "4.50.0", "", ["Still accepted by your Transformers 4.50.0", "deprecated alias of processing_class", "Your version is in that range"], ["problem"]],
  ["trainer tokenizer v5", "Trainer.__init__() got an unexpected keyword argument 'tokenizer'", "", "5.0.0", "", ["Removed after Transformers v4.57.6", "From v4.46.0 to v4.57.6", "Use processing_class (from v4.46.0)"], []],
  ["adalora json", '{"peft_type":"ADALORA","r":8,"target_r":4,"init_r":12,"lora_alpha":8}', "", "", "", ["This AdaLoraConfig file uses keys up to PEFT"], []],
  ["dpo", "DPOConfig.__init__() got an unexpected keyword argument 'max_prompt_length'", "", "", "", ["Removed after TRL v0.28.0", "max_length"], []],
  ["grpo inherited", "GRPOConfig(per_device_train_batch_size=4)", "", "", "", ["inherited TrainingArguments argument", "Accepted by Transformers"], ["problem"]],
  ["group_by_length", "TrainingArguments(group_by_length=True, warmup_ratio=0.1)", "", "", "", ["Removed after Transformers v5.1.0", "train_sampling_strategy", "Removed after Transformers v5.14.1", "warmup_steps"], []],
  ["untracked class", "FooConfig.__init__() got an unexpected keyword argument 'x'", "", "", "", ["FooConfig is not a class this page tracks"], []],
  ["nothing", "hello", "", "", "", ["Found no"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
    await p.goto(URL, { waitUntil: "networkidle" });
    if (await p.locator("h1").count() !== 1) { fail++; console.log("FAIL h1 count"); }
    for (const [name, q, vp, vt, vr, want, not] of cases) {
      await p.fill("#q", q); await p.fill("#vp", vp); await p.fill("#vt", vt); await p.fill("#vr", vr); await p.click("#go");
      const t = (await p.evaluate(() => document.getElementById("res").innerText + " " + document.getElementById("status").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x)); n++;
      if (miss.length || extra.length) { fail++; console.log("FAIL", w, name, "missing", miss, "unwanted", extra, "|", t.slice(0, 700)); }
      const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (over > 0) { fail++; console.log("FAIL overflow after", name, w, over); }
    }
    await p.fill("#filter", "max_");
    const vis = await p.evaluate(() => [...document.querySelectorAll("table.full tbody tr")].filter(r => r.style.display !== "none").length);
    if (!(vis >= 4 && vis < 30)) { fail++; console.log("FAIL filter", vis); }
    const p2 = await b.newPage({ viewport: { width: w, height: 900 } });
    await p2.goto(URL + "?q=" + encodeURIComponent("SFTConfig(max_seq_length=512)") + "&trl=0.19.1#lookup", { waitUntil: "networkidle" });
    const t2 = await p2.textContent("#res"); if (!t2.includes("Still accepted by your TRL 0.19.1")) { fail++; console.log("FAIL url restore", t2.slice(0, 200)); }
  }
  if (errs.length) { fail++; console.log("errors", errs); }
  await b.close();
  console.log(fail ? "FAIL " + fail : "ALL PASS (" + n + " cases)"); process.exit(fail ? 1 : 0);
})();
