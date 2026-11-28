"""Replay server: answers in the request/response format of Ollama, TEI or vLLM and applies the
pre/post-processing that engine's source code applies, on top of the reference model.

It is used only to test embedcheck.py's client code and diagnoses. The behaviours encoded here
were read from the source at these tags: Ollama v0.40.19 (server/routes.go EmbedHandler and
EmbeddingsHandler), TEI v1.10.0 (router/src/lib.rs, router/src/http/types.rs, core/src/infer.rs),
vLLM v0.34.0 (transformers_utils/config.py get_pooling_config, layers/pooler/activations.py).

usage: python mock_engine.py <port> <ollama|tei|vllm> <model dir> [--rerank]
"""
import json, math, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, ENGINE, MODEL = int(sys.argv[1]), sys.argv[2], sys.argv[3]
RERANK = "--rerank" in sys.argv

if RERANK:
    import torch
    from sentence_transformers import CrossEncoder
    ce = CrossEncoder(MODEL, device="cpu")
else:
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(MODEL, device="cpu")
    pool = getattr(st[1], "pooling_mode", "mean")
    max_pos = st[0].auto_model.config.max_position_embeddings


def l2(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(text, max_tokens, normalize):
    """No prompt prefix (none of the three adds sentence-transformers' default prompt on these endpoints)."""
    keep = st.max_seq_length
    st.max_seq_length = max_tokens
    tok = st.encode(text, prompt="", output_value="token_embeddings", convert_to_numpy=False).float()
    st.max_seq_length = keep
    v = {"cls": tok[0], "mean": tok.mean(0), "lasttoken": tok[-1]}[pool].tolist()
    return l2(v) if normalize else v


def logits(q, docs):
    return ce.predict([(q, d) for d in docs], activation_fn=torch.nn.Identity()).tolist()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        p = self.path
        if ENGINE == "ollama" and p == "/api/embed":
            # truncates to the GGUF context_length (minus BOS/EOS) by default, then always L2-normalizes
            return self.send(200, {"embeddings": [embed(t, max_pos, True) for t in body["input"]]})
        if ENGINE == "ollama" and p == "/api/embeddings":
            # legacy endpoint: no truncation step, no normalization
            return self.send(200, {"embedding": embed(body["prompt"], max_pos, False)})
        if ENGINE == "tei" and p == "/embed":
            # truncates at sentence-transformers max_seq_length (auto-truncate true), normalize defaults to true
            return self.send(200, [embed(t, st.max_seq_length, body.get("normalize", True)) for t in body["inputs"]])
        if ENGINE == "vllm" and p == "/v1/embeddings":
            # max_model_len = max_seq_length; longer inputs are refused unless truncate_prompt_tokens is set
            out = []
            for t in body["input"]:
                n = len(st.tokenizer(t)["input_ids"])
                if n > st.max_seq_length and not body.get("truncate_prompt_tokens"):
                    return self.send(400, {"error": {"message": f"This model's maximum context length is {st.max_seq_length} tokens. "
                                                                f"However, you requested {n} tokens in the input for embedding generation. "
                                                                "Please reduce the length of the input.", "code": 400}})
                out.append({"index": len(out), "embedding": embed(t, st.max_seq_length, True)})
            return self.send(200, {"data": out})
        if ENGINE == "tei" and p == "/rerank":
            s = logits(body["query"], body["texts"])
            if not body.get("raw_scores"):
                s = [1 / (1 + math.exp(-x)) for x in s]
            return self.send(200, [{"index": i, "score": x} for i, x in enumerate(s)])
        if ENGINE == "vllm" and p == "/v1/rerank":
            # 1-label classifier -> sigmoid unless use_activation is false
            s = logits(body["query"], body["documents"])
            if body.get("use_activation", True):
                s = [1 / (1 + math.exp(-x)) for x in s]
            return self.send(200, {"results": [{"index": i, "relevance_score": x} for i, x in enumerate(s)]})
        self.send(404, {"error": "no such endpoint in this mock: " + p})


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
