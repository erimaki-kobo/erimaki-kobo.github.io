#!/usr/bin/env python3
"""Bring en/vllm-kv-concurrency-planner/index.html from v0.33.0 to v0.34.0 (one-off, 2026-11-17).

Usage: python3 -I patch_v0.34.0.py <repository root>
Every replacement asserts how many times its target occurs, so it stops on a page that is not the
2026-11-17 one. After this the published page is its own template: edit it directly and run the checks
in README.md. kvplan.py next to the page was edited by hand in the same commit.
"""
import re
import sys
from pathlib import Path

p = Path(sys.argv[1]) / "en/vllm-kv-concurrency-planner/index.html"
s = p.read_text(encoding="ascii")
assert 'id="v034"' in s and 'id="ver"' not in s, "not the page this patch was written for"
done = 0


def rep(old, new, count=1):
    global s, done
    assert s.count(old) == count, (s.count(old), count, old[:90])
    s = s.replace(old, new)
    done += count


# ---------------------------------------------------------------- library (kvplan.js inside the page)
rep('''      if (hasS && hasF) {
        var wins = {};
        layers.forEach(function (l) { if (l.kind === "sliding") wins[l.slidingWindow] = 1; });
        if (Object.keys(wins).length > 1)
          throw new Unsupported("two sliding-window sizes with the hybrid KV cache manager disabled");
''', '''      var wins = {};
      layers.forEach(function (l) { if (l.kind === "sliding") wins[l.slidingWindow] = 1; });
      if (Object.keys(wins).length > 1)
        throw new Unsupported("two sliding-window sizes with the hybrid KV cache manager disabled");
      if (hasS && hasF) {
''')
rep('''  function defaultBatch(totalGib, deviceName, serve, cc) {''',
    '''  // v0.34.0 extensible KV cache: measure_kv_cache_bytes with nothing committed yet
  function measuredKvMemoryBytes(requestedBytes, initFreeBytes, residentBytes, transientBytes,
      growthBytes, marginFloorBytes, marginFraction) {
    var floor = has(marginFloorBytes) ? marginFloorBytes : GIB;
    var frac = has(marginFraction) ? marginFraction : 0.75;
    var headroom = initFreeBytes - residentBytes;
    var margin = Math.max(floor, Math.floor(transientBytes * frac));
    var available = Math.min(requestedBytes - residentBytes, headroom - margin);
    available -= Math.max(transientBytes, growthBytes || 0);
    return Math.max(available, 0);
  }
  function defaultBatch(totalGib, deviceName, serve, cc) {''')
rep('''    v0_kv_gib: /memory reserved for KV Cache is ([\\d.]+) ?GiB/
  };''', '''    v0_kv_gib: /memory reserved for KV Cache is ([\\d.]+) ?GiB/,
    after_warmup: /(\\d+) KV cache blocks \\(([\\d.]+) GiB\\) fit within the requested ([\\d.]+) GiB/
  };''')
rep('''      } else if (key === "tokens" || key === "gpu_blocks" || key === "est_max_len")''',
    '''      } else if (key === "after_warmup") {
        out.warmup_blocks = parseInt(g[0], 10); out.warmup_gib = parseFloat(g[1]);
        out.requested_gib = parseFloat(g[2]);
      } else if (key === "tokens" || key === "gpu_blocks" || key === "est_max_len")''')
rep('''    if (!("available_gib" in out) && "reserved_gib" in out) out.available_gib = out.reserved_gib;''',
    '''    if ("warmup_gib" in out) {
      out.reserved_before_warmup_gib = "available_gib" in out ? out.available_gib : null;
      out.available_gib = out.warmup_gib;
    }
    if (!("available_gib" in out) && "reserved_gib" in out) out.available_gib = out.reserved_gib;''')
rep('''VLLM_VERSION: "v0.33.0", readConfig''', '''VLLM_VERSION: "v0.34.0", readConfig''')
rep('''kvMemoryBytes: kvMemoryBytes, defaultBatch''',
    '''kvMemoryBytes: kvMemoryBytes, measuredKvMemoryBytes: measuredKvMemoryBytes, defaultBatch''')

# ---------------------------------------------------------------- form
rep('''<div class="grid">
<div><label for="gpu">Memory of one GPU''', '''<div class="grid">
<div><label for="ver">vLLM version and how the KV cache is sized</label><select id="ver"><option value="m34">v0.34.0: measured after warmup (default on CUDA and ROCm)</option><option value="e34">v0.34.0: estimate (--no-enable-extensible-kv-cache, other platforms)</option><option value="e33">v0.33.0 and earlier</option></select></div>
<div><label for="gpu">Memory of one GPU''')
rep('''<input id="util" inputmode="decimal" value="0.92">''', '''<input id="util" inputmode="decimal" value="1.0">''')
rep('''<div><label for="kvm">or: KV memory, GiB (overrides the four above)</label>''',
    '''<div><label for="trn">of which transient activation peak, GiB (v0.34.0 measured sizing only)</label><input id="trn" inputmode="decimal" value="1.0"></div>
<div><label for="kvm">or: KV memory, GiB (overrides the five above)</label>''')
rep('''<input id="blk" inputmode="numeric" value="16">''', '''<input id="blk" inputmode="numeric" value="64">''')
rep('''placeholder="INFO [gpu_worker.py] Available KV cache memory: 16.65 GiB&#10;''',
    '''placeholder="INFO [extensible_kv_cache.py] Memory after warmup: ... 837 KV cache blocks (6.54 GiB) fit within the requested 24.00 GiB. (v0.34.0)&#10;INFO [gpu_worker.py] Available KV cache memory: 16.65 GiB&#10;''')
rep('''<label for="log">Startup log, or just the lines with "Available KV cache memory" and "GPU KV cache size" (or the startup error)</label>''',
    '''<label for="log">Startup log, or just the lines with "Available KV cache memory" (v0.34.0: "Memory after warmup") and "GPU KV cache size", or the startup error</label>''')

# ---------------------------------------------------------------- UI script
rep('''        blockSize: Math.max(1, Math.floor(num("blk") || 16))});''',
    '''        blockSize: Math.max(1, Math.floor(num("blk") || VER[$("ver").value].blk))});''')
rep('''    var total = num("gpu"), util = num("util") || 0.92, kvm = num("kvm"), avail, how;''',
    '''    var mode = $("ver").value;
    var total = num("gpu"), util = num("util") || VER[mode].util, kvm = num("kvm"), avail, how;''')
rep('''      var nonKv = ((num("wts") || 0) + (num("oth") || 0)) * GIB;
      avail = K.kvMemoryBytes(Math.floor(total * GIB), util, Math.floor(nonKv));
      how = "ceil(" + total + " &times; " + util + ") &minus; " + (num("wts") || 0) + " &minus; " + (num("oth") || 0) + " GiB";''',
    '''      var nonKv = ((num("wts") || 0) + (num("oth") || 0)) * GIB;
      if (mode === "m34") {
        var trn = Math.min(num("trn") || 0, num("oth") || 0);
        var totalB = Math.floor(total * GIB), trnB = Math.floor(trn * GIB);
        avail = K.measuredKvMemoryBytes(Math.ceil(totalB * util), totalB, Math.floor(nonKv) - trnB, trnB);
        how = "min(budget &minus; resident, free &minus; resident &minus; margin) &minus; transient peak: budget ceil(" + total + " &times; " + util +
          "), resident " + (num("wts") || 0) + " + " + ((num("oth") || 0) - trn).toFixed(2).replace(/\\.?0+$/, "") + ", transient " + trn +
          ", margin " + Math.max(1, 0.75 * trn).toFixed(2).replace(/\\.?0+$/, "") + " GiB; vLLM logs the real figure as <code>Memory after warmup</code>";
      } else {
        avail = K.kvMemoryBytes(Math.floor(total * GIB), util, Math.floor(nonKv));
        how = "ceil(" + total + " &times; " + util + ") &minus; " + (num("wts") || 0) + " &minus; " + (num("oth") || 0) + " GiB";
      }''')
rep('''    if ("available_gib" in d) seen.push("KV memory " + d.available_gib + " GiB");''',
    '''    if ("warmup_blocks" in d) seen.push(fmt(d.warmup_blocks) + " blocks after warmup (v0.34.0 measured sizing" +
      (d.reserved_before_warmup_gib !== null ? "; " + d.reserved_before_warmup_gib + " GiB was only the reservation before warmup" : "") + ")");
    if ("available_gib" in d) seen.push("KV memory " + d.available_gib + " GiB");''')
rep('''  var EXAMPLES = {''', '''  var VER = {m34: {blk: 64, util: "1.0"}, e34: {blk: 64, util: "0.92"}, e33: {blk: 16, util: "0.92"}};
  var EXAMPLES = {''')
rep('''  ["cfg", "gpu", "util", "wts", "oth", "kvm", "len", "tp", "kvd", "mbt", "asy", "hyb", "typ", "blk"].forEach(function (id) {''',
    '''  $("ver").addEventListener("change", function () {
    var v = VER[$("ver").value];
    $("blk").value = v.blk; $("util").value = v.util; $("trn").disabled = $("ver").value !== "m34";
    runConfig();
  });
  ["cfg", "gpu", "util", "wts", "oth", "trn", "kvm", "len", "tp", "kvd", "mbt", "asy", "hyb", "typ", "blk"].forEach(function (id) {''')

# ---------------------------------------------------------------- text
m = re.search(r'<p class="lede">.*?</p>\n<p>The planner below.*?</p>\n<p class="meta">Published 2026-11-12.*?</p>\n<p class="note" id="v034">.*?</p>', s, re.S)
assert m
s = s[:m.start()] + '''<p class="lede"><strong>vLLM answers this at startup, and you can compute the same number before you launch.</strong> It takes <code>total GPU memory &times; gpu_memory_utilization</code>, keeps what the weights, the activations and the CUDA graphs need, cuts what is left into blocks of 64 tokens (16 up to v0.33.0), and logs <code>GPU KV cache size: N tokens, Maximum concurrency for L tokens per request: X.XXx</code>. X is the number of blocks divided by the blocks one request of <code>max_model_len</code> tokens needs. Lowering <code>--max-model-len</code> does not free memory; it only raises X. How many requests really run together is capped separately by <code>--max-num-seqs</code> (256 or 1,024 by default).</p>
<p>The planner below runs that calculation in your browser, from a <code>config.json</code> before launch or from a startup log afterwards. It follows vLLM v0.34.0 and, with the version switch, v0.33.0 and earlier. It uses vLLM's layer grouping, so it also gets models with sliding-window layers right (Gemma 2 and 3, gpt-oss), where "bytes per token &times; context" overshoots by a factor of two or more.</p>
<p class="meta">Published 2026-11-12 &middot; Corrected 2026-11-14: two rows of the version table (v0.8.4, v0.20.0) &middot; Updated 2026-11-17: follows vLLM v0.34.0 (2026-11-16), with a switch for v0.33.0 and earlier &middot; Agrees with vLLM's own planning code on 40,000 random configurations for each of the two releases and with 8 public startup logs (<a href="#checked">details</a>) &middot; Tool version 1.1.0 &middot; <a href="#limits">no GPU run by us</a></p>
<p class="note" id="v034"><strong>What v0.34.0 changed.</strong> A block is 64 tokens instead of 16 (PR #63231). On CUDA and ROCm the "extensible KV cache" is on by default: the cache is sized from the memory that is actually free after CUDA graph capture and warmup, not from an estimate, and <code>gpu_memory_utilization</code>, when not given, is 1.0 instead of 0.92. <code>--no-enable-extensible-kv-cache</code>, <code>--kv-cache-memory-bytes</code>, <code>--num-gpu-blocks-override</code>, other platforms and some KV connectors keep the estimate and 0.92. The grouping of layers and the blocks one request needs are the same code as in v0.33.0.</p>''' + s[m.end():]
done += 1

m = re.search(r'<p><strong>Seven steps, all visible in the v0\.33\.0 source\.</strong>.*?</ol>', s, re.S)
assert m
B = "https://github.com/vllm-project/vllm/blob/v0.34.0/vllm/"
s = s[:m.start()] + f'''<p><strong>Seven steps, all visible in the v0.34.0 source.</strong> The example is the planner's default: Llama-3.1-8B in bf16 on a 24 GiB GPU with nothing else on it, 14.96 GiB of weights, and an assumed 1.5 GiB for activations and CUDA graphs, 1.0 GiB of it a transient peak.</p>
<ol class="steps">
<li><strong>Budget</strong> = ceil(total memory &times; <code>gpu_memory_utilization</code>). It is a share of the total, not of what is free. With the extensible KV cache the default is 1.0 and the budget is only a cap; with estimate-based sizing (and in every release up to v0.33.0) the default is 0.92, and if less than the budget is free, startup stops with <code>Free memory on device ... is less than desired GPU memory utilization</code> (<a href="{B}v1/worker/utils.py">worker/utils.py</a>, <a href="{B}config/cache.py">config/cache.py</a>). Example: 24 &times; 1.0 = 24 GiB; up to v0.33.0, 24 &times; 0.92 = 22.08 GiB.</li>
<li><strong>KV memory.</strong> With the extensible KV cache, vLLM measures after CUDA graph capture and warmup: min(budget &minus; resident, free at startup &minus; resident &minus; margin) &minus; transient peak, where resident is what stays allocated (weights, CUDA graphs, workspaces), the margin is max(1 GiB, 0.75 &times; transient peak) (3 GiB floor on ROCm), and the transient peak is the larger of the measured activation peak and the growth of PyTorch's reservation. It logs <code>Memory after warmup: ... N KV cache blocks (X GiB) fit within the requested ...</code>; the earlier <code>Available KV cache memory</code> line is only the address range reserved before warmup (<a href="{B}v1/worker/extensible_kv_cache.py">extensible_kv_cache.py</a>). Example: min(24 &minus; 15.46, 24 &minus; 15.46 &minus; 1) &minus; 1 = 6.54 GiB. With estimate-based sizing: budget &minus; weights &minus; activation peak of a profiling pass &minus; estimated CUDA graph memory, which is the <code>Available KV cache memory</code> line (<a href="{B}v1/worker/gpu_worker.py">gpu_worker.py</a>); up to v0.33.0, 22.08 &minus; 14.96 &minus; 1.5 = 5.62 GiB. <code>--kv-cache-memory-bytes</code> sets it directly.</li>
<li><strong>One page</strong> is one block of one layer: KV heads &times; (key dims + value dims) &times; bytes per element &times; block size (64 tokens; 16 up to v0.33.0). With tensor parallel, each GPU holds max(1, KV heads &divide; TP) heads (<a href="{B}v1/kv_cache_interface.py">kv_cache_interface.py</a>, <a href="{B}config/model.py">config/model.py</a>). Example: 8 &times; 256 &times; 2 &times; 64 = 262,144 bytes.</li>
<li><strong>Layers are put into groups</strong> that share a block table, and one block holds the pages of the widest group. A model whose layers are all alike is one group (<a href="{B}v1/core/kv_cache_planning.py">kv_cache_planning.py</a>). Example: 32 layers &times; 262,144 = 8,388,608 bytes per block, which is 128 KiB per token.</li>
<li><strong>Blocks</strong> = KV memory // bytes per block. Example: 837 blocks (2,877 blocks of 16 tokens from 5.62 GiB up to v0.33.0).</li>
<li><strong>Blocks one full-length request needs</strong>: ceil(L &divide; block size) for a full-attention group; for a sliding-window group, ceil(min(window &minus; 1 + tokens in flight, L) &divide; block size) + 1, where tokens in flight = concurrent batches (2 with async scheduling, the default) &times; <code>max_num_batched_tokens</code>. Example at L = 32,768: 512 blocks.</li>
<li><strong>Maximum concurrency</strong> = blocks &divide; blocks per request, and <code>GPU KV cache size</code> = int(concurrency &times; L) tokens. One block is the permanently reserved null block: if a single request does not fit in the rest, startup stops and prints an estimated maximum model length. Example: 53,568 tokens, 1.63x at 32,768; 6.54x at 8,192; at 131,072 it refuses to start and estimates 53,504. Up to v0.33.0 the same GPU gives 46,032 tokens and 1.40x at 32,768.</li>
</ol>''' + s[m.end():]
done += 1

rep('''in <a href="https://github.com/vllm-project/vllm/blob/v0.33.0/vllm/engine/arg_utils.py">arg_utils.py</a>, v0.33.0):''',
    '''in <a href="https://github.com/vllm-project/vllm/blob/v0.34.0/vllm/engine/arg_utils.py">arg_utils.py</a>; the function is the same code in v0.33.0 and v0.34.0):''')

m = re.search(r'<li><strong>vLLM v0\.33\.0\'s planning code\.</strong>.*?</li>\n<li><strong>The browser version</strong>.*?</li>', s, re.S)
assert m
s = s[:m.start()] + '''<li><strong>vLLM's planning code, v0.33.0 and v0.34.0.</strong> The unmodified source files <code>kv_cache_interface.py</code> and <code>kv_cache_planning.py</code>, plus the capacity functions of <code>kv_cache_utils.py</code>, were run with PyTorch replaced by a stub that only knows dtype sizes. On 40,000 random configurations per release (full attention, MLA, interleaved sliding window with one or two window sizes, all-sliding; hybrid manager on and off; 1 to 80 layers; blocks of 16, 32, 64 and 128 tokens) the planner returned the same block count, token capacity, concurrency, group count, start-or-refuse decision and estimated maximum model length. The harness was written again for v0.34.0, independently of the one used on 2026-11-12, and it found one difference, now fixed: with <code>--disable-hybrid-kv-cache-manager</code>, a model whose layers are all sliding-window with two different window sizes is refused by vLLM, and the planner used to compute it.</li>
<li><strong>v0.34.0's measured sizing.</strong> <code>measure_kv_cache_bytes</code>, taken from <code>extensible_kv_cache.py</code> as it is, returns the same bytes as the planner on 20,000 random inputs. What the planner cannot know is the input: how much stays resident and how large the transient peak is on your GPU.</li>
<li><strong>The browser version</strong> returns the same results as <code>kvplan.py</code> on 6,032 random inputs (config.json files with both sizing modes, and log lines).</li>''' + s[m.end():]
done += 1

rep('''<p class="note">The T4 logs are from an older engine that prints blocks; capacity there is blocks &times; 16.''',
    '''<p class="note">All eight logs are from releases before v0.34.0, so the planner column is the "v0.33.0 and earlier" setting (blocks of 16 tokens). We have not found a public v0.34.0 startup log yet. The T4 logs are from an older engine that prints blocks; capacity there is blocks &times; 16.''')
m = re.search(r'<tr><td>v0\.34\.0 \(2026-11\)</td><td>.*?</td></tr>', s, re.S)
assert m
s = s[:m.start()] + '''<tr><td>v0.34.0 (2026-11)</td><td>default block 16 &rarr; 64 tokens; the extensible KV cache is on by default on CUDA and ROCm and sizes the cache from the memory free after CUDA graph capture and warmup (new log line <code>Memory after warmup</code>); default <code>gpu_memory_utilization</code> is 1.0 with it, 0.92 without; with it, less free memory than the budget no longer stops startup; the "does not fit" error ends with a different hint</td></tr>''' + s[m.end():]
done += 1
rep('''On older releases the config tab can differ for sliding-window models; the log tab does not depend on the version.''',
    '''On releases older than v0.26.0 the config tab can differ for sliding-window models; the log tab does not depend on the version.''')
rep('''the non-KV memory (activation peak, CUDA graphs) is your input, because vLLM measures it rather than computes it. Start once, read <code>Available KV cache memory</code>, and put it in the "KV memory" field.''',
    '''the non-KV memory (activation peak, CUDA graphs) is your input, because vLLM measures it rather than computes it. Start once, read <code>Memory after warmup: ... KV cache blocks (X GiB)</code> (v0.34.0 with the extensible KV cache) or <code>Available KV cache memory</code> (estimate-based sizing and older releases), and put it in the "KV memory" field.''')
rep('''<li>Attention backends can raise the block size above 16 for some head sizes.''',
    '''<li>With the extensible KV cache the final block count is also capped by the address range reserved before warmup, and with several GPUs every rank uses the smallest count; the planner computes one GPU and does not model the reservation.</li>
<li>Attention backends can raise the block size above the default for some head sizes.''')
# FAQ: the same sentences are in the JSON-LD
rep('''cut into blocks of 16 tokens. For a full-attention model one request needs ceil(max_model_len / 16) blocks.''',
    '''cut into blocks of 64 tokens (16 up to v0.33.0). For a full-attention model one request needs ceil(max_model_len / block size) blocks. From v0.34.0 on CUDA and ROCm the memory is measured after warmup instead of estimated, and gpu_memory_utilization defaults to 1.0.''', 2)
rep('''<li>vLLM v0.33.0 source: ''', '''<li>vLLM v0.34.0 source: <a href="https://github.com/vllm-project/vllm/blob/v0.34.0/vllm/v1/worker/extensible_kv_cache.py">v1/worker/extensible_kv_cache.py</a> (<code>measure_kv_cache_bytes</code>, margins), <a href="https://github.com/vllm-project/vllm/blob/v0.34.0/vllm/config/cache.py">config/cache.py</a> (block size, <code>resolved_gpu_memory_utilization</code>), <a href="https://github.com/vllm-project/vllm/blob/v0.34.0/vllm/config/vllm.py">config/vllm.py</a> (when the extensible KV cache is on), <a href="https://github.com/vllm-project/vllm/blob/v0.34.0/docs/configuration/optimization.md">docs/configuration/optimization.md</a> (GPU Memory Utilization).</li>
<li>vLLM v0.33.0 source: ''')
rep('''<code>python kvplan.py plan --config config.json --gpu-gib 24 --weights-gib 14.96 --max-model-len 32768</code> or''',
    '''<code>python kvplan.py plan --config config.json --gpu-gib 24 --weights-gib 14.96 --max-model-len 32768</code> (add <code>--vllm-version 0.33</code> for v0.33.0 and earlier) or''')
rep('''following the layer grouping of vLLM v0.33.0''', '''following vLLM v0.34.0 and v0.33.0''')
rep('''"softwareVersion": "1.0.0"''', '''"softwareVersion": "1.1.0"''', 2)

s.encode("ascii")
p.write_text(s, encoding="ascii")
print("replacements:", done)
