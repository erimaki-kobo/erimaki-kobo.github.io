#!/usr/bin/env python3
"""Second readings of what names_hist.py and build_data.py produced. Nothing is installed or run.

Usage: python3 -I test_data.py diffusers.git dates.json names_hist.json <out dir with data.json> checks.json [-v]
 1. Type-checking copy. Every lazy __init__.py repeats its names as plain imports under
    `if TYPE_CHECKING or DIFFUSERS_SLOW_IMPORT:`. Compare that block, name by name, with the lazy reading. Upstream keeps the
    two by hand, so a few names are in one place only; those are counted and must stay a short known list (MAX_TC_DIFF).
 2. Plain text, top level. A top-level name must appear as a word in src/diffusers/__init__.py of every release that has it,
    and must not appear there in the release before its first or after its last (stale entries excepted).
 3. Plain text, definitions. Every `class X`, `def X` and `X =` found at column 0 by a regular expression in a module that
    does not replace itself must be among the names read for that module.
 4. Placeholders. The names the top-level module hands out with a backend missing are the same names as with it installed.
 5. Anchors: facts known from public error reports and from the files themselves.
"""
import ast, json, os, sys, warnings, collections
warnings.simplefilter("ignore", SyntaxWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch
REPO, PYPI, H = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
OUT, CHK = sys.argv[4], sys.argv[5]
MAX_TC_DIFF = 70
import re
tags = H["tags"]
want, text = fetch.load(REPO, tags)
diff = collections.OrderedDict(); n_mod = n_same = 0; broken = set(); stars = set()
for t in tags:
    mods = {}
    for p, sha in want[t].items():
        m = p[:-3].replace("/", ".")
        m = m[:-len(".__init__")] if m.endswith(".__init__") else "" if m == "__init__" else m
        mods[m] = sha
    def defs_of(m):
        return {n.name for n in ast.parse(text[mods[m]]).body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and not n.name.startswith("_")}
    for m in H["lazy"][t]:
        tree = ast.parse(text[mods[m]])
        got = set()
        def walk(body, on, top=False):
            for n in body:
                if isinstance(n, ast.If):
                    tc = "TYPE_CHECKING" in {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)}
                    walk(n.body, on or tc); walk(n.orelse, on)
                elif isinstance(n, ast.Try):
                    for part in (n.body, n.orelse, n.finalbody, *[h.body for h in n.handlers]): walk(part, on)
                elif (on or top) and isinstance(n, ast.ImportFrom) and n.level >= 1:
                    for a in n.names:
                        if a.name == "*":
                            # only dummy modules are star-imported here, as a stand-in for a missing backend; the module they
                            # name is often the whole dummy file of another package, so it says nothing about this one
                            assert n.module.rsplit(".", 1)[-1].startswith("dummy_"), (t, m, n.module)
                            stars.add((m, n.module))
                        else:
                            got.add(a.asname or a.name)
        walk(tree.body, False)
        pre = m + "." if m else ""
        children = {k[len(pre):] for k in mods if k.startswith(pre) and k != m and "." not in k[len(pre):]}
        mine = set(H["mods"][t][m]) - children
        got -= children
        # names the lazy table serves from .utils and the file itself imports at its head (so the block has no need to repeat them)
        head = {a.asname or a.name for n in tree.body if isinstance(n, ast.ImportFrom) and n.level >= 1 for a in n.names}
        mine -= head
        mine -= {'__version__'} if m == '' else set()
        n_mod += 1
        if mine == got: n_same += 1
        else: diff[(t, m)] = (sorted(mine - got), sorted(got - mine))
print("lazy modules compared:", n_mod, "identical:", n_same)
names = collections.defaultdict(lambda: [set(), set(), []])
for (t, m), (a, b) in diff.items():
    for n in a: names[(m, n)][0].add(t)
    for n in b: names[(m, n)][1].add(t)
print("differences:", len(names), "module/name pairs;", sum(1 for v in names.values() if v[0]), "only in the lazy table,", sum(1 for v in names.values() if v[1]), "only in the type-checking block")
assert len(names) <= MAX_TC_DIFF, len(names)
if "-v" in sys.argv:
    for (m, n), (a, b, _) in sorted(names.items()):
        ts = sorted(a or b, key=fetch.ver)
        print(("lazy only " if a else "tc only   "), m or "(top)", n, ts[0], "..", ts[-1], len(ts))
print("1. dummy star imports skipped:", len(stars))
checks = {"CHK_TC_MODS": n_mod, "CHK_TC_SAME": n_same, "CHK_TC_DIFF": len(names)}

# 2. plain text, top level
D = json.load(open(OUT + "/data.json"))
R, T = D["releases"], D["ranges"]
tc_only_top = {(n, t) for (m, n), (a, b, _) in names.items() if m == "" for t in b}     # in the type-checking block only: not importable
stale_top = {(n, i) for m, n, key, kind, a, b in D["stale"] if m == "" for i in range(a, b or len(R))}
init = [text[want[t]["__init__.py"]] for t in tags]
words = [set(re.findall(r"[A-Za-z_]\w*", s)) for s in init]
files_at = [set(want[t]) for t in tags]
n_edges = n_inside = 0
for n, ri in D["top"].items():
    r = T[ri]
    sub = lambda i: (n + ".py") in files_at[i] or any(p.startswith(n + "/") for p in files_at[i])     # a submodule: no text needed
    for a, b in zip(r[::2], r[1::2]):
        for i in range(a, b or len(R)):
            assert n in words[i] or sub(i), ("has it, text does not", n, R[i][0])
            n_inside += 1
        for i in ([a - 1] if a > 0 else []) + ([b] if b else []):
            if (n, i) in stale_top or any(sub(j) for j in range(len(R))) or (n, tags[i]) in tc_only_top:
                continue
            # the release next to the range must not mention the name at all, or only in a place that is not an import
            if n in words[i]:
                hits = [l for l in init[i].splitlines() if re.search(r"\b%s\b" % re.escape(n), l)]
                assert all(l.lstrip().startswith("#") or "import" not in l and '"' + n + '"' not in l for l in hits), ("text has it", n, R[i][0], hits[:2])
            n_edges += 1
print("2. top-level names:", len(D["top"]), "| name-release pairs found in the text:", n_inside, "| range edges checked:", n_edges)
checks.update({"CHK_TOP": len(D["top"]), "CHK_TOP_PAIRS": n_inside, "CHK_TOP_EDGES": n_edges})

# 3. plain text, definitions
rx = re.compile(r"^(?:class|def|async def)\s+([A-Za-z_]\w*)|^([A-Za-z_]\w*)\s*(?::[^=\n]+)?=(?!=)", re.M)
n_files = n_defs = 0
seen = set()
for t in tags:
    lazy = set(H["lazy"][t])
    for p, sha in want[t].items():
        m = p[:-3].replace("/", ".")
        m = m[:-len(".__init__")] if m.endswith(".__init__") else "" if m == "__init__" else m
        if m in lazy:
            continue
        have = set(H["mods"][t][m])
        if (sha, m) in seen:
            continue
        seen.add((sha, m))
        src = text[sha]
        # blank out triple-quoted strings so that example code in docstrings is not read as definitions
        src = re.sub(r'(\"\"\"|\'\'\')(.*?)\1', lambda q: "\n" * q.group(0).count("\n"), src, flags=re.S)
        found = {a or b for a, b in rx.findall(src)}
        miss = found - have
        assert not miss, (t, p, sorted(miss)[:5])
        n_files += 1
        n_defs += len(found)
print("3. files:", n_files, "| definitions found by the regular expression, all among the names read:", n_defs)
checks.update({"CHK_DEF_FILES": n_files, "CHK_DEFS": n_defs})

# 4. placeholders
bad = {t: sorted(set(H["placeholders"][t]) - set(H["mods"][t][""])) for t in tags}
bad = {t: v for t, v in bad.items() if v}
# apart from one slip in 0.21.0, the only such names are the stale entries: a placeholder is still handed out for them
exp = {"v0.21.0": ["CLIPImageProjection"]}
for n, i in sorted(stale_top):
    exp.setdefault(tags[i], []).append(n)
assert bad == exp, bad
print("4. placeholders:", sum(len(H["placeholders"][t]) for t in tags), "| not also real:", bad)
checks["CHK_PLACEHOLDERS"] = sum(len(H["placeholders"][t]) for t in tags)

# 5. anchors
core = json.load(open(OUT + "/names-core.json"))
pipe = json.load(open(OUT + "/names-pipelines.json"))


def span(m, n):
    src = D["top"] if m == "" else core.get(m) or pipe.get(m) or {}
    if n not in src:
        return None
    r = T[src[n]]
    return [(R[a][0], R[b][0] if b else None) for a, b in zip(r[::2], r[1::2])]


def mod(m):
    r = T[D["mods"][m]]
    return [(R[a][0], R[b][0] if b else None) for a, b in zip(r[::2], r[1::2])]


ANCHORS = [
    # public reports: the release someone had when the import failed, and the first release that has the name
    (span("", "StableDiffusionDepth2ImgPipeline"), [("0.10.0", None)]),     # fails on 0.9.0: hf.co/stabilityai/stable-diffusion-2-depth/discussions/6
    (span("", "FluxPipeline"), [("0.30.0", None)]),                         # hf.co/black-forest-labs/FLUX.1-dev/discussions/41
    (span("", "StableAudioPipeline"), [("0.30.0", None)]),                  # hf.co/stabilityai/stable-audio-open-1.0/discussions/40
    (span("", "WanPipeline"), [("0.33.0", None)]),                          # discuss.huggingface.co/t/cannot-import-wan-pipeline/145370
    (span("utils", "HF_HUB_OFFLINE"), [("0.12.0", "0.25.0")]),              # still fails on 0.31: discuss.huggingface.co/t/.../40262
    (span("", "DPMSolverMultistepScheduler"), [("0.8.0", None)]),
    (span("", "EulerDiscreteScheduler"), [("0.7.0", None)]),
    # the files themselves
    (span("utils", "randn_tensor"), [("0.12.0", "0.21.0")]),
    (span("utils.torch_utils", "randn_tensor"), [("0.12.0", None)]),
    (span("", "StableDiffusion3Pipeline"), [("0.29.0", None)]),
    (span("", "StableVideoDiffusionPipeline"), [("0.24.0", None)]),
    (span("", "LCMScheduler"), [("0.22.0", None)]),
    (span("", "ControlNetModel"), [("0.14.0", None)]),
    (span("", "OnnxStableDiffusionPipeline"), [("0.6.0", "0.43.0")]),
    (span("", "FlaxStableDiffusionPipeline"), [("0.5.0", "0.40.0")]),
    (span("", "StableDiffusionKDiffusionPipeline")[-1][1], "0.37.0"),
    (span("", "OnnxStableDiffusionInpaintPipelineLegacy"), [("0.8.0", "0.25.0")]),
    (span("models.embeddings", "PositionNet"), [("0.20.0", "0.26.0")]),
    (mod("models.unet_2d_condition"), [("0.2.0", "0.29.0")]),
    (mod("models.unets.unet_2d_condition"), [("0.26.0", None)]),
    (mod("pipeline_utils"), [("0.0.2", "0.22.0")]),
    (mod("models.controlnet"), [("0.14.0", "0.37.0")]),
    (D["lazy_from"], [r[0] for r in R].index("0.21.0")),
]
for got, exp in ANCHORS:
    assert got == exp, (got, exp)
print("5. anchors:", len(ANCHORS))
checks["CHK_ANCHORS"] = len(ANCHORS)
json.dump(checks, open(CHK, "w"))
