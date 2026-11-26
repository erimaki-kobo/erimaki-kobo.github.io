#!/usr/bin/env python3
"""Walk the first-parent history of llama.cpp (from 2024-04) and record, commit by commit,
  - convert side: every chkhsh in get_vocab_base_pre() (convert-hf-to-gguf.py -> convert_hf_to_gguf.py -> conversion/base.py)
    with the name it maps to and the "# ref:" model URL above it
  - load side: every tokenizer_pre == "<name>" the loader accepts (llama.cpp -> src/llama.cpp -> src/llama-vocab.cpp)
Each hash / name gets: first commit that has it, the first bNNNN tag containing that commit,
and (if it later disappeared) the commit that removed it.
Input: raw_fp.txt (git log --first-parent --reverse --raw ...). Output: pretok_raw.json
Usage: extract_pretok.py LLAMA_REPO RAW_FP OUT"""
import json, re, subprocess, sys
REPO, RAW, OUT = sys.argv[1:4]
CONV = ["conversion/base.py", "convert_hf_to_gguf.py", "convert-hf-to-gguf.py"]
VOCAB = ["src/llama-vocab.cpp", "src/llama-model.cpp", "src/llama.cpp", "llama.cpp"]
HASH_RE = re.compile(r'if (chkhsh == "[0-9a-f]{64}"(?:\s+or\s+chkhsh == "[0-9a-f]{64}")*):\s*\n((?:[ \t]*#[^\n]*\n)*)[ \t]*res = "([^"]+)"')
NAME_RE = re.compile(r'tokenizer_pre == "([^"]+)"')


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, check=True).stdout


def blob(oid, cache={}):
    if oid not in cache:
        cache[oid] = git("cat-file", "blob", oid)
    return cache[oid]


def parse_conv(src):
    out = {}
    for cond, comments, name in HASH_RE.findall(src):
        ref = re.search(r"#\s*ref:\s*(\S+)", comments)
        for h in re.findall(r"[0-9a-f]{64}", cond):
            out[h] = {"name": name, "ref": ref.group(1) if ref else None}
    return out


def parse_vocab(src):
    return set(NAME_RE.findall(src))


commits = []
cur = None
for line in open(RAW, encoding="utf-8"):
    line = line.rstrip("\n")
    if line.startswith("C "):
        _, h, d, *s = line.split(" ", 3)
        cur = {"hash": h, "date": d, "subject": s[0] if s else "", "changes": {}}
        commits.append(cur)
    elif line.startswith(":") and cur is not None:
        meta, path = line.split("\t", 1)
        new = meta.split()[3]
        cur["changes"][path] = None if set(new) == {"0"} else new

state = {}  # path -> blob oid
hashes, names = {}, {}
prev_h, prev_n = {}, set()
for c in commits:
    state.update(c["changes"])
    h_now, n_now = {}, set()
    for p in CONV:
        if state.get(p):
            s = blob(state[p])
            if 'chkhsh == "' in s:
                h_now = parse_conv(s)
                break
    for p in VOCAB:
        if state.get(p):
            s = blob(state[p])
            if "tokenizer_pre ==" in s:
                n_now = parse_vocab(s)
                break
    # a commit that moves the list (file split) can leave both empty for one step; skip such gaps
    if not h_now and prev_h:
        h_now = prev_h
    if not n_now and prev_n:
        n_now = prev_n
    for k, v in h_now.items():
        e = hashes.setdefault(k, {"name": v["name"], "ref": v["ref"], "spans": []})
        if k not in prev_h:
            e["spans"].append({"added": c["hash"], "added_date": c["date"], "added_subject": c["subject"], "removed": None})
        elif v["name"] != prev_h[k]["name"]:
            e.setdefault("renames", []).append({"commit": c["hash"], "date": c["date"], "from": prev_h[k]["name"], "to": v["name"]})
        e["name"], e["ref"] = v["name"], v["ref"] or e["ref"]
    for k in prev_h:
        if k not in h_now:
            hashes[k]["spans"][-1].update(removed=c["hash"], removed_date=c["date"], removed_subject=c["subject"])
    for k in n_now:
        e = names.setdefault(k, {"spans": []})
        if k not in prev_n:
            e["spans"].append({"added": c["hash"], "added_date": c["date"], "added_subject": c["subject"], "removed": None})
    for k in prev_n:
        if k not in n_now:
            names[k]["spans"][-1].update(removed=c["hash"], removed_date=c["date"], removed_subject=c["subject"])
    prev_h, prev_n = h_now, n_now

tag_cache = {}


def first_tag(commit):
    if commit not in tag_cache:
        try:
            out = git("describe", "--contains", "--match", "b*", commit).strip()
            m = re.match(r"(b\d+)", out)
            tag_cache[commit] = m.group(1) if m else None
        except subprocess.CalledProcessError:
            tag_cache[commit] = None
    return tag_cache[commit]


date_cache = {}


def tag_date(t):
    if t and t not in date_cache:
        date_cache[t] = git("log", "-1", "--format=%cd", "--date=short-local", t).strip()
    return date_cache.get(t)


for coll in (hashes, names):
    for k, e in coll.items():
        for sp in e["spans"]:
            sp["added_build"] = first_tag(sp["added"])
            sp["added_build_date"] = tag_date(sp["added_build"])
            if sp["removed"]:
                sp["removed_build"] = first_tag(sp["removed"])
                sp["removed_build_date"] = tag_date(sp["removed_build"])

head = git("rev-parse", "HEAD").strip()
head_tag = git("describe", "--tags", "--abbrev=0", "--match", "b*", head).strip()
json.dump({"head": head, "head_tag": head_tag, "head_tag_date": tag_date(head_tag),
           "head_date": git("log", "-1", "--format=%cd", "--date=short-local").strip(),
           "commits_walked": len(commits), "hashes": hashes, "names": names},
          open(OUT, "w"), indent=1, ensure_ascii=False)
print("commits", len(commits), "hashes", len(hashes), "names", len(names), "head_tag", head_tag, file=sys.stderr)
print("current hashes", sum(1 for e in hashes.values() if not e["spans"][-1]["removed"]),
      "current names", sum(1 for e in names.values() if not e["spans"][-1]["removed"]), file=sys.stderr)
print("removed hashes", [(k[:10], e["name"]) for k, e in hashes.items() if e["spans"][-1]["removed"]], file=sys.stderr)
print("removed names", [k for k, e in names.items() if e["spans"][-1]["removed"]], file=sys.stderr)
print("multi-span", [(k[:10], len(e["spans"])) for k, e in hashes.items() if len(e["spans"]) > 1] + [(k, len(e["spans"])) for k, e in names.items() if len(e["spans"]) > 1], file=sys.stderr)
