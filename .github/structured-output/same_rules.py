#!/usr/bin/env python3
"""Which functions that decide the structured-output backend differ between two vLLM tags?

Usage: python3 -I same_rules.py <vllm.git> <old tag> <new tag>
Reads the files with `git show` and compares each function's AST (comments and formatting do not count).
Nothing from vLLM is imported or run.
"""
import ast, subprocess, sys

repo, old, new = sys.argv[1:4]
FILES = [
    "vllm/sampling_params.py",
    "vllm/config/structured_outputs.py",
    "vllm/v1/structured_output/__init__.py",
    "vllm/v1/structured_output/utils.py",
    "vllm/v1/structured_output/request.py",
    "vllm/v1/structured_output/backend_xgrammar.py",
    "vllm/v1/structured_output/backend_guidance.py",
    "vllm/v1/structured_output/backend_outlines.py",
    "vllm/v1/structured_output/backend_lm_format_enforcer.py",
    "vllm/v1/engine/input_processor.py",
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
