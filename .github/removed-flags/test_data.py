"""Independent check: for sampled names, the source files at the first release contain the literal name and the
release before does not (plain substring search over the files the extractors read, fetched again with git show)."""
import json, random, subprocess, sys
D = json.load(open("out/data.json"))["libs"]; random.seed(1113)
H = "/home/claude/w/hist"
def show(repo, tag, path):
    p = subprocess.run(["git", "-C", f"{H}/{repo}.git", "show", f"refs/tags/{tag}:{path}"], capture_output=True)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else ""
VF = ["vllm/engine/arg_utils.py", "vllm/entrypoints/openai/cli_args.py", "vllm/entrypoints/common/cli_args.py", "vllm/entrypoints/launchers/cli_args.py", "vllm/entrypoints/api_server.py", "vllm/entrypoints/openai/api_server.py", "vllm/scripts.py", "vllm/entrypoints/cli/serve.py"]
def vtext(tag): return "".join(show("vllm-project_vllm", tag, p) for p in VF)
EARLY = json.load(open("out/data.json")).get("env_early", {})
def etext(tag):  # envs.py, plus the other files for the releases before a variable entered envs.py
    t = show("vllm-project_vllm", tag, "vllm/envs.py")
    p = subprocess.run(["git", "-C", f"{H}/vllm-project_vllm.git", "grep", "-h", "-o", "-E", '"VLLM_[A-Z0-9_]+"', f"refs/tags/{tag}", "--", "vllm/*.py", ":!vllm/envs.py"], capture_output=True)
    return t + "".join(l for l in p.stdout.decode().splitlines() if l.strip('"') in EARLY)
fails = n = 0
for lib, txt, conv in (("vllm_cli", vtext, lambda s: [f'"{s}"', "'" + s + "'", s[2:].replace("-", "_") + ":"]), ("vllm_env", etext, lambda s: [f'"{s}"']) ):
    L = D[lib]; T = L["tags"]
    names = [k for k in L["names"]]
    for name in random.sample(names, 30):
        r = L["names"][name]; i = r[0][0]
        pats = conv(name)
        now = txt(T[i]); ok = any(p in now for p in pats)
        if i > 0:
            before = txt(T[i - 1]); ok = ok and not any(p in before for p in pats[:2])
        n += 1; fails += not ok
        if not ok: print("FAIL", lib, name, T[i])
print(f"{n - fails}/{n} pass")
