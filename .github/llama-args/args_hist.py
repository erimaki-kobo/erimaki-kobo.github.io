#!/usr/bin/env python3
"""History of llama.cpp's command-line options, from every commit that touched common/arg.cpp.

Usage: python3 -I args_hist.py <llama.cpp clone (--filter=blob:none is enough)> > args_hist.json
Nothing is compiled or run: common/arg.cpp is read as text. Each `add_opt(common_arg(...))` (earlier `llama_arg`)
gives the option's names, its negated names, the binaries it is registered for (set_examples / set_excludes),
its environment variable (set_env) and whether it is a stub that only says "the argument has been removed".
Every commit is mapped to the first bNNNN build tag that contains it. Dates are UTC commit dates.
"""
import bisect, json, os, re, subprocess, sys

REPO = sys.argv[1]
ENV = dict(os.environ, TZ="UTC")


def git(*a, inp=None):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, check=True, env=ENV, input=inp).stdout


STR = re.compile(r'"((?:[^"\\]|\\.)*)"')


def blocks(src):
    """Yield the text of every add_opt( ... ) call, matching parentheses outside string and char literals and comments."""
    for m in re.finditer(r"add_opt\(\s*(?:common_arg|llama_arg)\(", src):
        i, depth, n = m.end(), 2, len(src)
        while i < n and depth:
            c = src[i]
            if c == '"':
                i = STR.match(src, i).end()
                continue
            if c == "'":
                i = src.index("'", i + 2 if src[i + 1] == "\\" else i + 1) + 1
                continue
            if src.startswith("//", i):
                i = src.index("\n", i)
                continue
            if src.startswith("/*", i):
                i = src.index("*/", i) + 2
                continue
            depth += (c == "(") - (c == ")")
            i += 1
        yield src[m.end():i]


def brace(s, i):
    """s[i] == '{' -> (string literals inside the brace list, index after the closing brace)."""
    j, depth = i, 0
    while True:
        if s[j] == '"':
            j = STR.match(s, j).end()
            continue
        depth += (s[j] == "{") - (s[j] == "}")
        j += 1
        if depth == 0:
            return [x.group(1) for x in STR.finditer(s[i:j])], j


def options(src):
    out = []
    for b in blocks(src):
        i = b.index("{")
        names, j = brace(b, i)
        neg = []
        k = re.match(r"\s*,\s*\{", b[j:])
        if k:
            neg, j = brace(b, j + k.end() - 1)
        lam = b.find("[]", j)
        head = b[j:lam if lam > 0 else len(b)]
        help_ = "".join(x.group(1) for x in STR.finditer(head))
        ex = re.search(r"\.set_examples\(\{([^}]*)\}\)", b)
        exc = re.search(r"\.set_excludes\(\{([^}]*)\}\)", b)
        env = re.search(r'\.set_env\("([^"]+)"\)', b)
        removed = None
        if "arg_removed(" in b or "the argument has been removed" in help_:
            r = re.search(r'arg_removed\("((?:[^"\\]|\\.)*)"\)', b)
            removed = r.group(1) if r else help_.split("the argument has been removed", 1)[1].lstrip(". ")
        # the option's own deprecation warning starts with "DEPRECATED" (a warning about one value of an option does not)
        warn = next((x.group(1) for x in STR.finditer(b[lam:] if lam > 0 else "") if x.group(1).startswith("DEPRECATED")), None)
        names = [x for x in names if x.startswith("-")]
        if not names:
            continue
        out.append({"names": names, "neg": [x for x in neg if x.startswith("-")],
                    "ex": sorted(re.findall(r"LLAMA_EXAMPLE_(\w+)", ex.group(1))) if ex else None,
                    "exc": sorted(re.findall(r"LLAMA_EXAMPLE_(\w+)", exc.group(1))) if exc else [],
                    "env": env.group(1) if env else None, "removed": removed,
                    "deprecated": bool(re.search(r"deprecated", help_, re.I) or warn) and not removed,
                    "warn": re.sub(r"\\n", "", warn) if warn else None,
                    "help": re.sub(r"\\n", " ", help_)[:200]})
    return out


# ---- commits that touched the file, oldest first, with the blob at each ----
log = [l.split("\t", 2) for l in git("log", "--reverse", "--first-parent", "--date=short-local", "--format=%H\t%cd\t%s", "--", "common/arg.cpp").splitlines()]
shas = {}
for h, _, _ in log:
    t = git("ls-tree", h, "--", "common/arg.cpp").split()
    shas[h] = t[2]
have = set(git("cat-file", "--batch-check=%(objectname) %(objecttype)", "--batch-all-objects").split())
need = sorted(set(shas.values()) - have)
if need:
    subprocess.run(["git", "-C", REPO, "-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "origin", "--no-tags", "--no-write-fetch-head",
                    "--recurse-submodules=no", "--filter=blob:none", "--stdin"], input="\n".join(need) + "\n", text=True, check=True)

# ---- build tags on the first-parent line ----
order = {h: i for i, h in enumerate(git("rev-list", "--first-parent", "--reverse", "HEAD").split())}
tags = []
for l in git("for-each-ref", "--format=%(refname:short)\t%(objectname)\t%(*objectname)\t%(creatordate:short-local)", "refs/tags").splitlines():
    name, obj, peeled, d = l.split("\t")
    h = peeled or obj                                   # annotated tags point at a tag object
    if re.fullmatch(r"b\d+", name) and h in order:
        tags.append((order[h], int(name[1:]), d))
tags.sort()
tag_idx = [t[0] for t in tags]


def first_build(h):
    k = bisect.bisect_left(tag_idx, order[h])
    return None if k == len(tags) else [tags[k][1], tags[k][2]]


out = {"head": git("rev-parse", "HEAD").strip(), "head_date": git("log", "-1", "--date=short-local", "--format=%cd").strip(),
       "latest_build": [tags[-1][1], tags[-1][2]], "n_tags": len(tags), "commits": []}
cache = {}
for h, d, subj in log:
    if first_build(h) is None:
        # common/arg.cpp changed after the newest release tag: no build ships it yet, so it is left for the next run
        out["unreleased"] = out.get("unreleased", 0) + 1
        continue
    sha = shas[h]
    if sha not in cache:
        src = git("cat-file", "blob", sha)
        # neg_env: LLAMA_ARG_NO_X is read for an option that has negated names and LLAMA_ARG_X
        # underscore: "--ctx_size" is read as "--ctx-size"
        cache[sha] = (options(src), "neg_env" in src and "LLAMA_ARG_NO_" in src, "std::replace(arg.begin(), arg.end(), '_', '-')" in src)
    o, neg_env, underscore = cache[sha]
    out["commits"].append({"commit": h, "date": d, "subject": subj, "build": first_build(h), "options": o, "neg_env": neg_env, "underscore": underscore})
json.dump(out, sys.stdout, separators=(",", ":"))
print("commits", len(log), "blobs", len(cache), "tags", len(tags), "options at head", len(out["commits"][-1]["options"]), file=sys.stderr)
