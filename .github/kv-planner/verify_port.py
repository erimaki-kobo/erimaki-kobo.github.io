"""Compare kvplan.py against vLLM's own planning code on random configurations.

python3 verify_port.py <kvplan dir> <vllm source dir> [count] [seed]
"""
import random
import sys

sys.path.insert(0, sys.argv[1])
import kvplan  # noqa: E402
import real_vllm  # noqa: E402

m = real_vllm.load(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
rng = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 20261117)


def rand_case():
    bs = rng.choice([16, 16, 32, 64, 64, 64, 128])
    heads = rng.choice([1, 2, 4, 8, 16])
    hs = rng.choice([64, 128, 256])
    db = rng.choice([2, 2, 4, 1])
    n = rng.randint(1, 80)
    shape = rng.choice(["full", "full", "mla", "hybrid", "hybrid", "allslide", "twowin"])
    layers = []
    if shape == "full":
        layers = [dict(kind="full", num_kv_heads=heads, head_size=hs, head_size_v=hs,
                       dtype_bytes=db, block_size=bs, sliding_window=None)] * n
    elif shape == "mla":
        layers = [dict(kind="mla", num_kv_heads=1, head_size=rng.choice([576, 320]),
                       head_size_v=0, dtype_bytes=db, block_size=bs,
                       sliding_window=None)] * n
    else:
        w1 = rng.choice([128, 512, 1024, 4096, 1000, 77])
        w2 = rng.choice([256, 2048, 300])
        pat = rng.choice([2, 3, 6, 4])
        for i in range(n):
            if shape == "allslide":
                k, w = "sliding", w1
            elif shape == "twowin":
                k, w = ("sliding", w1 if i % 2 else w2) if (i + 1) % pat else ("full", None)
            else:
                k, w = ("sliding", w1) if (i + 1) % pat else ("full", None)
            layers.append(dict(kind=k, num_kv_heads=heads, head_size=hs, head_size_v=hs,
                               dtype_bytes=db, block_size=bs, sliding_window=w))
    L = rng.choice([1, 17, 512, 2048, 4096, 8192, 32768, 131072, 1000, 40960, 262144])
    infl = rng.choice([2048, 4096, 8192, 16384, 2 * 8192, 1000])
    per_tok = n * heads * hs * 2 * db
    avail = int(per_tok * L * rng.choice([0.0, 0.3, 0.9, 1.0, 1.01, 1.5, 4, 20, 33.3]) *
                rng.random() * 2) + rng.randint(0, 5000)
    return layers, avail, L, infl, rng.random() < 0.25


stats = dict(ok=0, both_refuse=0, mismatch=0, fits=0, nofit=0)
bad = []
for i in range(N):
    layers, avail, L, infl, dis = rand_case()
    r = real_vllm.real_plan(m, layers, avail, L, infl, dis)
    try:
        kl = [kvplan.Layer(l["kind"], l["num_kv_heads"], l["head_size"], l["head_size_v"],
                           l["dtype_bytes"], l["block_size"], l["sliding_window"])
              for l in layers]
        p = kvplan.plan(kl, avail, L, in_flight_tokens=infl, disable_hybrid=dis)
        mine = None
    except kvplan.Unsupported as e:
        p, mine = None, str(e)
    if "error" in r or mine:
        if "error" in r and mine:
            stats["both_refuse"] += 1
        else:
            stats["mismatch"] += 1
            bad.append((i, "refusal", r, mine, dis, len(layers), sorted({(l["kind"], l["sliding_window"]) for l in layers},key=str)))
        continue
    diffs = []
    if r["num_blocks"] != p.num_blocks:
        diffs.append(("num_blocks", r["num_blocks"], p.num_blocks))
    if r["num_blocks"] > 0:
        if r["fits"] != p.fits:
            diffs.append(("fits", r["fits"], p.fits))
        if r.get("tokens") != p.tokens:
            diffs.append(("tokens", r.get("tokens"), p.tokens))
        if abs(r["concurrency"] - p.concurrency) > 1e-12 * max(1, p.concurrency):
            diffs.append(("conc", r["concurrency"], p.concurrency))
        if r["num_groups"] != p.num_groups:
            diffs.append(("groups", r["num_groups"], p.num_groups))
        if not r["fits"] and r.get("est") is not None and r["est"] != p.estimated_max_model_len:
            diffs.append(("est", r["est"], p.estimated_max_model_len))
        stats["fits" if r["fits"] else "nofit"] += 1
    elif p.fits:
        diffs.append(("fits0", False, True))
    if diffs:
        stats["mismatch"] += 1
        bad.append((i, diffs, len(layers), avail, L, infl, dis,
                    sorted({(l["kind"], l["sliding_window"], l["block_size"]) for l in layers},
                           key=str)))
    else:
        stats["ok"] += 1
print(stats)
for b in bad[:8]:
    print(b)
sys.exit(1 if stats["mismatch"] else 0)
