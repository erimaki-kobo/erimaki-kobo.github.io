#!/usr/bin/env python3
"""Names the current loader handles identically: same branch body in the tokenizer_pre if/else chain of
src/llama-vocab.cpp at HEAD. Also the first release where each converter file held the hash list.
Usage: groups.py LLAMA_REPO groups.json paths.json"""
import json, re, subprocess, sys
REPO, OUT, PATHS = sys.argv[1:4]
def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True).stdout
s = git("show", "HEAD:src/llama-vocab.cpp")
a = s.index("if (tokenizer_pre.empty())")
b = s.index("unknown pre-tokenizer type", a)
parts = re.split(r"\}\s*else if \(", s[a:b])
by = {}
for p in parts[1:]:
    cond, body = p[:p.index("{")], p[p.index("{") + 1:]
    names = re.findall(r'tokenizer_pre == "([^"]+)"', cond)
    assert names, cond
    body = re.sub(r"//[^\n]*", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    by.setdefault(body, []).extend(names)
groups = [v for v in by.values() if len(v) > 1]
json.dump(groups, open(OUT, "w"), indent=1)
print("branches", len(parts) - 1, "groups", len(groups), file=sys.stderr)
# where the converter list lived: first tag containing the first commit where each file has 'chkhsh == "'
res = {}
for f in ["convert-hf-to-gguf.py", "convert_hf_to_gguf.py", "conversion/base.py"]:
    log = git("log", "--first-parent", "--reverse", "--format=%H", "-S", 'chkhsh == "', "--", f).split()
    if log:
        t = git("describe", "--contains", "--match", "b*", log[0]).strip()
        res[f] = re.match(r"(b\d+)", t).group(1)
json.dump(res, open(PATHS, "w"), indent=1)
print(res, file=sys.stderr)
