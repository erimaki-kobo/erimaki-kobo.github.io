#!/usr/bin/env python3
"""Write a tiny random-weight Qwen3 GGUF (F32) that carries the real Qwen2 BPE vocab
(from llama.cpp's models/ggml-vocab-qwen2.gguf) and the real Qwen3 chat template
(models/templates/Qwen-Qwen3-0.6B.jinja). Its text is nonsense; the server's request
handling, template rendering and sampling code paths are the real ones.

usage: PYTHONPATH=<llama.cpp>/gguf-py python make_toy_qwen3.py <llama.cpp dir> <out.gguf>
"""
import sys, os
import numpy as np
import gguf

src, out = sys.argv[1], sys.argv[2]
r = gguf.GGUFReader(os.path.join(src, "models/ggml-vocab-qwen2.gguf"))
def field(name):
    f = r.fields[name]
    return f
def sval(name):
    f = r.fields[name]; return bytes(f.parts[f.data[0]]).decode()
def ival(name):
    f = r.fields[name]; return int(f.parts[f.data[0]][0])
toks = [bytes(r.fields["tokenizer.ggml.tokens"].parts[i]) for i in r.fields["tokenizer.ggml.tokens"].data]
types = [int(r.fields["tokenizer.ggml.token_type"].parts[i][0]) for i in r.fields["tokenizer.ggml.token_type"].data]
merges = [bytes(r.fields["tokenizer.ggml.merges"].parts[i]).decode() for i in r.fields["tokenizer.ggml.merges"].data]
# Qwen3 adds these four to the Qwen2 vocab (ids 151665-151668, user-defined, not special)
for i, t in zip(range(151665, 151669), (b"<tool_response>", b"</tool_response>", b"<think>", b"</think>")):
    assert toks[i].startswith(b"[PAD"), toks[i]
    toks[i] = t; types[i] = int(gguf.TokenType.USER_DEFINED)
tmpl = open(os.path.join(src, "models/templates/Qwen-Qwen3-0.6B.jinja")).read()
V = len(toks)
rng = np.random.default_rng(0)
def w(*shape, scale=None):
    s = scale if scale is not None else 1.0 / np.sqrt(shape[-1])
    return (rng.standard_normal(shape) * s).astype(np.float32)
dim, hidden, nl, nh, nkv, hd = 64, 128, 2, 4, 2, 16
g = gguf.GGUFWriter(out, "qwen3")
g.add_name("toy-qwen3"); g.add_context_length(4096); g.add_file_type(gguf.LlamaFileType.ALL_F32)
g.add_tokenizer_model("gpt2"); g.add_tokenizer_pre(sval("tokenizer.ggml.pre"))
g.add_token_list(toks); g.add_token_types(types); g.add_token_merges(merges)
g.add_eos_token_id(151645); g.add_bos_token_id(151643); g.add_pad_token_id(151643)  # as in Qwen3-0.6B
g.add_add_bos_token(False)
g.add_chat_template(tmpl)
g.add_embedding_length(dim); g.add_block_count(nl); g.add_feed_forward_length(hidden)
g.add_head_count(nh); g.add_head_count_kv(nkv); g.add_key_length(hd); g.add_value_length(hd)
g.add_layer_norm_rms_eps(1e-6); g.add_rope_freq_base(1e6)
g.add_tensor("token_embd.weight", w(V, dim, scale=1.0))
for i in range(nl):
    p = "blk.%d." % i
    g.add_tensor(p+"attn_norm.weight", np.ones(dim, np.float32))
    g.add_tensor(p+"attn_q.weight", w(nh*hd, dim)); g.add_tensor(p+"attn_k.weight", w(nkv*hd, dim))
    g.add_tensor(p+"attn_v.weight", w(nkv*hd, dim)); g.add_tensor(p+"attn_output.weight", w(dim, nh*hd))
    g.add_tensor(p+"attn_q_norm.weight", np.ones(hd, np.float32)); g.add_tensor(p+"attn_k_norm.weight", np.ones(hd, np.float32))
    g.add_tensor(p+"ffn_norm.weight", np.ones(dim, np.float32))
    g.add_tensor(p+"ffn_gate.weight", w(hidden, dim)); g.add_tensor(p+"ffn_up.weight", w(hidden, dim))
    g.add_tensor(p+"ffn_down.weight", w(dim, hidden))
g.add_tensor("output_norm.weight", np.ones(dim, np.float32)); g.add_tensor("output.weight", w(V, dim, scale=0.5))
g.write_header_to_file(); g.write_kv_data_to_file(); g.write_tensors_to_file(); g.close()
print("wrote", out, "vocab", V)
