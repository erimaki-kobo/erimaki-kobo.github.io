#!/usr/bin/env python3
"""Ask a running llama-server how it renders the Qwen3 chat template for each way of
turning thinking off, via POST /apply-template (same request parsing as /v1/chat/completions).

Qwen3's template ends the prompt with an empty "<think>\\n\\n</think>\\n\\n" block when
enable_thinking is false; that block is what makes the real model skip thinking.

usage: python render_matrix.py <port> <label> >> results.jsonl
"""
import json, sys, urllib.request, urllib.error

port, label = sys.argv[1], sys.argv[2]
CASES = [
    ("none", {}),
    ("ctk enable_thinking false", {"chat_template_kwargs": {"enable_thinking": False}}),
    ("ctk enable_thinking \"false\" (string)", {"chat_template_kwargs": {"enable_thinking": "false"}}),
    ("ctk thinking false", {"chat_template_kwargs": {"thinking": False}}),
    ("reasoning_effort none", {"reasoning_effort": "none"}),
    ("think false", {"think": False}),
    ("enable_thinking false (top level)", {"enable_thinking": False}),
]
for name, extra in CASES:
    body = {"messages": [{"role": "user", "content": "hi"}]}
    body.update(extra)
    req = urllib.request.Request("http://localhost:%s/apply-template" % port, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    row = {"build": label, "case": name}
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            p = json.loads(r.read())["prompt"]
        row["status"] = 200
        row["thinking_off"] = p.rstrip().endswith("</think>")
        row["tail"] = p[-30:]
    except urllib.error.HTTPError as e:
        row["status"] = e.code
        row["error"] = e.read().decode("utf-8", "replace")[:200]
    print(json.dumps(row, ensure_ascii=False))
