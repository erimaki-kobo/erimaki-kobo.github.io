#!/usr/bin/env python3
"""Prove that tables.py renders the published tables from the published data.

Usage: python3 -I check_tables.py <index.html> <data.json>
Run it on the page and data as published (before update_data.py), and again on the new pair after build_page.py.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tables as T

s, D = Path(sys.argv[1]).read_text(encoding="ascii"), json.load(open(sys.argv[2]))
bad = 0
for tid, fn in (("tft", T.tft_rows), ("vlt", T.vlt_rows)):
    _, old = T.replace_tbody(s, tid, "")
    o, n = old.split("\n"), fn(D).split("\n")
    diff = [(a, b) for a, b in zip(o, n) if a != b]
    print(tid, len(o), "rows on the page,", len(n), "from the data,", len(diff), "differ")
    bad += len(diff) + abs(len(o) - len(n))
    for a, b in diff[:5]:
        print("  page:", a[:200], "\n  data:", b[:200])
_, old = T.replace_tbody(s, "fam", "")
rows = old.split("\n")
for r in rows:
    c = re.findall(r"<td>(.*?)</td>", r)
    mt, cls = re.sub(r"<[^>]+>", "", c[1]), re.sub(r"<[^>]+>", "", c[3])
    if cls == "MistralLarge4ForConditionalGeneration" and "MistralLarge4ForCausalLM" in D["vl"]:
        continue                                        # written by hand in build_page.py
    for i, (a, b) in zip((3, 5, 6, 7, 8, 9), zip([c[2], c[4], c[5], c[6], c[7], c[8]], T.fam_cells(D, mt, cls))):
        if a != b:
            bad += 1
            print("fam", c[0], "column", i, "| page:", a, "| data:", b)
print("fam", len(rows), "rows")
# the tool reads data.json: every name in the tables must be in it and the other way round
names = set(re.findall(r"<tr><td><code>([^<]+)</code>", T.replace_tbody(s, "vlt", "")[1]))
assert names == set(D["vl"]), (len(names), len(D["vl"]))
print("OK" if not bad else "DIFFERENCES: %d" % bad)
sys.exit(1 if bad else 0)
