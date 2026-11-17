#!/usr/bin/env python3
"""Tell readers of en/vllm-kv-concurrency-planner what vLLM v0.34.0 changed, until the calculator is ported.

Usage: python3 -I 2026-11-17_kv_v0.34.0.py <repository root>      (idempotent)
Read from vllm/config/cache.py at v0.33.0 and v0.34.0: DEFAULT_BLOCK_SIZE 16 -> 64 (PR #63231), the new
enable_extensible_kv_cache field and resolved_gpu_memory_utilization (1.0 with it, 0.92 without). The log lines
"Available KV cache memory" and "Maximum concurrency for %s tokens per request" exist in both tags.
Remove this script's notice when kvplan.py / kvplan.js follow v0.34.0.
"""
import re, sys
from pathlib import Path

p = Path(sys.argv[1]) / "en/vllm-kv-concurrency-planner/index.html"
s = p.read_text(encoding="ascii")
NOTE = ('<p class="note" id="v034"><strong>vLLM v0.34.0 (2026-11-16) sizes the KV cache differently, and this page still follows v0.33.0.</strong> '
        'Three defaults changed. A block is 64 tokens instead of 16 (PR #63231). On CUDA and ROCm the "extensible KV cache" is on unless '
        '<code>--kv-cache-memory-bytes</code> is set: the cache is sized from the memory that is actually free after CUDA graph capture and warmup, '
        'not from an estimate (it falls back to the estimate where the driver lacks virtual-memory support). With it, '
        '<code>gpu_memory_utilization</code>, when not given, is 1.0 instead of 0.92. The log lines (<code>Available KV cache memory</code>, '
        '<code>Maximum concurrency for L tokens per request</code>) are unchanged. For a v0.34.0 estimate, set "Block size, tokens" to 64 and '
        '<code>--gpu-memory-utilization</code> to 1.0 in the planner; it has not been compared with v0.34.0\'s code yet, so treat that result as approximate.</p>')
ROW = ('<tr><td>v0.34.0 (2026-11)</td><td>default block 16 &rarr; 64 tokens; the extensible KV cache is on by default on CUDA and ROCm and sizes the cache '
       'from the memory free after CUDA graph capture and warmup; default <code>gpu_memory_utilization</code> is 1.0 with it, 0.92 without. '
       'The planner on this page does not follow this release yet</td></tr>')
if 'id="v034"' not in s:
    m = re.search(r'<p class="meta">Published 2026-11-12.*?</p>', s, re.S)
    assert m and "Follows vLLM v0.33.0" in m.group(0)
    meta = m.group(0).replace("&middot; Follows vLLM v0.33.0", "&middot; Updated 2026-11-17: note on v0.34.0 &middot; Follows vLLM v0.33.0")
    assert meta != m.group(0)
    s = s[:m.start()] + meta + "\n" + NOTE + s[m.end():]
    last = "16,384 batched tokens</td></tr>\n</tbody>"
    assert s.count(last) == 1
    s = s.replace(last, "16,384 batched tokens</td></tr>\n" + ROW + "\n</tbody>")
    s, n = re.subn(r'("dateModified": ")\d{4}-\d\d-\d\d(")', r"\g<1>2026-11-17\2", s)
    assert n >= 1
    s.encode("ascii")
    p.write_text(s, encoding="ascii")
    print("notice and table row added")
else:
    print("already applied")
