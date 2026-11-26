#!/usr/bin/env python3
"""Cross-check pretok_raw.json against an independent read: at sampled bNNNN tags, grep the candidate
source files for chkhsh / tokenizer_pre entries and compare with the sets the history walk implies
for that tag. Usage: validate.py LLAMA_REPO pretok_raw.json [STEP]"""
import json, re, subprocess, sys
REPO, DATA = sys.argv[1], sys.argv[2]
STEP = int(sys.argv[3]) if len(sys.argv) > 3 else 400
FILES_PY = ["conversion/base.py", "convert_hf_to_gguf.py", "convert-hf-to-gguf.py"]
FILES_CPP = ["src/llama-vocab.cpp", "src/llama-model.cpp", "src/llama.cpp", "llama.cpp"]
d = json.load(open(DATA))


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True).stdout


def bn(t):
    return int(t[1:])


fp = git("rev-list", "--first-parent", "--reverse", d["head"]).split()
pos = {c: i for i, c in enumerate(fp)}
tags = sorted([t for t in git("tag", "--list", "b*").split() if re.fullmatch(r"b\d+", t) and bn(t) >= 2761], key=bn)
sample = tags[::STEP] + [tags[-1]] + ["b4417", "b4440", "b4463", "b4351", "b4360", "b4612", "b4620", "b9165", "b9219"]
bad = 0
for t in sample:
    if t not in tags:
        continue
    tc = git("rev-parse", f"refs/tags/{t}^{{commit}}").strip()
    if tc not in pos:
        print(t, "not on first-parent line, skipped")
        continue
    ti = pos[tc]
    hs, ns = set(), set()
    for f in FILES_PY:
        s = git("show", f"refs/tags/{t}:{f}")
        hs |= set(re.findall(r'chkhsh == "([0-9a-f]{64})"', s))
    for f in FILES_CPP:
        s = git("show", f"refs/tags/{t}:{f}")
        ns |= set(re.findall(r'tokenizer_pre == "([^"]+)"', s))

    def live(spans):
        return any(pos[s["added"]] <= ti and not (s["removed"] and pos[s["removed"]] <= ti) for s in spans)
    eh = {h for h, e in d["hashes"].items() if live(e["spans"])}
    en = {n for n, e in d["names"].items() if live(e["spans"])}
    ok = hs == eh and ns == en
    bad += not ok
    print(t, "hashes", len(hs), "names", len(ns), "OK" if ok else "MISMATCH",
          "" if ok else (sorted(x[:10] for x in hs ^ eh), sorted(ns ^ en)), flush=True)
print("mismatching tags:", bad)
checked = sum(1 for t in sample if t in tags)
json.dump({"tags_checked": checked, "mismatches": bad}, open("validate.json", "w"))
sys.exit(1 if bad else 0)
