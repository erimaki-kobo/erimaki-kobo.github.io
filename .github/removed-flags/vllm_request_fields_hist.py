"""vLLM request fields per release tag: SamplingParams and the OpenAI-compatible ChatCompletionRequest / CompletionRequest."""
import ast, json, os, re, subprocess, sys
H, C = sys.argv[1], sys.argv[2]
REPO = "vllm-project_vllm"
def git(*a):
    p = subprocess.run(["git", "-C", os.path.join(H, REPO + ".git")] + list(a), capture_output=True, text=True)
    return p.stdout, p.returncode
def show(tag, path):
    fn = os.path.join(C, REPO, tag + "__" + path.replace("/", "__"))
    if os.path.exists(fn):
        return open(fn, encoding="utf-8", errors="replace").read() or None
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    p = subprocess.run(["git", "-C", os.path.join(H, REPO + ".git"), "show", f"refs/tags/{tag}:{path}"], capture_output=True)
    txt = p.stdout.decode("utf-8", errors="replace") if p.returncode == 0 else ""
    open(fn, "w", encoding="utf-8").write(txt)
    return txt or None
def class_fields(src, cname):
    if not src:
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == cname:
            out = [b.target.id for b in n.body if isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name) and not b.target.id.startswith("_")]
            if not out:
                for b in n.body:
                    if isinstance(b, ast.FunctionDef) and b.name == "__init__":
                        out = [a.arg for a in b.args.args[1:] + b.args.kwonlyargs]
            return sorted(set(out))
    return None
out, _ = git("for-each-ref", "refs/tags", "--format=%(refname:lstrip=2)|%(creatordate:short)")
tags = sorted([tuple(l.split("|")) for l in out.splitlines() if re.match(r"^v\d+\.\d+\.\d+(\.post\d+)?$", l.split("|")[0])],
              key=lambda r: [int(x) for x in re.findall(r"\d+", r[0])])
res = {}
for t, d in tags:
    sp = class_fields(show(t, "vllm/sampling_params.py"), "SamplingParams")
    old = show(t, "vllm/entrypoints/openai/protocol.py")
    chat = class_fields(old, "ChatCompletionRequest") or class_fields(show(t, "vllm/entrypoints/openai/chat_completion/protocol.py"), "ChatCompletionRequest")
    comp = class_fields(old, "CompletionRequest") or class_fields(show(t, "vllm/entrypoints/openai/completion/protocol.py"), "CompletionRequest")
    res[t] = {"date": d, "sampling_params": sp or [], "chat": chat or [], "completion": comp or []}
    print(t, d, len(sp or []), len(chat or []), len(comp or []), file=sys.stderr, flush=True)
json.dump(res, sys.stdout)
