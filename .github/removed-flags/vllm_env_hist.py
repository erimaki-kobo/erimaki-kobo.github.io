"""vLLM environment variables per release tag (vllm/envs.py). usage: vllm_env_hist.py <hist dir> <cache dir> > vllm_env.json
"quoted": VLLM_ names that appear as a quoted string in other vllm/*.py files of the tag. build_data.py uses it only for
releases before a variable entered envs.py (VLLM_BATCH_INVARIANT was read with os.getenv from v0.11.1 to v0.18.1)."""
import json, os, re, subprocess, sys
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
out, _ = git("for-each-ref", "refs/tags", "--format=%(refname:lstrip=2)|%(creatordate:short)")
tags = sorted([tuple(l.split("|")) for l in out.splitlines() if re.match(r"^v\d+\.\d+\.\d+(\.post\d+)?$", l.split("|")[0])],
              key=lambda r: [int(x) for x in re.findall(r"\d+", r[0])])
res = {}
for t, d in tags:
    s = show(t, "vllm/envs.py")
    if not s:
        continue
    names = sorted(set(re.findall(r'^\s*["\'](VLLM_[A-Z0-9_]+)["\']\s*:', s, re.M)))
    g, _ = git("grep", "-h", "-o", "-E", r"""["']VLLM_[A-Z0-9_]+["']""", f"refs/tags/{t}", "--", "vllm/*.py", ":!vllm/envs.py")
    quoted = sorted(set(x[1:-1] for x in g.split()))
    res[t] = {"date": d, "names": names, "quoted": quoted}
    print(t, d, len(names), file=sys.stderr, flush=True)
json.dump(res, sys.stdout)
