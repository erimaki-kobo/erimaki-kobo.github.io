#!/usr/bin/env python3
"""Arguments accepted by PEFT config classes, Transformers TrainingArguments / Trainer and TRL configs / trainers,
at every final release tag. Reads the source with ast; nothing from the repositories is imported or run.

usage: python3 -I args_hist.py HIST_DIR > args_hist.json
HIST_DIR holds bare clones peft.git, trl.git (full) and transformers.git (--filter=blob:none is enough: the few
files read per tag are fetched in one batch).

Per class and release: the keyword arguments its constructor accepts.
  - a class that writes its own __init__: the parameters of that __init__ (TRL trainers, Trainer)
  - otherwise: the dataclass fields of the class and of its base classes found in the same package
    (LoraConfig + PeftConfig + PeftConfigMixin; SFTConfig + TRL's _BaseConfig)
A base class from another package is only named (TRL configs extend transformers.TrainingArguments).
@deprecate_kwarg("old", new_name="new") on __init__ is recorded as an alias: accepted with a warning.
"""
import ast, json, re, subprocess, sys

H = sys.argv[1]
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+(\.post\d+)?$")


def git(repo, *a, inp=None, text=True):
    p = subprocess.run(["git", "-C", "%s/%s.git" % (H, repo), *a], capture_output=True, text=text, input=inp)
    return p.stdout if p.returncode == 0 else None


def tags_of(repo, first=None):
    out = git(repo, "for-each-ref", "refs/tags", "--format=%(refname:lstrip=2)|%(creatordate:short)")
    rows = [l.split("|") for l in out.splitlines() if TAG_RE.match(l.split("|")[0])]
    key = lambda t: [int(x) for x in re.findall(r"\d+", t)]
    rows.sort(key=lambda r: key(r[0]))
    if first:
        rows = [r for r in rows if key(r[0]) >= key(first)]
    return rows


def name_of(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return name_of(node.func)
    if isinstance(node, ast.Subscript):
        return name_of(node.value)
    return None


def classes_in(src):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {}
    out = {}
    for n in tree.body:
        if not isinstance(n, ast.ClassDef):
            continue
        fields, init, aliases, var_kw = [], None, {}, False
        for st in n.body:
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                ann = ast.unparse(st.annotation)
                if "ClassVar" in ann:
                    continue
                v = st.value
                if isinstance(v, ast.Call) and name_of(v) == "field" and any(
                        k.arg == "init" and isinstance(k.value, ast.Constant) and k.value.value is False for k in v.keywords):
                    continue
                fields.append(st.target.id)
            elif isinstance(st, ast.FunctionDef) and st.name == "__init__":
                a = st.args
                init = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs if x.arg not in ("self",)]
                var_kw = a.kwarg is not None
                for d in st.decorator_list:
                    if isinstance(d, ast.Call) and name_of(d) == "deprecate_kwarg" and d.args and isinstance(d.args[0], ast.Constant):
                        new = None  # deprecate_kwarg(old_name, version, new_name=None, ...): new_name by keyword or third
                        if len(d.args) >= 3 and isinstance(d.args[2], ast.Constant) and isinstance(d.args[2].value, str):
                            new = d.args[2].value
                        for k in d.keywords:
                            if k.arg == "new_name" and isinstance(k.value, ast.Constant):
                                new = k.value.value
                        aliases[d.args[0].value] = new
        out[n.name] = {"bases": [b for b in (name_of(x) for x in n.bases) if b], "dc": any(name_of(d) == "dataclass" for d in n.decorator_list),
                       "fields": fields, "init": init, "aliases": aliases, "var_kw": var_kw}
    return out


def resolve(cmap, name, seen=()):
    """(accepted names, aliases, external bases) of class `name` in one release."""
    c = cmap[name]
    if c["init"] is not None:
        return list(c["init"]), dict(c["aliases"]), [], c["var_kw"]
    names, ext = [], []
    for b in c["bases"]:
        if b in cmap and b not in seen and b != name:
            bn, _, be, _ = resolve(cmap, b, seen + (name,))
            names += [x for x in bn if x not in names]
            ext += [x for x in be if x not in ext]
        elif b not in ("object", "Generic", "ABC", "Enum", "str", "dict"):
            ext.append(b)
    names += [x for x in c["fields"] if x not in names]
    return names, {}, ext, False


def tree_files(repo, tag, prefixes):
    out = git(repo, "ls-tree", "-r", tag, "--", *prefixes) or ""
    rows = []
    for l in out.splitlines():
        meta, path = l.split("\t", 1)
        if path.endswith(".py"):
            rows.append((meta.split()[2], path))
    return rows


def run(repo, prefixes, want, first=None, prefetch=False):
    tags = tags_of(repo, first)
    per_tag_files = {t: tree_files(repo, t, prefixes) for t, _ in tags}
    blobs = sorted({sha for fs in per_tag_files.values() for sha, _ in fs})
    if prefetch:  # blobless clone: fetch every needed blob in one request instead of one request per file
        have = set((git(repo, "cat-file", "--batch-check=%(objectname) %(objecttype)", "--batch-all-objects") or "").split())
        need = [b for b in blobs if b not in have]
        if need:
            subprocess.run(["git", "-C", "%s/%s.git" % (H, repo), "-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "origin",
                            "--no-tags", "--no-write-fetch-head", "--recurse-submodules=no", "--filter=blob:none", "--stdin"],
                           input="\n".join(need) + "\n", text=True, check=True)
    cache = {}
    def parsed(sha):
        if sha not in cache:
            cache[sha] = classes_in(git(repo, "cat-file", "blob", sha) or "")
        return cache[sha]
    res = {"tags": [t for t, _ in tags], "dates": [d for _, d in tags], "classes": {}}
    for i, (t, _) in enumerate(tags):
        cmap = {}
        for sha, path in per_tag_files[t]:
            for cn, info in parsed(sha).items():
                if cn in cmap and len(cmap[cn]["fields"]) + len(cmap[cn]["init"] or []) >= len(info["fields"]) + len(info["init"] or []):
                    continue
                cmap[cn] = info
        for cn in cmap:
            if not want(cn, cmap[cn]):
                continue
            names, aliases, ext, var_kw = resolve(cmap, cn)
            if not names:
                continue
            rec = res["classes"].setdefault(cn, {"p": {}, "alias": {}, "ext": {}, "has": [], "kw": []})
            def add(d, k):
                r = d.setdefault(k, [])
                if r and r[-1][1] == i - 1:
                    r[-1][1] = i
                else:
                    r.append([i, i])
            for x in names:
                add(rec["p"], x)
            for old, new in aliases.items():
                if old not in names:
                    add(rec["alias"], old + ">" + (new or ""))
            for e in ext:
                add(rec["ext"], e)
            if var_kw:
                add({"kw": rec["kw"]}, "kw")
            if rec["has"] and rec["has"][-1][1] == i - 1:
                rec["has"][-1][1] = i
            else:
                rec["has"].append([i, i])
        print(repo, t, len(cmap), file=sys.stderr, flush=True)
    return res


def peft_types(tag):
    """{PEFT_TYPE: config class} at one tag, from the register_peft_method(name=..., config_cls=...) calls."""
    m = {}
    for sha, path in tree_files("peft", tag, ["src/peft"]):
        src = git("peft", "cat-file", "blob", sha) or ""
        if "register_peft_method" not in src:
            continue
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Call) and name_of(n) == "register_peft_method":
                kw = {k.arg: k.value for k in n.keywords}
                if isinstance(kw.get("name"), ast.Constant) and name_of(kw.get("config_cls")):
                    m[kw["name"].value.upper()] = name_of(kw["config_cls"])
    return m


def peft_forward():
    """First PEFT release whose loader drops unknown config keys with a warning instead of raising TypeError."""
    for t, _ in tags_of("peft"):
        src = git("peft", "show", "%s:src/peft/config.py" % t) or git("peft", "show", "%s:src/peft/utils/config.py" % t) or ""
        if "got an unexpected keyword argument" in src and "Unexpected keyword arguments" in src and "ignored" in src:
            return t
    return None


out = {
    "peft_types": peft_types(tags_of("peft")[-1][0]),
    "peft_forward": peft_forward(),
    "peft": run("peft", ["src/peft"], lambda n, c: n.endswith("Config") and c["init"] is None),
    "trl": run("trl", ["trl"], lambda n, c: (n.endswith("Config") and c["init"] is None) or (n.endswith("Trainer") and c["init"] is not None)),
    "transformers": run("transformers", ["src/transformers/training_args.py", "src/transformers/training_args_seq2seq.py",
                                         "src/transformers/trainer.py", "src/transformers/trainer_seq2seq.py"],
                        lambda n, c: n in ("TrainingArguments", "Seq2SeqTrainingArguments", "Trainer", "Seq2SeqTrainer"),
                        first="v4.0.0", prefetch=True),
}
json.dump(out, sys.stdout, separators=(",", ":"))
