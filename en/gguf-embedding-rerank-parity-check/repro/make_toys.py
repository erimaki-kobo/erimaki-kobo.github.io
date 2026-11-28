"""Build tiny random-weight embedding / reranker checkpoints in Hugging Face format.

The vocabularies are real: they are read from llama.cpp's models/ggml-vocab-bert-bge.gguf
(BERT WordPiece, as in BAAI/bge-small-en-v1.5) and models/ggml-vocab-qwen2.gguf (Qwen2 BPE,
which Qwen3 uses). Weights are random (seeded), which is enough to test whether an engine
computes the same function as sentence-transformers / transformers: pooling, normalization,
prefixes, truncation, segment ids and classifier heads do not depend on trained weights.

usage: python make_toys.py <llama.cpp dir> <out dir>
"""
import json, os, sys
import torch
import gguf
from transformers import (BertConfig, BertModel, BertForSequenceClassification, BertTokenizerFast,
                          Qwen3Config, Qwen3ForCausalLM, PreTrainedTokenizerFast)

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)


def field_strs(r, key):
    f = r.fields[key]
    return [bytes(f.parts[i]).decode("utf-8") for i in f.data]


# ---------- BERT WordPiece vocab ----------
r = gguf.GGUFReader(os.path.join(src, "models/ggml-vocab-bert-bge.gguf"))
btoks = field_strs(r, "tokenizer.ggml.tokens")
btypes = [int(r.fields["tokenizer.ggml.token_type"].parts[i][0]) for i in r.fields["tokenizer.ggml.token_type"].data]
vocab = []
for t, ty in zip(btoks, btypes):
    if ty == gguf.TokenType.CONTROL:
        vocab.append(t)
    elif t.startswith("▁"):
        vocab.append(t[1:])
    else:
        vocab.append("##" + t)
vt = os.path.join(out, "_bert_vocab.txt")
with open(vt, "w", encoding="utf-8") as f:
    f.write("\n".join(vocab) + "\n")


def bert_tok():
    return BertTokenizerFast(vocab=vt, do_lower_case=True, model_max_length=512)


def bert_cfg(**kw):
    return BertConfig(vocab_size=len(vocab), hidden_size=64, num_hidden_layers=2, num_attention_heads=4,
                      intermediate_size=128, max_position_embeddings=512, type_vocab_size=2, **kw)


def st_files(d, pooling, normalize=True, prompts=None, default_prompt=None, max_seq=512):
    mods = [{"idx": 0, "name": "0", "path": "", "type": "sentence_transformers.models.Transformer"},
            {"idx": 1, "name": "1", "path": "1_Pooling", "type": "sentence_transformers.models.Pooling"}]
    if normalize:
        mods.append({"idx": 2, "name": "2", "path": "2_Normalize", "type": "sentence_transformers.models.Normalize"})
        os.makedirs(os.path.join(d, "2_Normalize"), exist_ok=True)
    json.dump(mods, open(os.path.join(d, "modules.json"), "w"), indent=1)
    os.makedirs(os.path.join(d, "1_Pooling"), exist_ok=True)
    json.dump({"word_embedding_dimension": 64, "pooling_mode_cls_token": pooling == "cls",
               "pooling_mode_mean_tokens": pooling == "mean", "pooling_mode_max_tokens": False,
               "pooling_mode_lasttoken": pooling == "last"},
              open(os.path.join(d, "1_Pooling", "config.json"), "w"), indent=1)
    json.dump({"max_seq_length": max_seq, "do_lower_case": False},
              open(os.path.join(d, "sentence_bert_config.json"), "w"))
    cfg = {"prompts": prompts or {}, "default_prompt_name": default_prompt, "similarity_fn_name": "cosine"}
    json.dump(cfg, open(os.path.join(d, "config_sentence_transformers.json"), "w"), indent=1)


def save_bert_embed(name, seed, pooling, **kw):
    torch.manual_seed(seed)
    d = os.path.join(out, name)
    m = BertModel(bert_cfg(), add_pooling_layer=True).eval()
    m.save_pretrained(d)
    bert_tok().save_pretrained(d)
    if pooling:
        st_files(d, pooling, **kw)
    print("wrote", d)


# A: bge-style, CLS pooling + Normalize
save_bert_embed("bert-cls-norm", 1, "cls")
# B: MiniLM-style, mean pooling + Normalize, max_seq_length 128 (like all-MiniLM-L6-v2's 256)
save_bert_embed("bert-mean-norm", 2, "mean", max_seq=128)
# C: E5-style, mean pooling, default prompt "query: " applied by sentence-transformers
save_bert_embed("bert-mean-prompt", 3, "mean", prompts={"query": "query: ", "passage": "passage: "},
                default_prompt="query")
# D: plain HF checkpoint with no sentence-transformers files (no modules.json)
save_bert_embed("bert-no-st-files", 4, None)

# E: cross-encoder (BertForSequenceClassification, 1 label, pooler present)
torch.manual_seed(5)
d = os.path.join(out, "bert-cross-encoder")
m = BertForSequenceClassification(bert_cfg(num_labels=1)).eval()
with torch.no_grad():  # make the head and pooler large enough that scores spread out
    m.classifier.weight.mul_(20.0)
m.save_pretrained(d)
bert_tok().save_pretrained(d)
print("wrote", d)

# ---------- Qwen2/Qwen3 BPE vocab ----------
from tokenizers import Tokenizer, models, pre_tokenizers, decoders, normalizers, Regex, AddedToken

r = gguf.GGUFReader(os.path.join(src, "models/ggml-vocab-qwen2.gguf"))
qtoks = field_strs(r, "tokenizer.ggml.tokens")
qtypes = [int(r.fields["tokenizer.ggml.token_type"].parts[i][0]) for i in r.fields["tokenizer.ggml.token_type"].data]
merges = field_strs(r, "tokenizer.ggml.merges")
extra = ["<tool_response>", "</tool_response>", "<think>", "</think>"]  # Qwen3 additions 151665-151668
qtoks = list(qtoks)
for k, t in enumerate(extra):  # ids 151665-151668 are [PAD] placeholders in the vocab file
    assert qtoks[151665 + k].startswith("[PAD")
    qtoks[151665 + k] = t
allv = {t: i for i, t in enumerate(qtoks)}
tk = Tokenizer(models.BPE(vocab=allv, merges=[tuple(m.split(" ", 1)) for m in merges], byte_fallback=False))
tk.normalizer = normalizers.NFC()
QWEN2_RE = r"""(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"""
tk.pre_tokenizer = pre_tokenizers.Sequence([
    pre_tokenizers.Split(Regex(QWEN2_RE), behavior="isolated", invert=False),
    pre_tokenizers.ByteLevel(add_prefix_space=False, trim_offsets=False, use_regex=False)])
tk.decoder = decoders.ByteLevel(add_prefix_space=False, trim_offsets=False, use_regex=False)
tk.add_special_tokens([AddedToken(t, special=True, normalized=False)
                       for t, ty in zip(qtoks, qtypes) if ty == gguf.TokenType.CONTROL])
tk.add_tokens([AddedToken(t, special=False, normalized=False) for t in extra])
V = len(qtoks)
assert tk.token_to_id("<|im_start|>") == 151644 and tk.token_to_id("</think>") == 151668, tk.token_to_id("</think>")
qtok = PreTrainedTokenizerFast(tokenizer_object=tk, eos_token="<|im_end|>", pad_token="<|endoftext|>",
                               padding_side="left")


def save_qwen3(name, seed, readme):
    torch.manual_seed(seed)
    d = os.path.join(out, name)
    cfg = Qwen3Config(vocab_size=V, hidden_size=64, intermediate_size=128, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, head_dim=16, max_position_embeddings=4096,
                      tie_word_embeddings=False)
    m = Qwen3ForCausalLM(cfg).eval()
    with torch.no_grad():
        m.lm_head.weight.mul_(30.0)
    m.save_pretrained(d)
    qtok.save_pretrained(d)
    cfgj = json.load(open(os.path.join(d, "config.json")))
    cfgj.pop("_name_or_path", None)
    json.dump(cfgj, open(os.path.join(d, "config.json"), "w"), indent=1)
    if readme:
        open(os.path.join(d, "README.md"), "w").write("# Qwen3-Reranker toy\n")
    print("wrote", d)


# F: Qwen3-Reranker-style causal LM; README marks it as a reranker (the converter looks for this)
save_qwen3("qwen3-reranker-toy", 6, readme=True)
# G: the same weights saved where nothing tells the converter it is a reranker
save_qwen3("toy-model", 6, readme=False)
