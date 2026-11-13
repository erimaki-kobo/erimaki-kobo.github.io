"""Compact per-name version ranges for the removed-flags lookup. Inputs: out/vllm_cli.json, vllm_env.json, vllm_req.json, sglang_cli.json."""
import json, re
def load(p): return json.load(open(p))
cli, env, req, sg = load("out/vllm_cli.json"), load("out/vllm_env.json"), load("out/vllm_req.json"), load("out/sglang_cli.json")
def ranges(d, key):
    tags = list(d); idx = {t: i for i, t in enumerate(tags)}
    span = {}
    for t in tags:
        for n in d[t][key]:
            r = span.setdefault(n, [])
            if r and r[-1][1] == idx[t] - 1: r[-1][1] = idx[t]
            else: r.append([idx[t], idx[t]])
    return tags, span
# A variable that envs.py defines counts as read in the releases just before it entered envs.py, if the source
# names it elsewhere in every one of them (it was read with os.getenv there). Never extended after its removal:
# later mentions are deprecation messages.
_tags = list(env); _first = {}
for _i, _t in enumerate(_tags):
    for _n in env[_t]["names"]: _first.setdefault(_n, _i)
EARLY = {}
for _n, _i in _first.items():
    _j = _i
    while _j > 0 and _n in env[_tags[_j - 1]].get("quoted", []): _j -= 1
    if _j < _i:
        EARLY[_n] = _tags[_j]
        for _k in range(_j, _i): env[_tags[_k]]["names"] = sorted(set(env[_tags[_k]]["names"]) | {_n})
print("env names read before they entered envs.py:", EARLY)
out = {"libs": {}, "env_early": EARLY}
def add(name, d, key, filt=None):
    tags, span = ranges(d, key)
    if filt: span = {k: v for k, v in span.items() if filt(k)}
    out["libs"][name] = {"tags": tags, "dates": [d[t]["date"] for t in tags], "names": span}
add("vllm_cli", cli, "flags", lambda k: k.startswith("--"))
add("vllm_env", env, "names")
# request fields: union of SamplingParams, chat, completion, each tracked separately
for k in ("sampling_params", "chat", "completion"):
    add("vllm_" + k, req, k)
add("sglang_cli", sg, "flags", lambda k: k.startswith("--"))
json.dump(out, open("out/data.json", "w"), separators=(",", ":"))
for k, v in out["libs"].items():
    last = len(v["tags"]) - 1
    gone = sum(1 for r in v["names"].values() if r[-1][1] != last)
    print(k, v["tags"][0], v["tags"][-1], len(v["tags"]), "names", len(v["names"]), "gone", gone, "now", len(v["names"]) - gone)
