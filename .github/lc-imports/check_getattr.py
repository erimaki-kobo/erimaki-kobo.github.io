#!/usr/bin/env python3
"""Second reading of the names served through __getattr__, by regular expressions: in every module file that defines
__getattr__, the quoted names in __all__ = [...] and the quoted keys of `"Name": "module"` lines must all be among the
names read for that module. Usage: python3 -I check_getattr.py <clone> names_hist_after_getattr.json <roots as in getattr_hist>"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch
REPO, H, ROOTS = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
default, over = ROOTS.split("|")[0], [x.split("=", 1) for x in ROOTS.split("|")[1:]]
root_of = lambda t: next((r for pre, r in over if t.split("==")[-1].lstrip("v").startswith(pre)), default)
n_files = n_names = 0
for root in sorted({root_of(t) for t in H["tags"]}):
    tags = [t for t in H["tags"] if root_of(t) == root]
    want, text = fetch.load(REPO, tags, root=root)
    for t in tags:
        for p, sha in want[t].items():
            src = text[sha]
            if not re.search(r"^def __getattr__", src, re.M):
                continue
            m = p[:-3].replace("/", ".")
            m = m[:-len(".__init__")] if m.endswith(".__init__") else "" if m == "__init__" else m
            names = set()
            a = re.search(r"^__all__\s*=\s*\[(.*?)^\]", src, re.M | re.S)
            if a:
                names |= set(re.findall(r'"(\w+)"', a.group(1)))
            names |= set(re.findall(r'^\s+"(\w+)":\s*"[\w.]+",?\s*$', src, re.M))
            miss = names - set(H["mods"][t].get(m, []))
            assert not miss, (t, p, sorted(miss)[:5])
            n_files += 1
            n_names += len(names)
print("__getattr__ modules checked: %d file versions, %d names, all among the names read" % (n_files, n_names))
