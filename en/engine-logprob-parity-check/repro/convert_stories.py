#!/usr/bin/env python3
"""Convert a llama2.c checkpoint (stories15M.bin) into a Hugging Face LlamaForCausalLM
directory so the same weights can be loaded by transformers and converted to GGUF.

usage: python convert_stories.py stories15M.bin tokenizer.model out_dir
"""
import json
import shutil
import struct
import sys

import numpy as np
import torch
from transformers import LlamaConfig, LlamaForCausalLM


def main(src, tok_model, out):
    raw = open(src, "rb").read()
    dim, hidden, n_layers, n_heads, n_kv, vocab, seq = struct.unpack("7i", raw[:28])
    shared = vocab > 0
    vocab = abs(vocab)
    w = np.frombuffer(raw, dtype="<f4", offset=28)
    pos = 0

    def take(*shape):
        nonlocal pos
        n = int(np.prod(shape))
        t = torch.from_numpy(w[pos:pos + n].copy()).reshape(*shape)
        pos += n
        return t

    emb = take(vocab, dim)
    rms_att = take(n_layers, dim)
    wq = take(n_layers, dim, dim)
    wk = take(n_layers, dim, dim)
    wv = take(n_layers, dim, dim)
    wo = take(n_layers, dim, dim)
    rms_ffn = take(n_layers, dim)
    w1 = take(n_layers, hidden, dim)
    w2 = take(n_layers, dim, hidden)
    w3 = take(n_layers, hidden, dim)
    rms_final = take(dim)
    head = dim // n_heads
    take(seq, head // 2)  # freq_cis_real (recomputed by the model)
    take(seq, head // 2)  # freq_cis_imag
    wcls = emb if shared else take(vocab, dim)
    assert pos == w.size, (pos, w.size)

    cfg = LlamaConfig(
        vocab_size=vocab, hidden_size=dim, intermediate_size=hidden, num_hidden_layers=n_layers,
        num_attention_heads=n_heads, num_key_value_heads=n_kv, max_position_embeddings=seq,
        rms_norm_eps=1e-5, rope_theta=10000.0, bos_token_id=1, eos_token_id=2, pad_token_id=0,
        tie_word_embeddings=shared, attention_bias=False, hidden_act="silu",
    )
    model = LlamaForCausalLM(cfg)

    def permute(x):
        # llama2.c (like Meta's Llama) rotates interleaved pairs; HF rotates half/half.
        return x.view(n_heads, head // 2, 2, dim).transpose(1, 2).reshape(dim, dim)

    sd = {"model.embed_tokens.weight": emb, "model.norm.weight": rms_final, "lm_head.weight": wcls}
    for i in range(n_layers):
        p = "model.layers.%d." % i
        sd[p + "input_layernorm.weight"] = rms_att[i]
        sd[p + "self_attn.q_proj.weight"] = permute(wq[i])
        sd[p + "self_attn.k_proj.weight"] = permute(wk[i])
        sd[p + "self_attn.v_proj.weight"] = wv[i]
        sd[p + "self_attn.o_proj.weight"] = wo[i]
        sd[p + "post_attention_layernorm.weight"] = rms_ffn[i]
        sd[p + "mlp.gate_proj.weight"] = w1[i]
        sd[p + "mlp.down_proj.weight"] = w2[i]
        sd[p + "mlp.up_proj.weight"] = w3[i]
    missing, unexpected = model.load_state_dict(sd, strict=False)
    assert not unexpected, unexpected
    assert all("lm_head" in m for m in missing), missing
    model = model.float().eval()
    model.save_pretrained(out, safe_serialization=True)
    shutil.copy(tok_model, out + "/tokenizer.model")
    json.dump({"tokenizer_class": "LlamaTokenizer", "bos_token": "<s>", "eos_token": "</s>",
               "unk_token": "<unk>", "add_bos_token": True, "add_eos_token": False,
               "legacy": True, "clean_up_tokenization_spaces": False},
              open(out + "/tokenizer_config.json", "w"), indent=1)
    print("saved", out, "params", sum(p.numel() for p in model.parameters()))


if __name__ == "__main__":
    main(*sys.argv[1:4])
