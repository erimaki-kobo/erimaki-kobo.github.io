#!/usr/bin/env python3
"""Mock OpenAI-compatible completion server with a deterministic toy language model,
for testing lpcheck. Two servers started with the same toy model return identical
logprobs unless a MODE perturbs one of them.

usage: FLAVOR=vllm MODE=exact python3 mock_server.py 9200

FLAVOR=vllm      /v1/completions legacy logprobs (tokens/token_logprobs/top_logprobs),
                 return_tokens_as_token_ids, prompt_logprobs, /tokenize {"prompt"}
FLAVOR=llamacpp  /v1/completions with logprobs.content[...] carrying token ids,
                 /tokenize {"content"}; no prompt_logprobs
FLAVOR=plain     legacy logprobs with token text only, no /tokenize, no extras

MODE=exact       same numbers as the toy model
MODE=noise       logits perturbed by about 1e-3 (half-precision-like numeric noise)
MODE=quant       logits perturbed by about 0.4 (different weights)
MODE=temp        returned logprobs are computed from logits / request temperature
MODE=reppen      server-side default repetition penalty 1.3 shapes token choice,
                 returned logprobs stay raw
MODE=procpen     like reppen, and returned logprobs include the penalty
MODE=logits      returns raw logits in place of logprobs
MODE=bos         text prompts get two BOS tokens
MODE=shift       prompt_logprobs are attached one position late
MODE=decode      decode steps after the first carry 2e-3 noise that prefill does not
MODE=topp        returned logprobs are renormalized over the request top_p nucleus
"""
import json
import math
import os
import random
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FLAVOR = os.environ.get("FLAVOR", "vllm")
MODE = os.environ.get("MODE", "exact")
V = 300
BOS = 256


def tokenize(text, special=True):
    ids = list(text.encode("utf-8"))
    if special:
        ids = [BOS] + ids
        if MODE == "bos":
            ids = [BOS] + ids
    return ids


def piece(i):
    if i < 256:
        return bytes([i]).decode("latin-1")
    return "<s>" if i == BOS else "<x%d>" % i


def base_logits(ctx):
    rng = random.Random(hash(tuple(ctx[-4:])) & 0xFFFFFFFF)
    lg = [rng.gauss(0.0, 2.2) for _ in range(V)]
    # a favourite continuation so greedy text has structure, with occasional near-ties
    fav = (sum(ctx[-3:]) * 31 + 7) % 256
    lg[fav] += 6.0
    if (sum(ctx[-2:]) % 5) == 0:
        lg[(fav + 13) % 256] = lg[fav] - 0.004
    # repeating the previous-but-one token is attractive (gives repetition penalties something to bite)
    if len(ctx) >= 2:
        lg[ctx[-2]] += 7.0
    return lg


def perturb(lg, ctx, scale, salt):
    rng = random.Random((hash(tuple(ctx[-6:])) ^ salt) & 0xFFFFFFFF)
    return [x + rng.gauss(0.0, scale) for x in lg]


def log_softmax(lg):
    m = max(lg)
    z = m + math.log(sum(math.exp(x - m) for x in lg))
    return [x - z for x in lg]


def apply_reppen(lg, ctx, pen):
    out = list(lg)
    for t in set(ctx):
        out[t] = out[t] / pen if out[t] > 0 else out[t] * pen
    return out


def step(ctx, req, decode_step):
    """-> (chosen id, returned values for every vocab id)."""
    lg = base_logits(ctx)
    if MODE == "noise":
        lg = perturb(lg, ctx, 1e-3, 0x51)
    elif MODE == "quant":
        lg = perturb(lg, ctx, 0.4, 0x77)
    elif MODE == "decode" and decode_step > 0:
        lg = perturb(lg, ctx, 2e-3, 0x99)
    temp = req.get("temperature")
    temp = 1.0 if temp is None else float(temp)
    pen = req.get("repetition_penalty") or req.get("repeat_penalty") or 1.0
    if MODE in ("reppen", "procpen") and pen == 1.0:
        pen = 1.3
    sample_lg = apply_reppen(lg, ctx, pen) if pen != 1.0 else lg
    ret = log_softmax(lg)
    if MODE == "procpen":
        ret = log_softmax(sample_lg)
    if MODE == "temp" and temp > 0:
        ret = log_softmax([x / temp for x in lg])
    if MODE == "logits":
        ret = list(lg)
    top_p = req.get("top_p")
    if MODE == "topp" and top_p is not None and float(top_p) < 1.0 and temp > 0:
        order = sorted(range(V), key=lambda i: -ret[i])
        keep, mass = [], 0.0
        for i in order:
            keep.append(i)
            mass += math.exp(ret[i])
            if mass >= float(top_p):
                break
        z = math.log(sum(math.exp(ret[i]) for i in keep))
        ks = set(keep)
        ret = [ret[i] - z if i in ks else float("-inf") for i in range(V)]
    if temp <= 0:
        chosen = max(range(V), key=lambda i: sample_lg[i])
    else:
        probs = log_softmax([x / temp for x in sample_lg])
        r, acc, chosen = random.random(), 0.0, V - 1
        for i in range(V):
            acc += math.exp(probs[i])
            if acc >= r:
                chosen = i
                break
    return chosen, ret


def topk(ret, k, chosen=None):
    order = sorted(range(V), key=lambda i: -ret[i])[:k]
    if chosen is not None and chosen not in order:
        order.append(chosen)
    return order


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path.endswith("/models"):
            owner = {"vllm": "vllm", "llamacpp": "llamacpp"}.get(FLAVOR, "someone")
            return self.send(200, {"object": "list", "data": [{"id": "toy-lm", "object": "model", "owned_by": owner}]})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        path = self.path.rstrip("/")
        if path.endswith("/tokenize"):
            if FLAVOR == "vllm" and "prompt" in req:
                ids = tokenize(req["prompt"], req.get("add_special_tokens", True))
                return self.send(200, {"count": len(ids), "max_model_len": 4096, "tokens": ids})
            if FLAVOR == "llamacpp" and "content" in req:
                return self.send(200, {"tokens": tokenize(req["content"], req.get("add_special", False))})
            return self.send(404, {"error": "not found"})
        if not path.endswith("/completions") or path.endswith("/chat/completions"):
            return self.send(404, {"error": "not found"})
        if FLAVOR == "plain" and any(k in req for k in ("prompt_logprobs", "return_tokens_as_token_ids", "n_probs")):
            return self.send(400, {"error": "unknown parameter"})
        prompt = req.get("prompt")
        if isinstance(prompt, str):
            ctx = tokenize(prompt, True)
        elif isinstance(prompt, list) and all(isinstance(x, int) for x in prompt):
            ctx = list(prompt)
        else:
            return self.send(400, {"error": "unsupported prompt type"})
        if any(t < 0 or t >= V for t in ctx):
            return self.send(400, {"error": "token id out of range"})
        n = int(req.get("max_tokens", 16))
        k = req.get("logprobs")
        if FLAVOR == "llamacpp" and req.get("n_probs"):
            k = req["n_probs"]
        as_ids = bool(req.get("return_tokens_as_token_ids")) and FLAVOR == "vllm"
        name = (lambda i: "token_id:%d" % i) if as_ids else piece
        prompt_ctx = list(ctx)
        steps, text = [], ""
        for s in range(n):
            chosen, ret = step(ctx, req, s)
            steps.append((chosen, ret))
            ctx.append(chosen)
            text += piece(chosen)
        choice = {"index": 0, "text": text, "finish_reason": "length"}
        if k:
            if FLAVOR == "llamacpp":
                content = []
                for chosen, ret in steps:
                    content.append({"id": chosen, "token": piece(chosen), "logprob": max(ret[chosen], -9999.0),
                                    "bytes": list(piece(chosen).encode("utf-8")),
                                    "top_logprobs": [{"id": i, "token": piece(i), "logprob": max(ret[i], -9999.0),
                                                      "bytes": list(piece(i).encode("utf-8"))} for i in topk(ret, k)]})
                choice["logprobs"] = {"content": content}
            else:
                choice["logprobs"] = {
                    "tokens": [name(c) for c, _ in steps],
                    "token_logprobs": [max(r[c], -9999.0) for c, r in steps],
                    "top_logprobs": [{name(i): max(r[i], -9999.0) for i in topk(r, k, c)} for c, r in steps],
                    "text_offset": [0] * len(steps),
                }
        pk = req.get("prompt_logprobs")
        if pk and FLAVOR == "vllm":
            out = [None]
            for i in range(1, len(prompt_ctx)):
                _, ret = step(prompt_ctx[:i], {"temperature": 0}, 0)
                actual = prompt_ctx[i]
                d = {}
                order = sorted(range(V), key=lambda j: -ret[j])
                for j in topk(ret, pk, actual):
                    d[str(j)] = {"logprob": max(ret[j], -9999.0), "rank": order.index(j) + 1, "decoded_token": piece(j)}
                out.append(d)
            if MODE == "shift":
                out = [None] + out[:-1]
            choice["prompt_logprobs"] = out
        self.send(200, {"id": "cmpl-mock", "object": "text_completion", "model": "toy-lm", "choices": [choice],
                        "usage": {"prompt_tokens": len(prompt_ctx), "completion_tokens": n,
                                  "total_tokens": len(prompt_ctx) + n}})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
