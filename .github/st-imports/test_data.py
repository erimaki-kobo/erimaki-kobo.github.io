#!/usr/bin/env python3
"""Second readings of names_hist.py + build_data.py for one library. Nothing is installed or run.

Usage: python3 -I test_data.py <lib> <clone> dates.json names_hist.json <lib>.json <source root> checks.json
 1. Type-checking copy (lazy packages only, trl from 0.8.0): the block under `if TYPE_CHECKING:` imports the same names
    eagerly. Compare it with the lazy reading; the differences must stay a short known list.
 2. Plain text, top level: a top-level name appears as a word in __init__.py of every release that has it (or is a
    submodule), and is not imported there in the release on either side of its range.
 3. Plain text, definitions: every `class X`, `def X`, `X =` at column 0 found by a regular expression in a module that
    does not replace itself is among the names read for that module.
 4. Anchors: facts from public error reports and from the files themselves.
"""
import ast, json, os, re, sys, warnings, collections
warnings.simplefilter("ignore", SyntaxWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch
LIB, REPO, PYPI, H, D, ROOT, CHK = sys.argv[1], sys.argv[2], json.load(open(sys.argv[3])), json.load(open(sys.argv[4])), json.load(open(sys.argv[5])), sys.argv[6], sys.argv[7]
tags = H["tags"]
want, text = fetch.load(REPO, tags, root=ROOT)   # tags come from names_hist.json, so --every-release carries over
R, T = D["releases"], D["ranges"]
checks = {}


def modname(p):
    m = p[:-3].replace("/", ".")
    return m[:-len(".__init__")] if m.endswith(".__init__") else "" if m == "__init__" else m


# 1. type-checking copy
n_mod = n_same = 0
diff = collections.defaultdict(set)
for t in tags:
    mods = {modname(p): sha for p, sha in want[t].items()}
    for m in H["lazy"][t]:
        tree = ast.parse(text[mods[m]])
        got = set()

        def walk(body, on):
            for n in body:
                if isinstance(n, ast.If):
                    tc = "TYPE_CHECKING" in {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)}
                    walk(n.body, on or tc)
                    walk(n.orelse, on)
                elif isinstance(n, ast.Try):
                    for part in (n.body, n.orelse, n.finalbody, *[h.body for h in n.handlers]):
                        walk(part, on)
                elif on and isinstance(n, ast.ImportFrom) and n.level >= 1:
                    for a in n.names:
                        assert a.name != "*", (t, m)
                        got.add(a.asname or a.name)
        walk(tree.body, False)
        pre = m + "." if m else ""
        children = {k[len(pre):] for k in mods if k.startswith(pre) and k != m and "." not in k[len(pre):]}
        head = {a.asname or a.name for n in tree.body if isinstance(n, ast.ImportFrom) and n.level >= 1 for a in n.names}
        mine = set(H["mods"][t][m]) - children - head - {"__version__"}
        got -= children
        n_mod += 1
        if mine == got:
            n_same += 1
        for n in mine - got:
            diff[("lazy only", m, n)].add(t)
        for n in got - mine:
            diff[("type-checking only", m, n)].add(t)
for k, ts in sorted(diff.items()):
    ts = sorted(ts, key=fetch.ver)
    print("   ", k, ts[0], "..", ts[-1], len(ts))
print("1. lazy package-release pairs:", n_mod, "| identical:", n_same, "| names in one place only:", len(diff))
assert len(diff) <= 25, len(diff)
checks.update({"CHK_TC_MODS": n_mod, "CHK_TC_SAME": n_same, "CHK_TC_DIFF": len(diff)})
tc_only_top = {(n, t) for (k, m, n), ts in diff.items() if k == "type-checking only" and m == "" for t in ts}

# 2. plain text, top level
stale_top = {(n, i) for m, n, key, kind, a, b in D["stale"] if m == "" for i in range(a, b or len(R))}
init = [text[want[t]["__init__.py"]] for t in tags]
words = [set(re.findall(r"[A-Za-z_]\w*", s)) for s in init]
# `from .features import *` in __init__.py (and stars inside those): the words of the starred modules count too
def star_words(t, path, seen):
    if path in seen or path not in want[t]:
        return set()
    seen.add(path)
    src = text[want[t][path]]
    pkg = path.rsplit("/", 1)[0] + "/" if "/" in path else ""
    out = set()
    for mod in re.findall(r"^\s*from \.([\w.]+) import \*", src, re.M):
        base = pkg + mod.replace(".", "/")
        for q in (base + ".py", base + "/__init__.py"):
            if q in want[t]:
                out |= set(re.findall(r"[A-Za-z_]\w*", text[want[t][q]])) | star_words(t, q, seen)
    return out


for i, t in enumerate(tags):
    words[i] |= star_words(t, "__init__.py", set())
files_at = [set(want[t]) for t in tags]
# a submodule name (at the top, or one a star import of a package carries along)
is_sub = lambda n: any(any(p == n + ".py" or p.endswith("/" + n + ".py") or p.startswith(n + "/") or ("/" + n + "/") in "/" + p for p in f) for f in files_at)
n_inside = n_edges = 0
for n, ri in D["names"][""].items():
    r = T[ri]
    for a, b in zip(r[::2], r[1::2]):
        for i in range(a, b or len(R)):
            assert n in words[i] or is_sub(n), ("has it, text does not", n, R[i][0])
            n_inside += 1
        for i in ([a - 1] if a > 0 else []) + ([b] if b else []):
            if (n, i) in stale_top or is_sub(n) or (n, tags[i]) in tc_only_top:
                continue
            lazy_i = "" in H["lazy"][tags[i]]
            for l in init[i].splitlines():
                if re.search(r"\b%s\b" % re.escape(n), l) and not l.lstrip().startswith("#"):
                    # a lazy module serves only its table: a name bound by an import at its head is not an attribute of it
                    assert ('"' + n + '"' not in l) if lazy_i else ("import" not in l and '"' + n + '"' not in l), ("text has it", n, R[i][0], l)
            n_edges += 1
print("2. top-level names:", len(D["names"][""]), "| name-release pairs found in the text:", n_inside, "| range edges checked:", n_edges)
checks.update({"CHK_TOP": len(D["names"][""]), "CHK_TOP_PAIRS": n_inside, "CHK_TOP_EDGES": n_edges})

# 3. definitions by regular expression
rx = re.compile(r"^(?:class|def|async def)\s+([A-Za-z_]\w*)|^([A-Za-z_]\w*)\s*(?::[^=\n]+)?=(?!=)", re.M)
n_files = n_defs = 0
seen = set()
for t in tags:
    lazy = set(H["lazy"][t])
    for p, sha in want[t].items():
        m = modname(p)
        if m in lazy or (sha, m) in seen:
            continue
        seen.add((sha, m))
        src = re.sub(r'("""|\'\'\')(.*?)\1', lambda q: "\n" * q.group(0).count("\n"), text[sha], flags=re.S)
        found = {a or b for a, b in rx.findall(src)} - set(__import__("keyword").kwlist)   # "try:  # Python >= 3.8" is not a definition
        miss = found - set(H["mods"][t][m])
        assert not miss, (t, p, sorted(miss)[:5])
        n_files += 1
        n_defs += len(found)
print("3. file versions:", n_files, "| definitions found by the regular expression, all among the names read:", n_defs)
checks.update({"CHK_DEF_FILES": n_files, "CHK_DEFS": n_defs})


# 4. anchors
def mspan(m):
    r = T[D["mods"][m]]
    return [(R[a][0], R[b][0] if b else None) for a, b in zip(r[::2], r[1::2])]


def span(m, n):
    r = T[D["names"][m][n]]
    return [(R[a][0], R[b][0] if b else None) for a, b in zip(r[::2], r[1::2])]


A = {
    "accelerate": lambda: [
        (span("utils", "is_npu_available"), [("0.21.0", None)]),         # discuss.huggingface.co/t/.../51177 (peft on an older accelerate)
        (span("", "PartialState"), [("0.17.0", None)]),                   # zindi 16583, discuss.huggingface.co/t/.../44605
        (span("utils", "is_safetensors_available"), [("0.15.0", "0.25.0")]),  # discuss.huggingface.co/t/.../76621
        (span("utils", "is_tpu_available"), [("0.1.0", "0.28.0")]),
        (span("", "Accelerator"), [("0.1.0", None)]),
    ],
    "peft": lambda: [
        (span("", "prepare_model_for_int8_training"), [("0.2.0", "0.10.0")]),
        (span("", "prepare_model_for_kbit_training"), [("0.4.0", None)]),
        (span("", "AutoPeftModelForCausalLM"), [("0.4.0", None)]),
        (span("", "LoraConfig"), [("0.0.1", None)]),
        (span("", "BoneConfig")[-1][1], "0.19.0"),
    ],
    "sentence_transformers": lambda: [
        (mspan("models"), [("0.1.0", None)]),                     # still importable after 5.4.0, through the deprecated-path finder
        (span("models", "Transformer"), [("0.3.0", None)]),
        (span("models", "BERT"), [("0.1.0", "2.0.0")]),
        (span("util", "cached_download"), [("2.0.0", "2.3.0")]),   # simplified.guide: ST 2.2.2 imports cached_download
        (span("util", "snapshot_download"), [("2.0.0", "5.1.0")]),
        (span("", "SentenceTransformer"), [("0.1.0", None)]),
        (span("", "SparseEncoder"), [("5.0.0", None)]),
        (span("", "CrossEncoder"), [("0.4.0", None)]),
    ],
    "timm": lambda: [
        (mspan("layers"), [("0.9.0", None)]),                    # github.com/huggingface/pytorch-image-models/discussions/1772 (No module named 'timm.layers')
        (mspan("models.layers.norm"), [("0.4.9", "0.9.0")]),     # forums.fast.ai/t/.../106471, pickled models (No module named 'timm.models.layers.norm')
        (mspan("models.layers"), [("0.2.1", None)]),             # kept as a deprecation mapping
        (span("models.layers", "DropPath"), [("0.2.1", None)]),
        (span("layers", "DropPath"), [("0.9.0", None)]),
        (span("models._efficientnet_blocks", "SqueezeExcite"), [("0.9.0", None)]),
        (span("models.efficientnet_blocks", "SqueezeExcite"), [("0.2.1", "0.9.0")]),
        (span("", "create_model"), [("0.1.1", None)]),
    ],
    "datasets": lambda: [
        (span("", "load_metric"), [("1.0.0", "3.0.0")]),                 # discuss.huggingface.co/t/.../107524 ("removed in datasets@3.0.0")
        (span("", "list_datasets"), [("1.0.0", "3.0.0")]),
        (span("", "set_caching_enabled"), [("1.3.0", "3.0.0")]),
        (span("", "disable_caching"), [("2.0.0", None)]),
        (span("", "load_dataset"), [("1.0.0", None)]),
        (span("", "List"), [("4.0.0", None)]),
        (span("arrow_writer", "SchemaInferenceError"), [("2.7.0", None)]),  # discuss.huggingface.co/t/trl-importation-error-on-kaggle/66817
        (span("utils.py_utils", "asdict"), [("2.4.0", None)]),
    ],
    "trl": lambda: [
        (span("", "DataCollatorForCompletionOnlyLM"), [("0.5.0", "0.20.0")]),
        (span("", "SFTTrainer"), [("0.5.0", None)]),
        (span("", "PPOTrainer"), [("0.2.0", "0.29.0")]),
        (span("", "setup_chat_format"), [("0.8.0", "0.26.0")]),
        (span("", "SFTScriptArguments"), [("0.9.3", "0.13.0")]),
        (span("", "ScriptArguments"), [("0.12.0", None)]),
        (span("", "GRPOTrainer"), [("0.14.0", None)]),
        (R[D["lazy_from"]][0] if D["lazy_from"] is not None else None, "0.8.0"),
    ],
}[LIB]()
for got, exp in A:
    assert got == exp, (got, exp)
print("4. anchors:", len(A))
checks["CHK_ANCHORS"] = len(A)
json.dump(checks, open(CHK, "w"))
