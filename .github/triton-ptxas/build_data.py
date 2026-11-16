"""Join pypi.json with the selection rules read from each Triton release tag and the torch pin of each vLLM tag.
usage: python3 build_data.py <workdir with pypi.json> <triton.git bare clone> <vllm.git bare clone>  -> <workdir>/data.json

Nothing from the Triton repository is executed. The three small rules that decide the outcome (which binary, which --gpu-name,
which CUDA release numbers ptx_get_version accepts) are re-implemented below, and each release's source text is matched against
the exact form the re-implementation assumes. An unknown form stops the build, so a new release cannot be mis-read silently."""
import json, subprocess, sys, re, os
W, TG, VG = sys.argv[1:4]
P = json.load(open(os.path.join(W, "pypi.json")))
def git(repo, *a):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None
def vkey(v): return [int(x) for x in re.findall(r"\d+", v)]
def norm(s): return re.sub(r"\s+", " ", s.replace('"', "'"))
CAPS = [80, 86, 89, 90, 100, 103, 110, 120, 121]

def rules(tag):
    raw = git(TG, "show", f"{tag}:third_party/nvidia/backend/compiler.py"); assert raw, tag
    src = norm(raw); kn = norm(git(TG, "show", f"{tag}:python/triton/knobs.py") or "")
    out = {}
    # --- which binary ---
    if "def get_ptxas(" not in src:                                   # <= v3.2.0
        assert "_path_to_binary('ptxas')" in src and "ptxas-blackwell" not in src, tag
        sel = lambda c: "ptxas"; out["sel_rule"] = "one"
    elif "name = 'ptxas-blackwell' if arch >= 100 else 'ptxas'" in src:   # v3.3.x
        sel = lambda c: "ptxas-blackwell" if c >= 100 else "ptxas"; out["sel_rule"] = ">=100"
    elif "def get_ptxas() -> knobs.NvidiaTool: return knobs.nvidia.ptxas " in src:   # v3.4.0 - v3.5.1
        sel = lambda c: "ptxas"; out["sel_rule"] = "one"
    elif "return knobs.nvidia.ptxas_blackwell if arch >= 100 else knobs.nvidia.ptxas " in src:   # v3.6.0 - v3.8.0
        sel = lambda c: "ptxas-blackwell" if c >= 100 else "ptxas"; out["sel_rule"] = ">=100"
    elif re.search(r"def get_ptxas\(arch: int\) -> knobs\.NvidiaTool: if arch < 90: return knobs\.nvidia\.ptxas (# [^\n]*? )?return knobs\.nvidia\.ptxas_blackwell ", src):   # v3.9.0
        sel = lambda c: "ptxas-blackwell" if c >= 90 else "ptxas"; out["sel_rule"] = ">=90"
    else:
        raise SystemExit(f"{tag}: get_ptxas has a form this script does not know")
    out["sel"] = {str(c): sel(c) for c in CAPS}
    # --- --gpu-name value ---
    if "def sm_arch_from_capability" in src:
        assert "suffix = 'a' if capability >= 90 else '' return f'sm_{capability}{suffix}'" in src, tag
        assert "arch = sm_arch_from_capability(capability)" in src and "--gpu-name={arch}" in src, tag
        nm = lambda c: f"sm_{c}" + ("a" if c >= 90 else ""); out["name_rule"] = "a>=90"
    else:
        assert ("suffix = 'a ' if capability == 90 else ' '" in src or "suffix = 'a' if capability == 90 else ''" in src) and "--gpu-name=sm_{capability}{suffix}" in src, tag
        nm = lambda c: f"sm_{c}" + ("a" if c == 90 else ""); out["name_rule"] = "a==90"
    out["name"] = {str(c): nm(c) for c in CAPS}
    # --- environment variable per binary ---
    if "replace('-', '_')" in kn:
        assert "env_nvidia_tool('ptxas-blackwell')" in kn
        out["env"] = {"ptxas": "TRITON_PTXAS_PATH", "ptxas-blackwell": "TRITON_PTXAS_BLACKWELL_PATH"}
    elif "env_nvidia_tool('ptxas')" in kn:
        assert "ptxas-blackwell" not in kn and "f'TRITON_{binary.upper()}_PATH'" in kn, tag
        out["env"] = {"ptxas": "TRITON_PTXAS_PATH"}
    else:
        assert "os.environ.get(f'TRITON_{binary.upper()}_PATH', '')" in src, tag
        out["env"] = {"ptxas": "TRITON_PTXAS_PATH"}
        if out["sel_rule"] != "one": out["env"]["ptxas-blackwell"] = "TRITON_PTXAS-BLACKWELL_PATH"   # upper() keeps the hyphen
    # --- a path that does not work falls back to the bundled binary ---
    assert ("paths = [path, self.default_path]" in kn) or ("as fallback in case the pointed binary isn't # accessible. self.default(), ]" in kn) or ("os.path.join(os.path.dirname(__file__), 'bin', binary)" in src), tag
    # --- which CUDA release numbers ptx_get_version accepts ---
    m = re.search(r"def ptx_get_version\(.*?raise RuntimeError\(", src); assert m, tag
    body = m.group(0)
    c13 = "if major >= 13:" in body
    if "if major == 12: return 80 + minor " in body: c12 = lambda mi: True; form = "12.x"
    elif "if minor < 6: return 80 + minor elif minor == 6: return 85 " in body: c12 = lambda mi: mi <= 6; form = "12.0-12.6"
    elif "if minor < 6: return 80 + minor else: return 80 + minor - 1 " in body: c12 = lambda mi: True; form = "12.x"
    else: raise SystemExit(f"{tag}: ptx_get_version has a form this script does not know")
    assert "if major == 11:" in body and "if major == 10:" in body
    out["cuda_rule"] = form + (" and 13+" if c13 else "")
    acc = []
    for mm in sorted({".".join(v.split(".")[:2]) for v in P["nvcc"]}, key=vkey):
        ma, mi = map(int, mm.split("."))
        if (ma == 12 and c12(mi)) or (ma >= 13 and c13): acc.append(mm)
    out["cuda_ok"] = acc
    tc = git(TG, "show", f"{tag}:cmake/nvidia-toolchain-version.json") or git(TG, "show", f"{tag}:cmake/nvidia-toolchain-version.txt")
    out["declared"] = json.loads(tc) if tc.strip().startswith("{") else {"ptxas": tc.strip()}
    out["tag_date"] = git(TG, "log", "-1", "--format=%cs", tag).strip()
    return out

# NVIDIA ptxas: sm names per CUDA release
CUDA = {}
for v, r in P["nvcc"].items():
    ls = [a["sm"] for a in r["arch"].values()]; assert all(l == ls[0] for l in ls), v     # x86_64 and aarch64 list the same names
    CUDA[v] = {"date": r["date"], "sm": ls[0]}
MIN = {}
for v in sorted(CUDA, key=vkey):
    m = ".".join(v.split(".")[:2]); MIN.setdefault(m, CUDA[v]["sm"]); assert MIN[m] == CUDA[v]["sm"], v   # every patch release of a minor agrees
T = {}
for v in sorted(P["triton"], key=vkey):
    if vkey(v) < [3, 0, 0]: continue
    r = rules("v" + v); pw = P["triton"][v]; tools = {}; same = True
    for a, x in pw["arch"].items():
        for n, t in x["tools"].items():
            tools.setdefault(n, t["banner"]); assert tools[n] == t["banner"]
            assert t["sm"] == CUDA[t["banner"]]["sm"], (v, a, n)      # bundled binary lists the same names as NVIDIA's wheel of that version
            assert r["declared"].get(n) == t["banner"], (v, n)        # the wheel contains what the tag's toolchain file declares
            same &= P["nvcc"][t["banner"]]["arch"][a]["sha256"] == t["sha256"]
    assert set(tools) == set(r["env"]), (v, tools, r["env"])
    r.update(date=pw["date"], tools=tools, aarch64="aarch64" in pw["arch"], byte_identical=same)
    res = {}
    for c in CAPS:
        tool = r["sel"][str(c)]; name = r["name"][str(c)]; ver = tools[tool]
        e = {"tool": tool, "ver": ver, "name": name, "ok": name in CUDA[ver]["sm"]}
        if not e["ok"]:
            e["var"] = r["env"][tool]
            e["cuda"] = [m for m in MIN if name in MIN[m] and m in r["cuda_ok"]]
        res[str(c)] = e
    r["res"] = res; del r["declared"]; T[v] = r
TORCH = {}
for v, r in P["torch"].items():
    if not r["triton"]: continue
    m = re.match(r"triton\s*\(?\s*(==|~=)\s*([\d.]+)", r["triton"]); assert m, r
    if vkey(m.group(2)) < [3, 0, 0]: continue
    tv = m.group(2)
    if m.group(1) == "~=":      # ~=3.8.0 means the newest 3.8.x
        tv = max((x for x in T if x.startswith(tv.rsplit(".", 1)[0] + ".")), key=vkey)
    assert tv in T, (v, tv)
    TORCH[v] = {"date": r["date"], "triton": tv, "spec": m.group(1) + m.group(2), "aarch64": "platform_machine" not in r["triton"]}
VLLM = []
for t in sorted((t for t in git(VG, "tag").split() if re.fullmatch(r"v\d+\.\d+\.\d+(\.\d+)?", t)), key=vkey):
    pin = None
    for f in ("requirements/cuda.txt", "requirements-cuda.txt", "requirements.txt", "pyproject.toml"):
        s = git(VG, "show", f"{t}:{f}")
        m = s and re.search(r"^\s*\"?torch\s*==\s*([\d.]+)", s, re.M)
        if m: pin = m.group(1); break
    if pin in TORCH: VLLM.append({"v": t[1:], "date": git(VG, "log", "-1", "--format=%cs", t).strip(), "torch": pin})
D = {"caps": CAPS, "triton": T, "cuda": MIN, "cuda_first": {m: min((CUDA[v]["date"] for v in CUDA if v.startswith(m + ".")), default=None) for m in MIN},
     "torch": TORCH, "vllm": VLLM}
json.dump(D, open(os.path.join(W, "data.json"), "w"), indent=1, sort_keys=True)
for v in T:
    print(v, T[v]["date"], T[v]["tag_date"], T[v]["tools"], T[v]["env"], T[v]["cuda_rule"], "identical" if T[v]["byte_identical"] else "same names", "aarch64" if T[v]["aarch64"] else "")
    print("   ", " ".join(f'{c}:{"ok" if e["ok"] else "NO(" + e["name"] + " " + e["var"][7:] + " " + (e["cuda"][0] + ".." + e["cuda"][-1] if e["cuda"] else "none") + ")"}' for c, e in T[v]["res"].items()))
print(len(VLLM), VLLM[0], VLLM[-1]); print({v: (TORCH[v]["triton"], TORCH[v]["aarch64"]) for v in TORCH})
