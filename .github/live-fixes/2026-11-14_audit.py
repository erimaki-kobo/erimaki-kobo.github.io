"""Corrections from the 2026-11-14 audit for vllm-kv-concurrency-planner, whose build scripts are not in this repository.
(The model-arch-min-version correction now lives in the page itself: .github/model-arch/build_page.py uses the published
page as its template.) Run from the repository root after rebuilding the page:
    python3 .github/live-fixes/2026-11-14_audit.py
Idempotent: a replacement that is already applied is skipped; one whose old text is missing stops with an error."""
import sys
FIXES = {
 "en/vllm-kv-concurrency-planner/index.html": [
  # K1: the estimated maximum model length is in the error from v0.8.4 (kv_cache_utils.py), not v0.9.1
  ('<tr><td>v0.9.1 (2025-06)</td><td><code>Available KV cache memory</code> line; startup stops when less than the budget is free; the "does not fit" error prints an estimated maximum model length</td></tr>',
   '<tr><td>v0.8.4 (2025-04)</td><td>the "does not fit" error prints an estimated maximum model length</td></tr>\n<tr><td>v0.9.1 (2025-06)</td><td><code>Available KV cache memory</code> line; startup stops when less than the budget is free</td></tr>'),
  # K2: VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS defaults to 1 from v0.20.0 (envs.py), not v0.21.0
  ('<tr><td>v0.20.0 (2026-04)</td><td>default <code>gpu_memory_utilization</code> 0.9 &rarr; 0.92</td></tr>',
   '<tr><td>v0.20.0 (2026-04)</td><td>default <code>gpu_memory_utilization</code> 0.9 &rarr; 0.92; the estimated CUDA graph memory is subtracted from the KV memory by default (<code>VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=0</code> turns it off; the variable exists from v0.18.0, off by default until here)</td></tr>'),
  ('<tr><td>v0.21.0 (2026-05)</td><td>the estimated CUDA graph memory is subtracted from the KV memory by default (<code>VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=0</code> turns it off)</td></tr>\n', ''),
  # the release date of v0.33.0 as on the other pages (tag date)
  ('Follows vLLM v0.33.0 (2026-10-31)', 'Follows vLLM v0.33.0 (2026-11-01)'),
  ('<p class="meta">Published 2026-11-12 &middot; Follows',
   '<p class="meta">Published 2026-11-12 &middot; Corrected 2026-11-14: two rows of the version table (v0.8.4, v0.20.0) &middot; Follows'),
 ],
}
MOD = "2026-11-14"
MARKERS = {'<p class="meta">Published 2026-11-12 &middot; Follows': ["Corrected 2026-11-14: two rows of the version table"]}
import re
for path, pairs in FIXES.items():
    s = open(path, encoding="utf-8").read(); n = 0
    for old, new in pairs:
        if new and new in s and old not in s: continue
        if not new and old not in s: continue
        if old not in s and any(m in s for m in MARKERS.get(old, [])): continue    # applied, and the line was extended later
        assert s.count(old) == 1, (path, s.count(old), old[:70])
        s = s.replace(old, new); n += 1
    s2 = re.sub(r'("dateModified": ")(\d{4}-\d\d-\d\d)(")', lambda m: m.group(1) + max(MOD, m.group(2)) + m.group(3), s)   # never move the date back
    open(path, "w", encoding="utf-8").write(s2)
    print(path, "applied", n, "dateModified", re.findall(r'"dateModified": "([0-9-]+)', s2)[:1])
