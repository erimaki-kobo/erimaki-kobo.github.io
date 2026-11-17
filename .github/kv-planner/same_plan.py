#!/usr/bin/env python3
"""Which functions of vLLM's KV cache planning differ between two tags?

Usage: python3 -I same_rules.py <vllm.git> <old tag> <new tag>
Reads the files with `git show` and compares each function's AST (comments and formatting do not count).
Nothing from vLLM is imported or run.
"""
import ast, subprocess, sys

repo, old, new = sys.argv[1:4]
FILES = [
    "vllm/v1/kv_cache_interface.py",
    "vllm/v1/core/kv_cache_planning.py",
    "vllm/v1/core/kv_cache_utils.py",
    "vllm/v1/core/kv_cache_layout.py",
    "vllm/v1/core/kv_cache_spec_registry.py",
    "vllm/v1/core/kv_cache_config_builder.py",
    "vllm/utils/math_utils.py",
    "vllm/v1/worker/utils.py",
    "vllm/v1/worker/gpu_worker.py",
    "vllm/config/model.py",
    "vllm/config/vllm.py",
    "vllm/config/cache.py",
    "vllm/engine/arg_utils.py",
    "vllm/model_executor/layers/attention/mla_attention.py",
]


def funcs(tag, path):
    r = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (tag, path)], capture_output=True, text=True)
    if r.returncode:
        return None
    out = {}

    def walk(node, prefix):
        for n in ast.iter_child_nodes(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = [b for b in n.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str))]
                out[prefix + n.name] = ast.dump(ast.Module(body=body, type_ignores=[])) + ast.dump(n.args)
                walk(n, prefix + n.name + ".")
            elif isinstance(n, ast.ClassDef):
                walk(n, prefix + n.name + ".")
    walk(ast.parse(r.stdout), "")
    return out


for p in FILES:
    a, b = funcs(old, p), funcs(new, p)
    if a is None or b is None:
        print("%-58s %s" % (p, "missing in " + (old if a is None else new)))
        continue
    ch = sorted(k for k in a.keys() & b.keys() if a[k] != b[k])
    print("%-58s same %d, changed %s, removed %s, added %s" % (
        p, len(a.keys() & b.keys()) - len(ch), ch, sorted(a.keys() - b.keys()), sorted(b.keys() - a.keys())))
