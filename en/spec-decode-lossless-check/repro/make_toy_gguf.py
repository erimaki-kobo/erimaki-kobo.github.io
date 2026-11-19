#!/usr/bin/env python3
"""Write a small Llama-architecture GGUF with random weights (F32) for CPU tests
of llama-server's speculative decoding. The text it produces is nonsense; what
matters is that the target runs through the real llama.cpp kernels, once as
one-token decode and once as a multi-token verify batch.

usage: PYTHONPATH=<llama.cpp>/gguf-py python make_toy_gguf.py out.gguf [seed]
"""
import sys

import numpy as np

import gguf

WORDS = ("the of and to in is was for on that with as by at from it his an were are which this be or had not "
         "but first one their its new after who they has her two she been other when there all during into "
         "school time may years more most only over city some world would where later up such used many can "
         "state about national out known university united then made number while american part three "
         "between people under following year system well north both main team south because high series "
         "film around second including also early before until since however these each name each through "
         "same small light water river house music game road line power light day night red blue green tree").split()


def main(out, seed=0):
    rng = np.random.default_rng(seed)
    dim, hidden, n_layers, n_heads, n_kv, ctx = 256, 688, 4, 8, 4, 4096
    tokens, scores, types = [b"<unk>", b"<s>", b"</s>"], [0.0, 0.0, 0.0], [
        gguf.TokenType.UNKNOWN, gguf.TokenType.CONTROL, gguf.TokenType.CONTROL]
    for b in range(256):
        tokens.append(("<0x%02X>" % b).encode())
        scores.append(0.0)
        types.append(gguf.TokenType.BYTE)
    seen = set()
    for i, w in enumerate(WORDS):
        for piece in ("▁" + w, w):
            if piece in seen:
                continue
            seen.add(piece)
            tokens.append(piece.encode())
            scores.append(-float(i) - (0.5 if not piece.startswith("▁") else 0.0))
            types.append(gguf.TokenType.NORMAL)
    for ch in ".,:;!?▁":
        tokens.append(ch.encode())
        scores.append(-1000.0)
        types.append(gguf.TokenType.NORMAL)
    vocab = len(tokens)

    def w(*shape, scale=None):
        s = scale if scale is not None else 1.0 / np.sqrt(shape[-1])
        return (rng.standard_normal(shape) * s).astype(np.float32)

    g = gguf.GGUFWriter(out, "llama")
    g.add_name("toy-random-llama")
    g.add_context_length(ctx)
    g.add_embedding_length(dim)
    g.add_block_count(n_layers)
    g.add_feed_forward_length(hidden)
    g.add_head_count(n_heads)
    g.add_head_count_kv(n_kv)
    g.add_layer_norm_rms_eps(1e-5)
    g.add_rope_dimension_count(dim // n_heads)
    g.add_rope_freq_base(10000.0)
    g.add_vocab_size(vocab)
    g.add_file_type(gguf.LlamaFileType.ALL_F32)
    g.add_tokenizer_model("llama")
    g.add_tokenizer_pre("default")
    g.add_token_list(tokens)
    g.add_token_scores(scores)
    g.add_token_types(types)
    g.add_bos_token_id(1)
    g.add_eos_token_id(2)
    g.add_unk_token_id(0)
    g.add_add_bos_token(True)
    g.add_add_eos_token(False)

    hd = dim // n_heads
    g.add_tensor("token_embd.weight", w(vocab, dim, scale=1.0))
    for i in range(n_layers):
        p = "blk.%d." % i
        g.add_tensor(p + "attn_norm.weight", np.ones(dim, np.float32))
        g.add_tensor(p + "attn_q.weight", w(dim, dim))
        g.add_tensor(p + "attn_k.weight", w(n_kv * hd, dim))
        g.add_tensor(p + "attn_v.weight", w(n_kv * hd, dim))
        g.add_tensor(p + "attn_output.weight", w(dim, dim))
        g.add_tensor(p + "ffn_norm.weight", np.ones(dim, np.float32))
        g.add_tensor(p + "ffn_gate.weight", w(hidden, dim))
        g.add_tensor(p + "ffn_up.weight", w(hidden, dim))
        g.add_tensor(p + "ffn_down.weight", w(dim, hidden))
    g.add_tensor("output_norm.weight", np.ones(dim, np.float32))
    # scale 0.25: top-1 probabilities spread between ~0.05 and ~0.9, so near-ties occur naturally
    g.add_tensor("output.weight", w(vocab, dim, scale=0.25))
    g.write_header_to_file()
    g.write_kv_data_to_file()
    g.write_tensors_to_file()
    g.close()
    print("wrote %s: vocab %d" % (out, vocab))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
