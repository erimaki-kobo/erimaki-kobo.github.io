#!/usr/bin/env python3
"""Toy OpenAI-compatible server for testing specdiff.py without a GPU.

A deterministic toy language model: next-token logits are a hash of the context.
At planted positions the top-2 logits are 0.001 nats apart (near-ties), so a
tiny numeric perturbation can flip them, as the batched verify pass does on
real engines.

    python mock_server.py PORT MODE [STATS]

MODE   base       ordinary decoding
       lossless   speculative, bit-identical to base
       neartie    speculative, logits perturbed by up to 0.004 nats (flips near-ties only)
       bug        speculative, occasionally emits the 3rd-ranked token (clear winner lost)
       brokenlp   identical tokens, but logprob 0.0 / empty top_logprobs after the 1st token
       nodraft    identical, and reports zero drafted tokens
       shift      greedy identical; at temperature > 0 the 2nd answer token is biased
       flaky      base whose greedy output changes between calls
STATS  vllm | sglang | llama | none   (how draft statistics are reported; default llama)
"""
import hashlib
import json
import math
import random
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VOCAB = ["the", " cat", " sat", " on", " mat", ",", ".", " and", " a", " dog", " ran", " far", " away",
         " home", " in", " rain", " sun", " light", " day", " night", " blue", " red", " tree", " road",
         " bird", " sang", " loud", " soft", " slow", " fast", " old", " new", " we", " they", " it",
         " is", " was", " will", " not", " very", "\n", " of", " to", " with", " by", " from", " up",
         " down", " out", " over"]
COLORS = ["red", "green", "yellow", "purple", "orange"]
FRUITS = ["apple", "pear", "banana", "grape", "tangerine"]

MODE = "base"
STATS = "llama"
LOCK = threading.Lock()
CALLS = [0]


def h(*parts):
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


def logits(ctx_key, pos, flaky_salt=0):
    rng = random.Random(h(ctx_key, pos, flaky_salt))
    lg = [rng.gauss(0, 2.0) for _ in VOCAB]
    if h("tie", ctx_key, pos) % 25 == 0:  # planted near-tie
        order = sorted(range(len(lg)), key=lambda i: -lg[i])
        lg[order[1]] = lg[order[0]] - 0.001
    return lg


def log_softmax(lg):
    m = max(lg)
    z = math.log(sum(math.exp(x - m) for x in lg)) + m
    return [x - z for x in lg]


def greedy(prompt, max_tokens, mode, salt):
    toks, lps, tops = [], [], []
    ctx = h(prompt)
    drafted = accepted = 0
    for pos in range(max_tokens):
        lg = logits(ctx, pos, salt)
        if mode == "neartie" and pos > 0:
            rng = random.Random(h("noise", ctx, pos))
            lg = [x + rng.uniform(-0.002, 0.002) for x in lg]
        lp = log_softmax(lg)
        order = sorted(range(len(lp)), key=lambda i: -lp[i])
        pick = order[0]
        if mode == "bug" and pos > 0 and h("bug", ctx, pos) % 97 == 0:
            pick = order[2]
        toks.append(VOCAB[pick])
        lps.append(lp[pick])
        tops.append([(VOCAB[i], lp[i]) for i in order[:5]])
        ctx = h(ctx, pick)
        if pos > 0:
            drafted += 1
            accepted += 1 if h("acc", ctx) % 3 else 0
    return toks, lps, tops, drafted, accepted


def sample(prompt, temperature, mode, seed):
    rng = random.Random(seed)
    # answer token 1 comes from prefill; token 2 goes through speculative verification
    w1 = [3, 2, 2, 1, 1]
    c = rng.choices(range(5), weights=w1)[0]
    w2 = [1.0] * 5
    w2[c] = 4.0
    if mode == "shift":
        w2[0] += 3.0
    f = rng.choices(range(5), weights=w2)[0]
    text = "Answer:\n%s %s" % (COLORS[c], FRUITS[f])
    return [text], 6, 4


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/models"):
            return self._send(200, {"object": "list", "data": [{"id": "toy-model"}]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        chat = self.path.endswith("/chat/completions")
        prompt = req["messages"][-1]["content"] if chat else req["prompt"]
        temp = float(req.get("temperature", 1.0))
        n = int(req.get("max_tokens", 16))
        with LOCK:
            CALLS[0] += 1
            call = CALLS[0]
        resp = {"id": "x", "object": "chat.completion" if chat else "text_completion", "model": "toy-model"}
        if temp > 0:
            seed = h(prompt, call, MODE)
            pieces, drafted, accepted = sample(prompt, temp, MODE, seed)
            text = pieces[0]
            choice = {"index": 0, "finish_reason": "stop"}
            if chat:
                choice["message"] = {"role": "assistant", "content": text}
            else:
                choice["text"] = text
            resp["choices"] = [choice]
        else:
            salt = call if MODE == "flaky" and h("fl", prompt) % 2 == 0 else 0
            toks, lps, tops, drafted, accepted = greedy(prompt, n, MODE, salt)
            if MODE == "brokenlp":
                lps = [lps[0]] + [0.0] * (len(lps) - 1)
                tops = [tops[0]] + [[] for _ in tops[1:]]
            k = int(req.get("top_logprobs") or req.get("logprobs") or 0) if req.get("logprobs") else 0
            choice = {"index": 0, "finish_reason": "length"}
            if chat:
                choice["message"] = {"role": "assistant", "content": "".join(toks)}
                if req.get("logprobs"):
                    choice["logprobs"] = {"content": [
                        {"token": t, "logprob": l, "top_logprobs": [{"token": a, "logprob": b} for a, b in tp[:k]]}
                        for t, l, tp in zip(toks, lps, tops)]}
            else:
                choice["text"] = "".join(toks)
                if req.get("logprobs"):
                    choice["logprobs"] = {"tokens": toks, "token_logprobs": lps,
                                          "top_logprobs": [dict(tp[:k]) for tp in tops]}
            resp["choices"] = [choice]
        spec_mode = MODE not in ("base", "flaky")
        if MODE == "nodraft":
            drafted = accepted = 0
        if spec_mode and STATS == "vllm":
            resp["metrics"] = {"speculative_decoding": {"num_draft_tokens": drafted, "num_accepted_draft_tokens": accepted}}
        elif spec_mode and STATS == "sglang" and req.get("return_spec_tokens_details"):
            resp["sglext"] = {"spec_tokens_details": {"spec_num_proposed_drafts": drafted,
                                                      "spec_num_correct_drafts": accepted}}
        elif STATS == "llama":
            t = {"predicted_n": n}
            if spec_mode and drafted:
                t.update({"draft_n": drafted, "draft_n_accepted": accepted})
            resp["timings"] = t
        self._send(200, resp)


if __name__ == "__main__":
    port = int(sys.argv[1])
    MODE = sys.argv[2]
    STATS = sys.argv[3] if len(sys.argv) > 3 else "llama"
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
