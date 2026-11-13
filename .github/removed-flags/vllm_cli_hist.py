"""vLLM CLI flags per release tag. usage: vllm_cli_hist.py <hist dir> <cache dir> > vllm_cli.json
Reads add_argument(...) calls with the AST: engine args (arg_utils.py), server args (cli_args.py, api_server.py),
the serve subcommand's own arguments (scripts.py, entrypoints/cli/serve.py: calls on serve_parser), names registered
in a loop over a literal list (for arg, type in [("--x", str), ...]: add_argument(arg, ...)), and FrontendArgs fields."""
import ast, re, subprocess, sys, os, json
H, C = sys.argv[1], sys.argv[2]
REPO = "vllm-project_vllm"
def git(*a):
    p = subprocess.run(["git", "-C", os.path.join(H, REPO + ".git")] + list(a), capture_output=True, text=True)
    return p.stdout, p.returncode
def show(tag, path):
    fn = os.path.join(C, REPO, tag + "__" + path.replace("/", "__"))
    if os.path.exists(fn):
        return open(fn, encoding="utf-8").read() or None
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    out, rc = git("show", f"refs/tags/{tag}:{path}")
    open(fn, "w", encoding="utf-8").write(out if rc == 0 else "")
    return out if rc == 0 else None
def flags_from_add_argument(src, receiver=None):
    """Flag names of add_argument calls. receiver: only calls on a variable of that name (serve_parser)."""
    out = set()
    tree = ast.parse(src)
    parents = {}
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            parents[ch] = n
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "add_argument"):
            continue
        if receiver and not (isinstance(n.func.value, ast.Name) and n.func.value.id == receiver):
            continue
        for a in n.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                if a.value.startswith("-"):
                    out.add(a.value)
            elif isinstance(a, ast.Name):  # a loop variable: take the literals of the enclosing for's iterable
                p = n
                while p in parents:
                    p = parents[p]
                    if isinstance(p, ast.For) and a.id in [x.id for x in ast.walk(p.target) if isinstance(x, ast.Name)]:
                        out.update(c.value for c in ast.walk(p.iter)
                                   if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value.startswith("--"))
                        break
    return out
def frontend_dataclass_flags(src):
    out = set()
    if "replace('_', '-')" not in src and 'replace("_", "-")' not in src:
        return out
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and node.name.endswith("FrontendArgs"):
            for n in node.body:
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and not n.target.id.startswith("_"):
                    out.add("--" + n.target.id.replace("_", "-"))
    return out
out, _ = git("for-each-ref", "refs/tags", "--format=%(refname:lstrip=2)|%(creatordate:short)")
tags = sorted([tuple(l.split("|")) for l in out.splitlines() if re.match(r"^v\d+\.\d+\.\d+(\.post\d+)?$", l.split("|")[0])],
              key=lambda r: [int(x) for x in re.findall(r"\d+", r[0])])
res = {}
for t, d in tags:
    fl = set()
    a = show(t, "vllm/engine/arg_utils.py")
    if a: fl |= flags_from_add_argument(a)
    for p in ("vllm/entrypoints/openai/cli_args.py", "vllm/entrypoints/common/cli_args.py", "vllm/entrypoints/launchers/cli_args.py", "vllm/entrypoints/api_server.py", "vllm/entrypoints/openai/api_server.py"):
        s = show(t, p)
        if s:
            fl |= flags_from_add_argument(s) | frontend_dataclass_flags(s)
    for p in ("vllm/scripts.py", "vllm/entrypoints/cli/serve.py"):
        s = show(t, p)
        if s:
            fl |= flags_from_add_argument(s, receiver="serve_parser")
    res[t] = {"date": d, "flags": sorted(fl)}
    print(t, len(fl), file=sys.stderr, flush=True)
json.dump(res, sys.stdout)
