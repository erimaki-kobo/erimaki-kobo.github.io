"""Extract llama.cpp's text-based special-token rules from src/llama-vocab.cpp at a tag, and find for each
EOG text the first bNNNN tag whose vocab code names it. Usage: python3 llama_eog_lists.py <llama.cpp bare clone> <tag> > out/llama_eog.json"""
import json, re, subprocess, sys, os
G, TAG = sys.argv[1], sys.argv[2]
def git(*a):
    p = subprocess.run(["git", "-C", G] + list(a), capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""
src = git("show", f"{TAG}:src/llama-vocab.cpp")
assert src
def block(after, until):
    i = src.index(after); j = src.index(until, i)
    return src[i:j]
def texts(b): return re.findall(r't\.first == "((?:[^"\\]|\\.)*)"', b)
dec = lambda s: s.encode().decode("unicode_escape").encode("latin-1").decode("utf-8") if "\\" in s else s
eot = texts(block("// find EOT token", "// find EOM token"))
eom = texts(block("// find EOM token", "// find FIM_PRE token"))
fim_pad = texts(block("// find FIM_PAD token", "// find FIM_REP token"))
fim_rep = texts(block("// find FIM_REP token", "// find FIM_SEP token"))
fim_sep = texts(block("// find FIM_SEP token", "\n        }\n")) if "// find FIM_SEP token" in src else []
eog_b = block("special_eog_ids.clear();", "// @ngxson : quick hack for gpt-oss")
eog_all = texts(eog_b)
flint = re.findall(r'LLAMA_VOCAB_PRE_TYPE_FLINT && \(([^)]*)\)', eog_b)
flint_texts = texts(flint[0]) if flint else []
eog = [t for t in eog_all if t not in flint_texts]
assert "<|eot_id|>" in eog and "<|im_end|>" in eog and "<end_of_turn>" in eog and len(eog) >= 20, eog
assert "<|fim_pad|>" in fim_pad and "<|file_sep|>" in fim_sep, (fim_pad, fim_sep)
assert 'has_return && has_call && has_end' in src and '"<rfl:parameter name=\\""' in src and '"<|plamo:eos|>"' in src
res = {"tag": TAG, "eot": eot, "eom": eom, "fim_pad": fim_pad, "fim_rep": fim_rep, "fim_sep": fim_sep, "eog": eog, "flint_only": flint_texts}
# first build naming each EOG text (in any file holding the vocab code), binary search over b-tags from b2702
tags = sorted([t for t in git("tag", "-l", "b[0-9]*").split() if re.fullmatch(r"b\d+", t)], key=lambda t: int(t[1:]))
dates = dict(l.split("|") for l in git("for-each-ref", "refs/tags/b*", "--format=%(refname:lstrip=2)|%(creatordate:short)").splitlines())
lo0 = tags.index("b2702"); hi0 = tags.index(TAG)
cache = {}
def code(tag):
    if tag not in cache:
        cache[tag] = "".join(git("show", f"{tag}:{p}") for p in ("src/llama-vocab.cpp", "src/llama.cpp", "llama.cpp"))
    return cache[tag]
first = {}
for t in sorted(set(eog + eot + eom)):
    lit = 't.first == "' + t + '"'
    lo, hi = lo0, hi0
    if lit in code(tags[lo]): first[t] = [tags[lo][1:], dates[tags[lo]], True]; continue
    while lo < hi:
        m = (lo + hi) // 2
        if lit in code(tags[m]): hi = m
        else: lo = m + 1
    first[t] = [tags[lo][1:], dates[tags[lo]], False]
    print(t, tags[lo], file=sys.stderr, flush=True)
res["first"] = first
json.dump(res, sys.stdout, ensure_ascii=False, indent=0)
