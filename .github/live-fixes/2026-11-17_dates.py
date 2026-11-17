#!/usr/bin/env python3
"""Fix the two vLLM release dates that were taken from git tags sitting on later commits.

v0.10.2: tag 2025-10-07, uploaded to PyPI 2025-09-13.  v0.11.0: tag 2025-10-10, uploaded 2025-10-04.
(.github/common/pypi_dates.json; every other vLLM tag is within 4 days of its upload.)

Usage: python3 -I 2026-11-17_dates.py <repository root>
Idempotent: a page that is already fixed is left alone. Run it again after rebuilding
en/vllm-kv-concurrency-planner from scripts that still use tag dates.
(en/model-arch-min-version takes its dates from pypi_dates.json since .github/model-arch/ exists.)
"""
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
P = json.loads((root / ".github/common/pypi_dates.json").read_text())["vllm"]
assert P["0.10.2"] == "2025-09-13" and P["0.11.0"] == "2025-10-04"

FIX = {
    "en/vllm-kv-concurrency-planner/index.html": [
        ("<td>v0.10.2 (2025-10)</td>", "<td>v0.10.2 (2025-09)</td>", 1),
    ],
}
for rel, reps in FIX.items():
    p = root / rel
    s = p.read_text(encoding="ascii")
    n = 0
    for old, new, count in reps:
        c = s.count(old)
        if c == 0:
            assert new in s, (rel, old)
            continue
        assert count is None or c == count, (rel, old, c)
        s = s.replace(old, new)
        n += c
    p.write_text(s, encoding="ascii")
    print(rel, "replacements:", n)
