#!/usr/bin/env python3
"""Small GGUF files for test_parser.mjs: a.gguf, b.gguf (other template and add_bos_token, same tensors), c.gguf (other weights).
Needs pip install gguf numpy."""
import gguf, numpy as np
def mk(path, tmpl, bos, scale=1.0):
    w = gguf.GGUFWriter(path, "llama")
    w.add_name("toy"); w.add_chat_template(tmpl); w.add_add_bos_token(bos)
    w.add_token_list(["a", "b", "c"] * 1000); w.add_tokenizer_model("gpt2"); w.add_tokenizer_pre("qwen2")
    rng = np.random.default_rng(0)
    for i in range(20):
        w.add_tensor(f"blk.{i}.w", (rng.standard_normal((64, 64)) * scale).astype(np.float32))
    w.write_header_to_file(); w.write_kv_data_to_file(); w.write_tensors_to_file(); w.close()
mk("a.gguf", "{{ x }}", True); mk("b.gguf", "{{ x }} fixed", False); mk("c.gguf", "{{ x }}", True, 2.0)
