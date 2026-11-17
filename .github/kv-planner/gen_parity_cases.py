#!/usr/bin/env python3
"""Random inputs with kvplan.py's answers, for test_parity.js.
python3 gen_parity_cases.py <dir with kvplan.py> <count> <seed> > cases.json"""
import json, math, random, sys
sys.path.insert(0, sys.argv[1])
import kvplan
n, rng = int(sys.argv[2]), random.Random(int(sys.argv[3]))
GIB = kvplan.GIB
cases = []
def cfg():
    t = rng.choice(["llama", "qwen3", "mistral", "gemma3", "gemma2", "gpt_oss", "deepseek_v3", "phi3", "mamba"])
    c = {"model_type": t, "hidden_size": rng.choice([2048, 2560, 4096, 5120]),
         "num_hidden_layers": rng.randint(1, 80), "num_attention_heads": rng.choice([8, 16, 32, 64])}
    if rng.random() < .7: c["num_key_value_heads"] = rng.choice([1, 2, 4, 8, 16])
    if rng.random() < .4: c["head_dim"] = rng.choice([64, 128, 256])
    if rng.random() < .5: c["sliding_window"] = rng.choice([128, 512, 1024, 4096, None])
    if rng.random() < .3: c["max_position_embeddings"] = rng.choice([4096, 32768, 131072])
    if t == "deepseek_v3" and rng.random() < .8:
        c["kv_lora_rank"], c["qk_rope_head_dim"] = 512, 64
    if t == "gemma3":
        if rng.random() < .5: c["sliding_window_pattern"] = rng.choice([2, 6, 3])
        c = {"model_type": "gemma3", "text_config": dict(c, model_type="gemma3_text")}
    if t == "qwen3" and rng.random() < .3: c["use_sliding_window"] = True
    return c
for i in range(n):
    c = cfg()
    tp = rng.choice([1, 1, 2, 4]); kvd = rng.choice(["auto", "fp8", "float32"])
    bs = rng.choice([16, 64, 64, 32]); L = rng.choice([512, 4096, 32768, 131072, 1000])
    infl = rng.choice([2048, 4096, 16384]); dis = rng.random() < .2
    total = rng.randint(8, 160) * GIB; util = rng.choice([1.0, 0.92, 0.9, 0.5])
    wts = int(rng.random() * 0.8 * total); oth = int(rng.random() * 4 * GIB)
    trn = min(int(rng.random() * 3 * GIB), oth)
    measured = rng.random() < .5
    case = {"cfg": c, "tp": tp, "kvd": kvd, "bs": bs, "L": L, "infl": infl, "dis": dis,
            "total": total, "util": util, "wts": wts, "oth": oth, "trn": trn, "measured": measured}
    try:
        shape = kvplan.read_config(c)
        layers = kvplan.build_layers(shape, tensor_parallel=tp, kv_dtype=kvd, block_size=bs)
        if measured:
            avail = kvplan.measured_kv_memory_bytes(math.ceil(total * util), total, wts + oth - trn, trn)
        else:
            avail = kvplan.kv_memory_bytes(total, util, wts + oth)
        case["avail"] = avail
        if avail > 0:
            p = kvplan.plan(layers, avail, L, in_flight_tokens=infl, disable_hybrid=dis)
            case["plan"] = [p.num_blocks, p.block_bytes, p.blocks_per_request, p.tokens, p.fits,
                            p.estimated_max_model_len, p.num_groups, p.padding_layers,
                            round(p.concurrency, 9)]
            case["typ"] = kvplan.requests_that_fit(layers, p.num_blocks, min(4096, L),
                                                   in_flight_tokens=infl, disable_hybrid=dis)
    except kvplan.Unsupported as e:
        case["unsupported"] = True
    cases.append(case)
LOGS = [
 "INFO Available KV cache memory: 16.65 GiB\nINFO GPU KV cache size: 155,904 tokens\nINFO Maximum concurrency for 40,960 tokens per request: 3.81x",
 "INFO Available KV cache memory: 9.10 GiB\nINFO Memory after warmup: 7.90 GiB free, 0.02 GiB committed to the KV cache, 1.00 GiB kept for transient activations (0.80 GiB allocated at peak, 1.00 GiB of torch reservation growth); 837 KV cache blocks (6.54 GiB) fit within the requested 24.00 GiB. Torch may reserve up to 2.10 GiB.\nINFO GPU KV cache size: 53,568 tokens, Maximum concurrency for 32,768 tokens per request: 1.63x",
 "ValueError: To serve at least one request with the model's max seq len (131072), (16.00 GiB KV cache is needed, which is larger than the available KV cache memory (6.54 GiB). Based on the available memory, the estimated maximum model length is 53504. The extensible KV cache already takes all device memory",
 "ValueError: Free memory on device cuda:0 (10.5/24.0 GiB) on startup is less than desired GPU memory utilization (0.92, 22.08 GiB). Decrease GPU memory utilization",
 "# GPU blocks: 3409, # CPU blocks: 0", "reserved 12.5 GiB memory for KV Cache as specified by kv_cache_memory_bytes config",
 "nothing here", "INFO Model loading took 14.96 GiB memory and 3.1 seconds\nINFO Available KV cache memory: 5.62 GiB",
]
logs = []
for t in LOGS:
    for a, l in [(None, None), (20.0, None), (None, 8192), (3.5, 65536)]:
        d = kvplan.parse_log(t)
        r = kvplan.from_log(d, new_available_gib=a, new_max_model_len=l)
        logs.append({"text": t, "a": a, "l": l, "parsed": d, "res": r})
json.dump({"cases": cases, "logs": logs}, sys.stdout)
