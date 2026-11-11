#!/usr/bin/env python3
"""Float64 NumPy forward pass for a llama2.c checkpoint, written from the architecture alone
(RMSNorm, RoPE on interleaved pairs, causal attention, SwiGLU, tied output embedding).
It produces an lpcheck reference file whose numbers do not depend on any inference engine.

usage: python np_ref.py stories15M.bin tokenizer.model out_ref.json [max_tokens] [top_k] [float64|float32]
"""
import json
import struct
import sys

import numpy as np
import sentencepiece as spm

sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/lp")
from lpcheck import PROMPTS  # noqa: E402


class Model:
    def __init__(self, path, dtype):
        raw = open(path, "rb").read()
        self.dim, self.hidden, self.L, self.H, self.KV, vocab, self.seq = struct.unpack("7i", raw[:28])
        assert vocab > 0
        w = np.frombuffer(raw, dtype="<f4", offset=28).astype(dtype)
        self.pos, self.w, self.dtype = 0, w, dtype
        d, hid, L = self.dim, self.hidden, self.L
        self.emb = self.take(vocab, d)
        self.rms_att = self.take(L, d)
        self.wq, self.wk, self.wv, self.wo = (self.take(L, d, d) for _ in range(4))
        self.rms_ffn = self.take(L, d)
        self.w1 = self.take(L, hid, d)
        self.w2 = self.take(L, d, hid)
        self.w3 = self.take(L, hid, d)
        self.rms_final = self.take(d)

    def take(self, *shape):
        n = int(np.prod(shape))
        t = self.w[self.pos:self.pos + n].reshape(*shape)
        self.pos += n
        return t

    def norm(self, x, g):
        return x / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + self.dtype(1e-5)) * g

    def logits(self, ids):
        """-> logits for every position, shape [T, vocab]."""
        T, H, hd = len(ids), self.H, self.dim // self.H
        x = self.emb[np.array(ids)]
        freqs = 1.0 / (10000.0 ** (np.arange(0, hd, 2, dtype=np.float64) / hd))
        ang = np.outer(np.arange(T, dtype=np.float64), freqs)
        cos, sin = np.cos(ang).astype(self.dtype)[:, None, :], np.sin(ang).astype(self.dtype)[:, None, :]
        mask = np.triu(np.full((T, T), -np.inf), 1).astype(self.dtype)

        def rope(t):
            a, b = t[..., 0::2], t[..., 1::2]
            out = np.empty_like(t)
            out[..., 0::2] = a * cos - b * sin
            out[..., 1::2] = a * sin + b * cos
            return out

        for l in range(self.L):
            h = self.norm(x, self.rms_att[l])
            q = rope((h @ self.wq[l].T).reshape(T, H, hd))
            k = rope((h @ self.wk[l].T).reshape(T, H, hd))
            v = (h @ self.wv[l].T).reshape(T, H, hd)
            att = np.einsum("thd,shd->hts", q, k) / np.sqrt(self.dtype(hd)) + mask[None]
            att = att - att.max(axis=-1, keepdims=True)
            att = np.exp(att)
            att = att / att.sum(axis=-1, keepdims=True)
            x = x + np.einsum("hts,shd->thd", att, v).reshape(T, self.dim) @ self.wo[l].T
            h = self.norm(x, self.rms_ffn[l])
            a = h @ self.w1[l].T
            x = x + ((a / (1.0 + np.exp(-a))) * (h @ self.w3[l].T)) @ self.w2[l].T
        return self.norm(x, self.rms_final) @ self.emb.T


def log_softmax(z):
    z = z.astype(np.float64)
    z = z - z.max()
    return z - np.log(np.exp(z).sum())


def main():
    path, tok_model, out = sys.argv[1:4]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 32
    k = int(sys.argv[5]) if len(sys.argv) > 5 else 5
    dtype = np.float32 if len(sys.argv) > 6 and sys.argv[6] == "float32" else np.float64
    m = Model(path, dtype)
    sp = spm.SentencePieceProcessor(model_file=tok_model)
    traces = []
    for name, text in PROMPTS:
        ids = [1] + sp.encode(text)
        cont = []
        for _ in range(n):
            cont.append(int(np.argmax(m.logits(ids + cont)[-1])))
        lg = m.logits(ids + cont)
        top, lps = [], []
        for i in range(n):
            row = log_softmax(lg[len(ids) - 1 + i])
            idx = np.argsort(-row)[:k]
            top.append([[int(j), sp.id_to_piece(int(j)).replace("▁", " "), float(row[j])] for j in idx])
            lps.append(float(row[cont[i]]))
        traces.append({"name": name, "text": text, "messages": None, "prompt_ids": ids, "cont_ids": cont,
                       "lp": lps, "top": top, "self_lp": None})
        print(name, len(ids), repr(sp.decode(cont))[:90])
    json.dump({"tool": "lpcheck", "version": "1.0.0", "source": "numpy-%s forward pass (np_ref.py)" % dtype.__name__,
               "dtype": dtype.__name__, "device": "cpu", "model": "stories15M (llama2.c)", "k": k, "traces": traces,
               "libs": {"numpy": np.__version__}}, open(out, "w"))
    print("wrote", out)


if __name__ == "__main__":
    main()
