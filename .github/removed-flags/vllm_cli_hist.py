"""vLLM CLI flags per release tag: engine args (arg_utils.py add_argument) + server/frontend args (cli_args.py)."""
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
    out, rc = git("show", f"{tag}:{path}")
    open(fn, "w", encoding="utf-8").write(out if rc == 0 else "")
    return out if rc == 0 else None
FLAG = re.compile(r"add_argument\(\s*((?:[\"'][^\"']+[\"']\s*,\s*)+)", re.S)
def flags_from_add_argument(src):
    out = set()
    for m in FLAG.finditer(src):
        for s in re.findall(r"[\"'](-[^\"']+)[\"']", m.group(1)):
            out.add(s)
    return out
def frontend_dataclass_flags(src):
    out = set()
    if "replace('_', '-')" not in src and 'replace("_", "-")' not in src:
        return out
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
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
    res[t] = {"date": d, "flags": sorted(fl)}
    print(t, len(fl), file=sys.stderr, flush=True)
json.dump(res, sys.stdout)
