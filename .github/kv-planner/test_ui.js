// node test_ui.js <index.html>   (needs: npm i jsdom)  Runs the page and checks what a reader sees.
const fs = require("fs"), {JSDOM} = require("jsdom");
const dom = new JSDOM(fs.readFileSync(process.argv[2], "utf8"), {runScripts: "dangerously"});
const d = dom.window.document, $ = id => d.getElementById(id);
const fire = (id, type) => $(id).dispatchEvent(new dom.window.Event(type, {bubbles: true}));
let fail = 0, n = 0;
const has = (id, text, label) => { n++; if (!$(id).textContent.includes(text)) { fail++; console.log("FAIL", label, "| wanted:", text, "| got:", $(id).textContent.slice(0, 400)); } };
const set = (id, v) => { $(id).value = v; fire(id, "input"); };
// default: v0.34.0 measured
has("out", "GPU KV cache size: 53,568 tokens, Maximum concurrency for 32,768 tokens per request: 1.63x", "default m34");
has("out", "837 of 64 tokens, 8,388,608 bytes each", "m34 blocks");
has("out", "6.54 GiB", "m34 kv memory");
set("len", "131072"); has("out", "Estimated maximum model length 53,504", "m34 refuse"); set("len", "32768");
// estimate, v0.34.0
$("ver").value = "e34"; fire("ver", "change");
n++; if ($("blk").value !== "64" || $("util").value !== "0.92" || !$("trn").disabled) { fail++; console.log("FAIL e34 defaults"); }
has("out", "GPU KV cache size: 46,016 tokens, Maximum concurrency for 32,768 tokens per request: 1.40x", "e34");
// v0.33.0
$("ver").value = "e33"; fire("ver", "change");
n++; if ($("blk").value !== "16" || $("util").value !== "0.92") { fail++; console.log("FAIL e33 defaults"); }
has("out", "GPU KV cache size: 46,032 tokens, Maximum concurrency for 32,768 tokens per request: 1.40x", "e33");
has("out", "2,877 of 16 tokens", "e33 blocks");
// example from a public log (Qwen3-32B TP=2, 33.66 GiB) under v0.33.0 rules
d.querySelector('[data-ex="qwen"]').click();
has("out", "6.73x", "qwen log example");
// back to measured: margin grows with the transient peak
$("ver").value = "m34"; fire("ver", "change"); d.querySelector('[data-ex="llama"]').click();
set("oth", "3"); set("trn", "2");   // resident 15.96, margin 1.5, transient 2 -> 24-15.96-1.5-2 = 4.54
has("out", "4.54 GiB", "m34 margin 0.75 x transient");
set("util", "0.5");                 // budget 12 < resident -> nothing left
has("out", "No available memory for the cache blocks", "m34 low utilization");
set("util", "1.0"); set("kvm", "6.54"); has("out", "53,568 tokens", "kvm override");
set("kvm", "");
// log tab
set("log", "INFO Available KV cache memory: 9.10 GiB\nINFO Memory after warmup: 7.90 GiB free, 0.02 GiB committed to the KV cache, 1.00 GiB kept for transient activations (0.80 GiB allocated at peak, 1.00 GiB of torch reservation growth); 837 KV cache blocks (6.54 GiB) fit within the requested 24.00 GiB. Torch may reserve up to 2.10 GiB.\nINFO GPU KV cache size: 53,568 tokens, Maximum concurrency for 32,768 tokens per request: 1.63x");
has("lout", "837 blocks after warmup", "log warmup line");
has("lout", "KV memory 6.54 GiB", "log uses the committed size");
has("lout", "9.1 GiB was only the reservation before warmup", "log reservation");
set("log", "INFO Available KV cache memory: 16.65 GiB\nINFO GPU KV cache size: 155,904 tokens\nINFO Maximum concurrency for 40,960 tokens per request: 3.81x");
has("lout", "3.81x", "old log");
set("log", "<img src=x onerror=alert(1)> Available KV cache memory: 1.00 GiB");
n++; if ($("lout").querySelector("img")) { fail++; console.log("FAIL escape"); }
console.log(JSON.stringify({checks: n, failed: fail}));
process.exit(fail ? 1 : 0);
