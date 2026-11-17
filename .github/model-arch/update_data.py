#!/usr/bin/env python3
"""Bring en/model-arch-min-version/data.json up to the newest releases (incremental: new tags only).

Usage: python3 -I update_data.py <data.json> <vllm.git> <transformers.git> <conv dir> <conv_first.json> <archs.json> <pypi_dates.json> > new_data.json
  conv dir        conversion/ + gguf-py/gguf/constants.py of the llama.cpp build named by archs.json["llama_cpp_head"]
  conv_first.json output of converter_first.py for the classes the converter learned since the old data
Before changing anything it re-derives what the old data says about its own newest tags (vLLM statuses, live
Transformers model_types) and stops if that does not reproduce: then the upstream files changed shape.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract as E
from gguf_map import gguf_map

old_p, VL, TF, conv, cf_p, archs_p, pypi_p = sys.argv[1:8]
D = json.load(open(old_p))
CF, ARCHS, PYPI = json.load(open(cf_p)), json.load(open(archs_p)), json.load(open(pypi_p))
log = lambda *a: print(*a, file=sys.stderr)

# ---- vLLM ----
native, special = E.vllm_registry(VL, D["vl_latest"])
for k, v in D["vl"].items():
    assert E.vllm_status(k, v[0], native, special, v[2] if len(v) > 2 and v[1] != "o" else None) == v, ("vLLM status not reproduced", k, v)
assert not native - set(D["vl"])
prev, prev_native = D["vl_latest"], native
for tag in E.final_tags(VL, D["vl_latest"]):
    native, special = E.vllm_registry(VL, tag)
    for k in sorted(native - set(D["vl"])):
        D["vl"][k] = [tag, "n"]
    for k, v in D["vl"].items():
        was_native = v[1] == "n" and k in prev_native
        last = prev if (was_native and k not in native) else (v[2] if len(v) > 2 and v[1] != "o" else None)
        new = E.vllm_status(k, v[0], native, special, last)
        if new[1] == "p":                              # the registry names the last version itself: must agree
            assert special[k][1] is None or "v" + special[k][1] == new[2], (k, special[k], new)
        if new != v:
            log("vLLM", tag, k, v, "->", new)
            D["vl"][k] = new
    prev, prev_native, D["vl_latest"] = tag, native, tag

# ---- Transformers ----
live = {k for k, v in D["tf"].items() if v[1] is None}
assert E.tf_model_types(TF, D["tf_latest"]) == live, "Transformers model_types not reproduced"
prev = D["tf_latest"]
for tag in E.final_tags(TF, D["tf_latest"]):
    now = E.tf_model_types(TF, tag)
    for k in sorted(now - live):
        assert k not in D["tf"], ("model_type came back", k)
        D["tf"][k] = [tag, None]
        log("Transformers", tag, "+", k)
    for k in sorted(live - now):
        D["tf"][k][1] = prev                           # last release that has it
        log("Transformers", tag, "-", k)
    live, prev, D["tf_latest"] = now, tag, tag
# class -> model_type: keep what is published (a class shared by two model_types keeps its first owner), add new classes
for c, mt in E.tf_arch_to_model_type(TF, D["tf_latest"]).items():
    D["a2m"].setdefault(c, mt)

# ---- dates: PyPI upload date where PyPI has the release, the tag date otherwise ----
import subprocess
def tag_date(repo, t):
    return subprocess.run(["git", "-C", repo, "for-each-ref", "--format=%(creatordate:short)", "refs/tags/" + t], capture_output=True, text=True, check=True).stdout.strip()
for repo, lib, tags in ((VL, "vllm", E.final_tags(VL)), (TF, "transformers", E.final_tags(TF, "v3.99"))):
    for t in tags:
        if t in D["dates"] or t in (D["vl_latest"], D["tf_latest"]) or any(t == v[0] for v in list(D["vl"].values()) + list(D["tf"].values())):
            d = PYPI[lib].get(t.lstrip("v")) or tag_date(repo, t)
            assert re.fullmatch(r"\d{4}-\d\d-\d\d", d), (t, d)
            if D["dates"].get(t) != d:
                log("date", t, D["dates"].get(t), "->", d)
            D["dates"][t] = d
D["dates"] = dict(sorted(D["dates"].items(), key=lambda kv: (not kv[0].startswith("v0."), E.vkey(kv[0]))))

# ---- GGUF ----
head = ARCHS["llama_cpp_head"]
A = {x["architecture"]: x for x in ARCHS["architectures"]}
for k, v in D["gg"].items():                           # what is published must still be what archs.json says
    assert "b" + v[0] == A[k]["llama_cpp_first_build"] and v[1] == A[k]["llama_cpp_first_build_date"], (k, v)
D["gg"] = {k: [x["llama_cpp_first_build"].lstrip("b"), x["llama_cpp_first_build_date"], x["ollama_first_release_bundled_llama_cpp"]]
           for k, x in sorted(A.items())}
m = gguf_map(conv)
assert all(m.get(k) == v[0] for k, v in D["h2g"].items()), "a published class changed its GGUF architecture"
for c in sorted(set(m) - set(D["h2g"])):
    b, date = CF[c][0], CF[c][1]
    assert int(b) <= int(head.lstrip("b")) and m[c] in D["gg"], (c, b, m[c])
    D["h2g"][c] = [m[c], b, date]
    log("converter +", c, D["h2g"][c])
D["h2g"] = dict(sorted(D["h2g"].items()))
D["vl"] = dict(sorted(D["vl"].items()))
D["tf"] = dict(sorted(D["tf"].items()))
D["a2m"] = dict(sorted(D["a2m"].items()))
D["gguf_asof"], D["gguf_build"] = ARCHS["as_of"], head
D["ollama_latest"] = ARCHS["ollama_latest"]
json.dump(D, sys.stdout, separators=(",", ":"), sort_keys=True)
log("vl", len(D["vl"]), "native", sum(v[1] == "n" for v in D["vl"].values()), "| tf", len(D["tf"]), "| a2m", len(D["a2m"]), "| h2g", len(D["h2g"]), "| gg", len(D["gg"]), "| dates", len(D["dates"]))
