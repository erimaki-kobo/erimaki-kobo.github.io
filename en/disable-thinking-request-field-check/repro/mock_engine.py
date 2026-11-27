#!/usr/bin/env python3
"""A tiny replay server that answers /v1/chat/completions the way each engine's request
handling does (rules copied from the source at the versions named below), with a fake
model that always thinks unless the engine turned thinking off. Used to test
thinkcheck.py's verdicts, not to measure engines.

usage: python mock_engine.py <port> <mode>
modes: ollama_v1   Ollama v0.40.18 /v1: only reasoning_effort "none" turns thinking off;
                   top_k, min_p, repeat_penalty, think, chat_template_kwargs are dropped; reply in "reasoning"
       vllm_0_21   vLLM v0.18.0-v0.21.x with Qwen3: only chat_template_kwargs.enable_thinking=false works;
                   reasoning_effort "none" is accepted but ignored; reply in "reasoning"
       vllm_0_17   vLLM v0.17.1: reasoning_effort "none" is rejected (400)
"""
import json, random, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODE = sys.argv[2]
WORDS = "cat dog owl fox bee yak elk emu ant bat cow hen pig ram rat".split()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ctk = req.get("chat_template_kwargs") or {}
        eff = req.get("reasoning_effort")
        if MODE == "vllm_0_17" and eff is not None and eff not in ("low", "medium", "high"):
            return self.send(400, {"error": {"message": "1 validation error: reasoning_effort Input should be 'low', 'medium' or 'high'"}})
        if MODE == "ollama_v1":
            off = eff == "none"
            known = {"seed", "temperature", "frequency_penalty"}
        else:
            off = ctk.get("enable_thinking") is False
            known = {"seed", "temperature", "top_k", "min_p", "repetition_penalty", "frequency_penalty"}
        prompt = req["messages"][-1]["content"]
        temp = float(req.get("temperature", 1.0))
        seed = req.get("seed") if "seed" in known else None
        rng = random.Random(seed) if seed is not None else random.Random()
        greedy = temp == 0 or ("top_k" in known and req.get("top_k") == 1) or ("min_p" in known and req.get("min_p") == 1.0)
        n = 8
        words = [WORDS[(len(prompt) + i) % len(WORDS)] if greedy else rng.choice(WORDS) for i in range(n)]
        pen = ("repetition_penalty" in known and req.get("repetition_penalty")) or ("frequency_penalty" in known and req.get("frequency_penalty"))
        if pen:
            words = list(dict.fromkeys(words)) + ["!"]
        msg = {"role": "assistant", "content": " ".join(words)}
        if not off:
            msg["reasoning"] = "Let me think about it."
        self.send(200, {"choices": [{"index": 0, "message": msg, "finish_reason": "stop"}],
                        "usage": {"completion_tokens": n + (0 if off else 6)}})


ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
