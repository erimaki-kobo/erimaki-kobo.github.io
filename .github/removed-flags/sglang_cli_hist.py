"""SGLang server CLI flags per release tag (add_argument calls; from v0.5.14 also Annotated dataclass fields)."""
import json, os, re, subprocess, sys, ast
H, C = sys.argv[1], sys.argv[2]
REPO = "sgl-project_sglang"
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
FLAG = re.compile(r"add_argument\(\s*((?:[\"'][^\"']+[\"']\s*,\s*)+)", re.S)
def flags(src):
    out = set()
    for m in FLAG.finditer(src):
        out.update(re.findall(r"[\"'](-[^\"']+)[\"']", m.group(1)))
    return out
def ls(tag, d):
    out, rc = git("ls-tree", "--name-only", f"refs/tags/{tag}:{d}")
    return out.split() if rc == 0 else []
def annotated_flags(src):
    out = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for n in cls.body:
            if not (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)):
                continue
            ann = n.annotation
            if not (isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name) and ann.value.id in ("A", "Annotated")):
                continue
            elts = ann.slice.elts if isinstance(ann.slice, ast.Tuple) else [ann.slice]
            meta = elts[1:]
            arg = next((e for e in meta if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == "Arg"), None)
            bare = any(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in meta)
            if arg is None and not bare:
                continue
            name, aliases, no_cli = "--" + n.target.id.replace("_", "-"), [], False
            if arg is not None:
                for kw in arg.keywords:
                    if kw.arg == "cli_name" and isinstance(kw.value, ast.Constant) and kw.value.value:
                        name = kw.value.value
                    elif kw.arg == "aliases" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        aliases = [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
                    elif kw.arg == "no_cli" and isinstance(kw.value, ast.Constant):
                        no_cli = bool(kw.value.value)
            if n.target.id.startswith("_") or no_cli:
                continue
            out.add(name)
            out.update(a for a in aliases if isinstance(a, str) and a.startswith("-"))
    return out
out, _ = git("for-each-ref", "refs/tags", "--format=%(refname:lstrip=2)|%(creatordate:short)")
tags = sorted([tuple(l.split("|")) for l in out.splitlines() if re.match(r"^v\d+\.\d+\.\d+(\.post\d+)?$", l.split("|")[0])],
              key=lambda r: [int(x) for x in re.findall(r"\d+", r[0])])
res = {}
for t, d in tags:
    s = show(t, "python/sglang/srt/server_args.py")
    fl = flags(s) if s else set()
    if s and "add_cli_args_from_dataclass" in s:
        fl |= annotated_flags(s)
        for f in ls(t, "python/sglang/srt/arg_groups/fields"):
            if f.endswith(".py"):
                fs = show(t, "python/sglang/srt/arg_groups/fields/" + f)
                if fs:
                    fl |= annotated_flags(fs)
    if fl:
        res[t] = {"date": d, "flags": sorted(fl)}
    print(t, d, len(fl), file=sys.stderr, flush=True)
json.dump(res, sys.stdout)
