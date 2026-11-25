"""Unit checks for cachecheck.classify(); live cases are in results.jsonl."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cachecheck as c
cases = [
    # n1, n2, shared, cache_n, slot1, slot2, expected exit code, word in verdict
    (1647, 1859, 1647, 1647, [0], [0], 0, "OK"),
    (1647, 1822, 1647, 1662, [0], [0], 0, "OK"),            # reply tokens cached too
    (1647, 1853, 1647, 1643, [0], [0], 0, "PARTIAL"),       # checkpoint 4 tokens back
    (1647, 1853, 1647, 0, [0], [0], 4, "FULL RE-PROCESSING"),
    (1647, 1853, 1647, 0, [0], [1], 3, "DIFFERENT SLOT"),
    (1647, 1859, 45, 45, [0], [0], 1, "reused all 45"),
    (1647, 1822, 45, 0, [0], [0], 1, "WHOLE prompt"),
    (1647, 1853, 1404, 1131, [0], [0], 1, "rolled back"),
    (1647, 1853, 1647, 1000, [0], [0], 5, "PARTIAL"),
]
for n1, n2, sh, cn, s1, s2, code, word in cases:
    v, k = c.classify(n1, n2, sh, cn, s1, s2)
    assert k == code and word in v, (n1, n2, sh, cn, s1, s2, k, v)
print("classify: %d cases ok" % len(cases))
v, k = c.classify(1647, 1828, 895, 1616, [0], [0])
assert k == 1 and "--cache-reuse" in v
print("cache-reuse case ok")
