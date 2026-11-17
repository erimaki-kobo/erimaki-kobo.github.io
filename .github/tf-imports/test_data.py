#!/usr/bin/env python3
"""Second reading of the same releases, by other means than names_hist.py. Nothing is imported or run.

Usage: python3 -I test_data.py <transformers clone> names_hist.json [checks.json to write for build_page.py]
 1. Lazy releases keep a static mirror of the runtime lists: the `from .x import A` statements under
    `if TYPE_CHECKING:` (the project's own utils/check_inits.py keeps the two halves equal). The names read
    from `_import_structure` must equal the names of that mirror. Where the mirror says `from .models import *`
    (define_import_structure releases) only names outside models/ are compared.
 2. For define_import_structure releases, `__all__` of every model file is read again line by line, the way
    transformers' own fetch__all__ does, and compared with the ast reading.
 3. Anchors: facts known from release notes and forum threads.
"""
import ast, json, re, subprocess, sys
REPO, H = sys.argv[1], json.load(open(sys.argv[2]))


def show(spec):
    return subprocess.run(["git", "-C", REPO, "show", spec], capture_output=True, text=True, check=True).stdout


def root(t):
    return "src/transformers" if subprocess.run(["git", "-C", REPO, "ls-tree", t, "--", "src/transformers"],
                                                capture_output=True, text=True).stdout.strip() else "transformers"


bad = 0
checked = same = most = 0
worst = []
for t in H["tags"]:
    top = H["top"][t]
    if top["kind"] != "lazy":
        continue
    tree = ast.parse(show("%s:%s/__init__.py" % (t, root(t))))
    tc = [n for n in ast.walk(tree) if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "TYPE_CHECKING"]
    assert len(tc) == 1, (t, len(tc))
    mirror, star_models = set(), False
    for n in ast.walk(ast.Module(body=tc[0].body, type_ignores=[])):
        if isinstance(n, ast.ImportFrom) and n.level >= 1:
            if (n.module or "").startswith("utils.dummy_"):
                continue
            for a in n.names:
                if a.name == "*":
                    star_models |= (n.module == "models")
                else:
                    mirror.add(a.asname or a.name)
    mine = {n for n, m in top["names"].items() if not (star_models and m.startswith("models."))}
    assert star_models == (t in H["scan_models"]), t
    # The mirror must not know a name the reading missed (TFMarian is upstream's own typo for TFMarianModel, v4.2-v4.4).
    # The other direction is upstream forgetting to mirror a runtime name; those names do import, so they are only counted.
    a, b = sorted(mine - mirror), sorted(mirror - set(top["names"]) - {"TFMarian"})
    checked += 1
    same += not a and not b
    most = max(most, len(a))
    if b or len(a) > 30:
        bad += 1
        worst.append((t, len(mine), a[:6], b[:6], len(a), len(b)))
print("1. runtime lists vs TYPE_CHECKING mirror: %d lazy releases; identical in %d; a mirrored name the reading lacks: %d releases; "
      "most runtime names upstream left out of the mirror in one release: %d" % (checked, same, bad, most))
for w in worst:
    print("   ", w)

# 2. line-based __all__
def fetch_all_lines(text):
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("__all__"):
            break
    else:
        return []
    if lines[i].rstrip().endswith("]"):
        return [x.strip("\"' ") for x in lines[i].split("=", 1)[1].strip().strip("[]").split(",") if x.strip()]
    out = []
    for l in lines[i + 1:]:
        if l.strip() == "]":
            break
        if l.strip() and not l.strip().startswith("#"):
            out.append(l.split("#")[0].strip().strip("\"', "))
    return out


diff2 = files = 0
for t in (H["scan_models"][0], H["scan_models"][len(H["scan_models"]) // 2], H["scan_models"][-1]):
    r = root(t)
    names = set()
    ls = subprocess.run(["git", "-C", REPO, "ls-tree", "-r", "--name-only", t, "--", r + "/models"], capture_output=True, text=True).stdout.split()
    paths = [p for p in ls if p.endswith(".py") and not p.endswith("__init__.py")]
    batch = subprocess.run(["git", "-C", REPO, "cat-file", "--batch"], input="".join("%s:%s\n" % (t, p) for p in paths).encode(),
                           capture_output=True, check=True).stdout
    i = 0
    for p in paths:
        nl = batch.index(b"\n", i)
        n = int(batch[i:nl].split()[2])
        text = batch[nl + 1:nl + 1 + n].decode("utf-8", "replace")
        i = nl + 2 + n
        files += 1
        if "__all__" in text:
            names |= set(fetch_all_lines(text))
    mine = {n for n, m in H["top"][t]["names"].items() if m.startswith("models.")}
    # names that __init__.py itself lists first keep that module key, so compare as "every __all__ name is known"
    missing = sorted(names - set(H["top"][t]["names"]))
    extra = sorted(mine - names)
    if missing or extra:
        diff2 += 1
        print("   ", t, "missing", missing[:8], "extra", extra[:8])
print("2. __all__ read line by line: 3 releases, %d files, %d differ" % (files, diff2))

# 3. anchors
def has(kind, tag, name):
    d = H[kind].get(tag)
    return d is not None and name in (d["names"] if kind == "top" else d)


anchors = [
    ("top", "v4.49.0", "AdamW", True), ("top", "v4.50.0", "AdamW", False),
    ("top", "v4.57.1", "TFBertModel", True), ("top", "v5.0.0", "TFBertModel", False),
    ("top", "v4.57.1", "FlaxBertModel", True), ("top", "v5.0.0", "FlaxBertModel", False),
    ("top", "v2.11.0", "AutoModelForSeq2SeqLM", False), ("top", "v3.0.0", "AutoModelForSeq2SeqLM", True),
    ("top", "v2.11.0", "AutoModelWithLMHead", True),
    ("top", "v4.28.0", "LlamaTokenizer", True), ("top", "v4.27.0", "LlamaTokenizer", False),
    ("top", "v4.57.1", "pipeline", True), ("top", "v5.23.0", "pipeline", True), ("top", "v2.2.0", "pipeline", False), ("top", "v2.3.0", "pipeline", True),
    ("top", "v4.41.0", "Conversation", True), ("top", "v4.42.0", "Conversation", False),
    ("utils", "v4.27.0", "is_tokenizers_available", True),
    ("utils", "v4.27.0", "FLAX_WEIGHTS_NAME", True),
]
wrong = [a for a in anchors if has(*a[:3]) != a[3]]
print("3. anchors: %d, wrong %s" % (len(anchors), wrong))
if len(sys.argv) > 3:
    json.dump({"CHK_LAZY": checked, "CHK_SAME": same, "CHK_MOST": most, "CHK_FILES": files, "CHK_ANCHORS": len(anchors)}, open(sys.argv[3], "w"))
sys.exit(1 if bad or diff2 or wrong else 0)
