#!/usr/bin/env python3
"""Write three tiny random-weight GGUF files (F32) for CPU tests of llama-server's
prompt cache: a full-attention Llama, a Gemma 2 with a sliding window (SWA) of 64,
and a Mamba (recurrent). The text they produce is nonsense; the server's caching
code paths are the real ones.

usage: PYTHONPATH=<llama.cpp>/gguf-py python make_toy_models.py <outdir>
"""
import os, sys
import numpy as np
import gguf

WORDS = ("the of and to in is was for on that with as by at from it his an were are which this be or had not "
         "but first one their its new after who they has her two she been other when there all during into "
         "school time may years more most only over city some world would where later up such used many can "
         "state about national out known university united then made number while american part three "
         "system user assistant tool call result file read write line error code").split()
CHATML = ("{% for m in messages %}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}<|im_end|>\n{% endfor %}"
          "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}")

def vocab():
    toks, scores, types = [b"<unk>", b"<s>", b"</s>"], [0.0, 0.0, 0.0], [
        gguf.TokenType.UNKNOWN, gguf.TokenType.CONTROL, gguf.TokenType.CONTROL]
    for b in range(256):
        toks.append(("<0x%02X>" % b).encode()); scores.append(0.0); types.append(gguf.TokenType.BYTE)
    seen = set()
    for i, w in enumerate(WORDS):
        for piece in ("▁" + w, w):
            if piece in seen: continue
            seen.add(piece); toks.append(piece.encode()); scores.append(-float(i)); types.append(gguf.TokenType.NORMAL)
    return toks, scores, types

def common(g, name, toks, scores, types, ctx=8192):
    g.add_name(name); g.add_context_length(ctx); g.add_vocab_size(len(toks))
    g.add_file_type(gguf.LlamaFileType.ALL_F32)
    g.add_tokenizer_model("llama"); g.add_tokenizer_pre("default")
    g.add_token_list(toks); g.add_token_scores(scores); g.add_token_types(types)
    g.add_bos_token_id(1); g.add_eos_token_id(2); g.add_unk_token_id(0)
    g.add_add_bos_token(True); g.add_add_eos_token(False)
    g.add_chat_template(CHATML)

def finish(g):
    g.write_header_to_file(); g.write_kv_data_to_file(); g.write_tensors_to_file(); g.close()

def main(outdir):
    rng = np.random.default_rng(0)
    def w(*shape, scale=None):
        s = scale if scale is not None else 1.0 / np.sqrt(shape[-1])
        return (rng.standard_normal(shape) * s).astype(np.float32)
    toks, scores, types = vocab(); V = len(toks)
    dim, hidden, nl, nh, nkv = 128, 256, 4, 4, 2; hd = dim // nh

    # 1. llama (full attention)
    g = gguf.GGUFWriter(os.path.join(outdir, "toy-llama.gguf"), "llama")
    common(g, "toy-llama", toks, scores, types)
    g.add_embedding_length(dim); g.add_block_count(nl); g.add_feed_forward_length(hidden)
    g.add_head_count(nh); g.add_head_count_kv(nkv); g.add_layer_norm_rms_eps(1e-5)
    g.add_rope_dimension_count(hd); g.add_rope_freq_base(10000.0)
    g.add_tensor("token_embd.weight", w(V, dim, scale=1.0))
    for i in range(nl):
        p = "blk.%d." % i
        g.add_tensor(p+"attn_norm.weight", np.ones(dim, np.float32))
        g.add_tensor(p+"attn_q.weight", w(dim, dim)); g.add_tensor(p+"attn_k.weight", w(nkv*hd, dim))
        g.add_tensor(p+"attn_v.weight", w(nkv*hd, dim)); g.add_tensor(p+"attn_output.weight", w(dim, dim))
        g.add_tensor(p+"ffn_norm.weight", np.ones(dim, np.float32))
        g.add_tensor(p+"ffn_gate.weight", w(hidden, dim)); g.add_tensor(p+"ffn_up.weight", w(hidden, dim))
        g.add_tensor(p+"ffn_down.weight", w(dim, hidden))
    g.add_tensor("output_norm.weight", np.ones(dim, np.float32)); g.add_tensor("output.weight", w(V, dim, scale=0.25))
    finish(g)

    # 2. gemma2 with sliding window 64 (every other layer is SWA)
    g = gguf.GGUFWriter(os.path.join(outdir, "toy-gemma2-swa64.gguf"), "gemma2")
    common(g, "toy-gemma2-swa64", toks, scores, types)
    g.add_embedding_length(dim); g.add_block_count(nl); g.add_feed_forward_length(hidden)
    g.add_head_count(nh); g.add_head_count_kv(nkv); g.add_layer_norm_rms_eps(1e-6)
    g.add_key_length(hd); g.add_value_length(hd); g.add_sliding_window(64)
    g.add_tensor("token_embd.weight", w(V, dim, scale=0.25))
    for i in range(nl):
        p = "blk.%d." % i
        g.add_tensor(p+"attn_norm.weight", np.zeros(dim, np.float32))
        g.add_tensor(p+"attn_q.weight", w(dim, dim)); g.add_tensor(p+"attn_k.weight", w(nkv*hd, dim))
        g.add_tensor(p+"attn_v.weight", w(nkv*hd, dim)); g.add_tensor(p+"attn_output.weight", w(dim, dim))
        g.add_tensor(p+"post_attention_norm.weight", np.zeros(dim, np.float32))
        g.add_tensor(p+"ffn_norm.weight", np.zeros(dim, np.float32))
        g.add_tensor(p+"ffn_gate.weight", w(hidden, dim)); g.add_tensor(p+"ffn_up.weight", w(hidden, dim))
        g.add_tensor(p+"ffn_down.weight", w(dim, hidden))
        g.add_tensor(p+"post_ffw_norm.weight", np.zeros(dim, np.float32))
    g.add_tensor("output_norm.weight", np.zeros(dim, np.float32))
    finish(g)

    # 3. mamba (recurrent)
    d_inner, d_state, d_conv, dt_rank = 2 * dim, 16, 4, 8
    g = gguf.GGUFWriter(os.path.join(outdir, "toy-mamba.gguf"), "mamba")
    common(g, "toy-mamba", toks, scores, types)
    g.add_embedding_length(dim); g.add_block_count(nl); g.add_feed_forward_length(0); g.add_head_count(0)
    g.add_layer_norm_rms_eps(1e-5)
    g.add_ssm_conv_kernel(d_conv); g.add_ssm_inner_size(d_inner); g.add_ssm_state_size(d_state); g.add_ssm_time_step_rank(dt_rank)
    g.add_tensor("token_embd.weight", w(V, dim, scale=1.0))
    for i in range(nl):
        p = "blk.%d." % i
        g.add_tensor(p+"attn_norm.weight", np.ones(dim, np.float32))
        g.add_tensor(p+"ssm_in.weight", w(2*d_inner, dim))
        g.add_tensor(p+"ssm_conv1d.weight", w(d_inner, d_conv)); g.add_tensor(p+"ssm_conv1d.bias", np.zeros(d_inner, np.float32))
        g.add_tensor(p+"ssm_x.weight", w(dt_rank + 2*d_state, d_inner))
        g.add_tensor(p+"ssm_dt.weight", w(d_inner, dt_rank)); g.add_tensor(p+"ssm_dt.bias", np.full(d_inner, -2.0, np.float32))
        g.add_tensor(p+"ssm_a", -np.exp(w(d_inner, d_state, scale=0.5)))
        g.add_tensor(p+"ssm_d", np.ones(d_inner, np.float32))
        g.add_tensor(p+"ssm_out.weight", w(dim, d_inner))
    g.add_tensor("output_norm.weight", np.ones(dim, np.float32)); g.add_tensor("output.weight", w(V, dim, scale=0.25))
    finish(g)
    print("wrote 3 models to", outdir, "vocab", V)

if __name__ == "__main__":
    main(sys.argv[1])
