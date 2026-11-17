"""Compare kvplan.measured_kv_memory_bytes with vLLM's measure_kv_cache_bytes
(taken from the v0.34.0 source by name; a pure function).
python3 verify_measured.py <kvplan dir> <extensible_kv_cache.py> [count]"""
import ast, random, sys
sys.path.insert(0, sys.argv[1])
import kvplan
src = open(sys.argv[2]).read()
fn = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)
      and n.name == "measure_kv_cache_bytes"]
assert len(fn) == 1
ns = {"KV_CACHE_MARGIN_FLOOR_BYTES": 1 << 30, "KV_CACHE_MARGIN_FRACTION": 0.75}
consts = dict(l.replace(" ", "").split("=", 1) for l in src.splitlines()
              if l.startswith(("KV_CACHE_MARGIN_FLOOR_BYTES =", "KV_CACHE_MARGIN_FRACTION =")))
assert consts["KV_CACHE_MARGIN_FRACTION"] == "0.75", consts
assert consts["KV_CACHE_MARGIN_FLOOR_BYTES"] == "(3ifcurrent_platform.is_rocm()else1)<<30", consts
exec(compile(ast.Module(body=fn, type_ignores=[]), "x", "exec"), ns)
real = ns["measure_kv_cache_bytes"]
rng = random.Random(34)
N = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
bad = 0
for _ in range(N):
    total = rng.randint(4, 200) << 30
    init_free = total - rng.randint(0, total // 3)
    util = rng.choice([1.0, 1.0, 0.92, 0.9, 0.5, 0.71])
    import math
    req = math.ceil(total * util)
    resident = rng.randint(0, total)
    transient = rng.randint(0, 6 << 30)
    growth = rng.choice([0, 0, rng.randint(0, 4 << 30)])
    floor = rng.choice([1 << 30, 3 << 30])
    r = real(requested_memory=req, init_free_memory=init_free,
             free_memory=init_free - resident, committed_bytes=0,
             transient_peak_bytes=transient, torch_reserve_growth_bytes=growth,
             margin_floor_bytes=floor)
    m = kvplan.measured_kv_memory_bytes(req, init_free, resident, transient,
                                        torch_reserve_growth_bytes=growth,
                                        margin_floor_bytes=floor)
    bad += r != m
print({"cases": N, "mismatch": bad})
sys.exit(1 if bad else 0)
