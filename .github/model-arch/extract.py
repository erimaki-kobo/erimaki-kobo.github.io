#!/usr/bin/env python3
"""Readers used by update_data.py. Everything is read with `git show` and parsed with ast; nothing upstream is imported or run."""
import ast, re, subprocess


def show(repo, tag, path):
    r = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (tag, path)], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def vkey(v):
    return [int(x) for x in re.findall(r"\d+", v)]


def final_tags(repo, after=None):
    out = subprocess.run(["git", "-C", repo, "tag"], capture_output=True, text=True, check=True).stdout.split()
    tags = sorted((t for t in out if re.fullmatch(r"v\d+(\.\d+)+(\.post\d+)?", t)), key=vkey)
    return [t for t in tags if after is None or vkey(t) > vkey(after)]


# ---- vLLM: vllm/model_executor/models/registry.py ----
VL_SPECIAL = {"_TRANSFORMERS_SUPPORTED_MODELS": "t", "_TRANSFORMERS_BACKEND_MODELS": "t",
              "_PREVIOUSLY_SUPPORTED_MODELS": "p", "_OOT_SUPPORTED_MODELS": "o"}


def vllm_registry(repo, tag):
    """-> (native names, {name: (kind, value)} for the Transformers-backend, removed and plugin lists)."""
    src = show(repo, tag, "vllm/model_executor/models/registry.py")
    native, special = set(), {}
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict):
            name, val = n.targets[0].id, n.value
        elif isinstance(n, ast.AnnAssign) and isinstance(n.value, ast.Dict):
            name, val = n.target.id, n.value
        else:
            continue
        if not name.endswith("_MODELS"):
            continue
        for k, v in zip(val.keys, val.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            if name in VL_SPECIAL:
                special.setdefault(k.value, (VL_SPECIAL[name], v.value if isinstance(v, ast.Constant) else None))
            else:
                native.add(k.value)
    return native, special


def vllm_status(name, first, native, special, last_native):
    """The data.json record for one architecture name, given the newest registry."""
    if name in native:
        return [first, "n"]
    kind, val = special.get(name, ("g", None))
    if kind == "o":
        return [first, "o", val]
    return [first, kind, last_native]


# ---- Transformers: model_type table and architecture -> model_type ----
def tf_model_types(repo, tag):
    """model_types that have a Config class at this tag."""
    out = set()
    for path in ("src/transformers/models/auto/configuration_auto.py", "src/transformers/models/auto/auto_mappings.py"):
        src = show(repo, tag, path)
        if src is None:
            continue
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Tuple) and len(n.elts) == 2 and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in n.elts) \
                    and n.elts[1].value.endswith("Config"):
                out.add(n.elts[0].value)
            elif isinstance(n, ast.Dict):          # CONFIG_MAPPING_NAMES additions written as {"model_type": "XConfig"}
                for k, v in zip(n.keys, n.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str) and isinstance(v, ast.Constant) \
                            and isinstance(v.value, str) and v.value.endswith("Config"):
                        out.add(k.value)
    return out


def tf_arch_to_model_type(repo, tag):
    """Class name -> model_type from the MODEL_FOR_*_MAPPING_NAMES / MODEL_MAPPING_NAMES tables (first table that names the class wins)."""
    src = show(repo, tag, "src/transformers/models/auto/modeling_auto.py")
    out = {}
    for n in ast.parse(src).body:
        if not (isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id.endswith("MAPPING_NAMES")):
            continue
        for t in ast.walk(n.value):
            if isinstance(t, ast.Tuple) and len(t.elts) == 2 and isinstance(t.elts[0], ast.Constant) and isinstance(t.elts[0].value, str):
                mt, v = t.elts[0].value, t.elts[1]
                names = [v.value] if isinstance(v, ast.Constant) and isinstance(v.value, str) else \
                    [e.value for e in v.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)] if isinstance(v, (ast.Tuple, ast.List)) else []
                for c in names:
                    out.setdefault(c, mt)
    return out
