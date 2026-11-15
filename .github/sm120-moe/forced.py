"""Run the forced-backend cases quoted on the page and write <run dir>/forced.json.
usage: python3 forced.py <run dir containing wt_<tag>/> <latest tag>"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN, LATEST = sys.argv[1], sys.argv[2]
def run(tag, cap, hum, force, env=None):
    e = dict(os.environ, CUDA_VISIBLE_DEVICES=""); e.update(env or {})
    p = subprocess.run([sys.executable, os.path.join(HERE, "run_select.py"), os.path.join(RUN, "wt_" + tag), str(cap), "1", str(hum)] + ([force] if force else []),
                       capture_output=True, text=True, env=e)
    out = {}
    for l in p.stdout.splitlines():
        if l.startswith("{"):
            r = json.loads(l)
            out[r["scenario"]] = ("ok:" + r["backend"]) if r.get("ok") else (r["error"] + ": " + r["msg"])
    assert out, p.stderr[-2000:]
    return out
F = {}
for force in ("flashinfer_trtllm", "cutlass", "flashinfer_cutlass", "b12x", "marlin"):
    for s, v in run(LATEST, 120, 1, force).items(): F[f"{force}|{s}"] = v
for name, env in (("env_fp4", {"VLLM_USE_FLASHINFER_MOE_FP4": "1"}),
                  ("env_fp4_throughput", {"VLLM_USE_FLASHINFER_MOE_FP4": "1", "VLLM_FLASHINFER_MOE_BACKEND": "throughput"}),
                  ("env_fp4_latency", {"VLLM_USE_FLASHINFER_MOE_FP4": "1", "VLLM_FLASHINFER_MOE_BACKEND": "latency"})):
    for tag in ("v0.15.0", "v0.15.1"):
        F[f"{tag}|{name}|nvfp4"] = run(tag, 120, 0, None, dict(env, SCEN_ONLY="nvfp4"))["nvfp4"]
json.dump(F, open(os.path.join(RUN, "forced.json"), "w"), indent=1, sort_keys=True)
for k in sorted(F): print(k, "=>", F[k][:230])
