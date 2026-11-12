#!/usr/bin/env python3
"""kvplan.py - KV-cache capacity planner for vLLM (follows vLLM v0.33.0).

Answers "how many tokens / how many concurrent requests fit?" the way vLLM
itself computes it at startup, instead of a flat bytes-per-token estimate:

  budget      = ceil(total_gpu_memory * gpu_memory_utilization)
  KV memory   = budget - weights - activation peak - CUDA graph estimate
                (or exactly --kv-cache-memory-bytes)
  block bytes = layers in the widest KV group * page bytes
  num_blocks  = KV memory // block bytes
  concurrency = num_blocks / blocks one max_model_len request needs
  "GPU KV cache size: N tokens" = int(concurrency * max_model_len)

Two ways to use it:

  # 1. Before launch, from config.json
  python kvplan.py plan --config config.json --gpu-gib 24 --weights-gib 14.96 \\
        --max-model-len 32768

  # 2. After launch, from the startup log (works for every model)
  python kvplan.py log --file vllm.log --max-model-len 16384

Covered from config.json: full attention (MHA/GQA/MQA), DeepSeek-style MLA,
interleaved sliding-window models (Gemma 2/3, gpt-oss), all-sliding models,
tensor parallel, fp8 KV. Not covered (use the log mode): Mamba / linear-attention
hybrids, DeepSeek-V4 sparse MLA, HiSparse, packed KV quantisation formats,
encoder-decoder, pipeline / context parallel, draft models.

Stdlib only. MIT License.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field

GIB = 1 << 30
VLLM_VERSION = "v0.33.0"


def cdiv(a: int, b: int) -> int:
    return -(a // -b)


class Unsupported(Exception):
    """The model needs a KV layout this script does not reproduce."""


# --------------------------------------------------------------------------
# Layer specs (vllm/v1/kv_cache_interface.py)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Layer:
    kind: str  # "full" | "mla" | "sliding"
    num_kv_heads: int
    head_size: int
    head_size_v: int
    dtype_bytes: int
    block_size: int
    sliding_window: int | None = None

    @property
    def bytes_per_token(self) -> int:
        # AttentionSpec.state_content_size_bytes * num_heads
        return self.num_kv_heads * (self.head_size + self.head_size_v) * self.dtype_bytes

    @property
    def page_bytes(self) -> int:
        # AttentionSpec.page_size_bytes (one block of block_size tokens)
        return self.bytes_per_token * self.block_size

    def blocks_per_request(self, max_model_len: int, in_flight_tokens: int) -> int:
        if self.kind == "sliding":
            # SlidingWindowSpec.max_admission_blocks_per_request
            tokens = min(self.sliding_window - 1 + in_flight_tokens, max_model_len)
            return cdiv(tokens, self.block_size) + 1
        # FullAttentionSpec.max_memory_usage_bytes / page_size_bytes
        return cdiv(max_model_len, self.block_size)


@dataclass
class Group:
    spec: Layer
    num_layers: int


def group_layers(layers: list[Layer], disable_hybrid: bool = False) -> list[Group]:
    """get_kv_cache_groups for the supported subset."""
    if disable_hybrid:
        kinds = {l.kind for l in layers}
        if "sliding" in kinds and "full" in kinds:
            if len({l.sliding_window for l in layers if l.kind == "sliding"}) > 1:
                # vLLM itself refuses to merge two window sizes into one group
                raise Unsupported("two sliding-window sizes with the hybrid KV "
                                  "cache manager disabled")
            # unify_hybrid_kv_cache_specs: allocate sliding layers as full
            layers = [
                Layer("full", l.num_kv_heads, l.head_size, l.head_size_v,
                      l.dtype_bytes, l.block_size)
                if l.kind == "sliding" else l
                for l in layers
            ]
    if not layers:
        return []
    buckets: dict[Layer, int] = {}
    for l in layers:
        buckets[l] = buckets.get(l, 0) + 1
    if len(buckets) == 1:
        return [Group(layers[0], len(layers))]
    if len({l.page_bytes for l in buckets}) != 1:
        raise Unsupported(
            "layers with different page sizes are packed by a layout this "
            "script does not reproduce"
        )
    if any(l.kind == "mla" for l in buckets):
        raise Unsupported("MLA mixed with other attention types")
    # _get_kv_cache_groups_uniform_page_size
    counts = list(buckets.values())
    group_size = min(counts)
    if max(counts) < group_size * 1.5:
        group_size = max(counts)
    groups: list[Group] = []
    for spec, n in buckets.items():
        num_groups = cdiv(n, group_size)
        for i in range(num_groups):
            groups.append(Group(spec, cdiv(n - i, num_groups)))  # len(layers[i::num_groups])
    return groups


def bytes_per_block(groups: list[Group]) -> int:
    """_get_kv_cache_bytes_per_block: the widest group's pages."""
    return max(g.num_layers * g.spec.page_bytes for g in groups)


@dataclass
class Plan:
    num_blocks: int
    block_bytes: int
    blocks_per_request: int
    concurrency: float
    tokens: int
    fits: bool
    estimated_max_model_len: int
    num_groups: int
    padding_layers: int
    notes: list[str] = field(default_factory=list)


def _blocks_per_request(groups: list[Group], max_model_len: int, in_flight: int) -> int:
    return sum(g.spec.blocks_per_request(max_model_len, in_flight) for g in groups)


def plan(
    layers: list[Layer],
    available_bytes: int,
    max_model_len: int,
    *,
    in_flight_tokens: int = 4096,
    disable_hybrid: bool = False,
) -> Plan:
    """get_kv_cache_configs + get_kv_cache_capacity for one GPU."""
    groups = group_layers(layers, disable_hybrid)
    bpb = bytes_per_block(groups)
    num_blocks = available_bytes // bpb
    per_req = _blocks_per_request(groups, max_model_len, in_flight_tokens)
    concurrency = num_blocks / per_req
    # One block is the permanently reserved null block.
    check_memory = available_bytes - bpb

    def fits(length: int) -> bool:
        return bpb * _blocks_per_request(groups, length, in_flight_tokens) <= check_memory

    ok = check_memory > 0 and fits(max_model_len)
    est = 0
    if check_memory > 0 and fits(1):
        lo, hi, est = 1, max_model_len, 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if fits(mid):
                est, lo = mid, mid + 1
            else:
                hi = mid - 1
    widest = max(g.num_layers for g in groups)
    padding = sum(widest - g.num_layers for g in groups)
    return Plan(
        num_blocks=num_blocks,
        block_bytes=bpb,
        blocks_per_request=per_req,
        concurrency=concurrency,
        tokens=int(concurrency * max_model_len),
        fits=ok,
        estimated_max_model_len=est,
        num_groups=len(groups),
        padding_layers=padding,
    )


def requests_that_fit(
    layers: list[Layer],
    num_blocks: int,
    tokens_per_request: int,
    *,
    in_flight_tokens: int = 4096,
    disable_hybrid: bool = False,
) -> int:
    """Whole requests of a given length (prompt + output) held at once,
    ignoring prefix-cache sharing. One block is the reserved null block."""
    groups = group_layers(layers, disable_hybrid)
    per = _blocks_per_request(groups, tokens_per_request, in_flight_tokens)
    return max(num_blocks - 1, 0) // per


# --------------------------------------------------------------------------
# Memory budget (vllm/v1/worker/utils.py request_memory, gpu_worker.py)
# --------------------------------------------------------------------------


def kv_memory_bytes(
    total_bytes: int,
    gpu_memory_utilization: float,
    non_kv_bytes: int,
    cudagraph_bytes: int = 0,
) -> int:
    requested = math.ceil(total_bytes * gpu_memory_utilization)
    return requested - non_kv_bytes - cudagraph_bytes


def default_batch(total_gib: float, device_name: str = "", serve: bool = True,
                  compute_capability: str = "") -> tuple[int, int]:
    """(max_num_seqs, max_num_batched_tokens) defaults, v0.33.0 get_batch_defaults."""
    name = device_name.lower()
    if total_gib >= 160:
        return 1024, 16384
    if total_gib >= 70 and "a100" not in name and compute_capability != "12.1":
        return 1024, 8192 if serve else 16384
    return 256, 2048 if serve else 8192


# --------------------------------------------------------------------------
# config.json -> layers (vllm/transformers_utils/model_arch_config_convertor.py,
# vllm/model_executor/layers/attention/attention.py, transformers 5.22.2 config
# class defaults for keys that hub configs leave out)
# --------------------------------------------------------------------------

MLA_MODEL_TYPES = {
    "axk1", "deepseek_v2", "deepseek_v3", "deepseek_v32", "deepseek_v4",
    "deepseek_v41", "dots3_note", "deepseek_mtp", "k3_dspark", "glm5_next",
    "glm5_next_text", "glm_moe_dsa", "glm4_moe_lite", "glm4_moe_lite_mtp",
    "kimi_k2", "kimi_linear", "longcat_flash", "pangu_ultra_moe",
    "pangu_ultra_moe_mtp", "bailing_hybrid", "bailing_hybrid_mtp",
    "bailing_hybrid_v3_mtp", "hy_v4", "hy_v4_mtp",
}

# Values the transformers config class fills in when config.json omits the key.
CLASS_DEFAULTS = {
    "gemma3_text": dict(num_hidden_layers=26, hidden_size=2304, num_attention_heads=8,
                        num_key_value_heads=4, head_dim=256, sliding_window=4096,
                        max_position_embeddings=131072),
    "gemma2": dict(num_hidden_layers=26, hidden_size=2304, num_attention_heads=8,
                   num_key_value_heads=4, head_dim=256, sliding_window=4096,
                   max_position_embeddings=8192),
    "gpt_oss": dict(num_hidden_layers=36, hidden_size=2880, num_attention_heads=64,
                    num_key_value_heads=8, head_dim=64, sliding_window=128,
                    max_position_embeddings=131072),
    "qwen2": dict(num_hidden_layers=32, hidden_size=4096, num_attention_heads=32,
                  num_key_value_heads=32, max_position_embeddings=32768),
    "qwen3": dict(num_hidden_layers=32, hidden_size=4096, num_attention_heads=32,
                  num_key_value_heads=32, head_dim=128, max_position_embeddings=32768),
    "mistral": dict(num_hidden_layers=32, hidden_size=4096, num_attention_heads=32,
                    num_key_value_heads=8, sliding_window=4096,
                    max_position_embeddings=131072),
    "llama": dict(num_hidden_layers=32, hidden_size=4096, num_attention_heads=32,
                  max_position_embeddings=2048),
    "phi3": dict(num_hidden_layers=32, hidden_size=3072, num_attention_heads=32,
                 max_position_embeddings=4096),
    "deepseek_v3": dict(num_hidden_layers=61, hidden_size=7168, num_attention_heads=128,
                        kv_lora_rank=512, qk_rope_head_dim=64,
                        max_position_embeddings=4096),
}
# Interleaved sliding-window pattern when layer_types is absent:
# layer i is sliding unless (i + 1) % pattern == 0.
SLIDING_PATTERN = {"gemma3_text": ("sliding_window_pattern", 6), "gemma2": (None, 2),
                   "gpt_oss": (None, 2)}
KV_HEAD_KEYS = ("n_head_kv", "num_kv_heads", "num_key_value_heads",
                "multi_query_group_num", "num_attention_groups")
KV_DTYPE_BYTES = {"auto": 2, "float16": 2, "bfloat16": 2, "float32": 4,
                  "fp8": 1, "fp8_e4m3": 1, "fp8_e5m2": 1}


@dataclass
class ModelShape:
    model_type: str
    kind: str  # "full" | "mla" | "hybrid" | "sliding"
    num_layers: int
    total_kv_heads: int
    head_size: int
    sliding_window: int | None
    sliding_layers: list[bool]
    max_position_embeddings: int | None
    notes: list[str]


def read_config(config: dict) -> ModelShape:
    notes: list[str] = []
    outer_type = config.get("model_type", "")
    text = config
    for key in ("text_config", "llm_config", "language_config"):
        if isinstance(config.get(key), dict):
            text = config[key]
            notes.append(f"using {key}")
            break
    mt = text.get("model_type") or {"gemma3": "gemma3_text"}.get(outer_type, outer_type)
    defaults = CLASS_DEFAULTS.get(mt, {})

    def get(key, fallback=None):
        if key in text:  # an explicit null stays null, as in transformers
            return text[key] if text[key] is not None else fallback
        if key in defaults:
            notes.append(f"{key} not in config.json; using the {mt} class default "
                         f"{defaults[key]}")
            return defaults[key]
        return fallback

    if config.get("is_encoder_decoder") or text.get("is_encoder_decoder"):
        raise Unsupported("encoder-decoder model")
    layer_types = text.get("layer_types")
    if layer_types and any(t not in ("full_attention", "sliding_attention")
                           for t in layer_types):
        raise Unsupported("layer_types other than full / sliding attention "
                          "(linear-attention or state-space layers keep a fixed-size "
                          "state per request)")
    if text.get("compress_ratios") or text.get("compress_ratio"):
        raise Unsupported("DeepSeek-V4 style sparse MLA")
    if mt in ("mamba", "mamba2", "jamba", "bamba", "falcon_mamba", "zamba2",
              "qwen3_5", "qwen3_next", "gemma3n_text", "gemma3n"):
        raise Unsupported(f"{mt} keeps state this script does not reproduce")

    num_layers = get("num_hidden_layers")
    if not num_layers:
        raise Unsupported("num_hidden_layers not found")
    heads = get("num_attention_heads", 0)

    is_mla = mt in MLA_MODEL_TYPES and get("kv_lora_rank") is not None
    if is_mla:
        head_size = get("kv_lora_rank") + get("qk_rope_head_dim", 0)
        return ModelShape(mt, "mla", num_layers, 1, head_size, None, [False] * num_layers,
                          get("max_position_embeddings"), notes)

    total_kv = next((text[k] for k in KV_HEAD_KEYS if text.get(k) is not None), None)
    if total_kv is None and "num_key_value_heads" in text:
        total_kv = heads  # explicit null: same as the attention heads
    if total_kv is None:
        total_kv = defaults.get("num_key_value_heads")
        if total_kv is not None:
            notes.append(f"num_key_value_heads not in config.json; using the {mt} class "
                         f"default {total_kv}")
        else:
            total_kv = heads
    head_dim = get("head_dim")
    if head_dim and head_dim > 0:
        head_size = head_dim
    elif text.get("hidden_size_per_head") is not None:
        head_size = text["hidden_size_per_head"]
    else:
        hidden = get("hidden_size", 0)
        if not heads or not hidden:
            raise Unsupported("hidden_size / num_attention_heads not found")
        head_size = hidden // heads

    # Sliding window: transformers config post-processing, then vLLM's rule.
    window = get("sliding_window")
    if mt in ("qwen2", "qwen3", "qwen2_moe", "qwen3_moe") and not text.get(
            "use_sliding_window", False):
        window = None
    if window == 0:
        window = None
    if text.get("attention_chunk_size") is not None:
        notes.append("chunked local attention: vLLM turns the hybrid KV manager off "
                     "by default, so every layer is allocated as full attention")
        window = None
    sliding = [False] * num_layers
    if window is not None:
        if layer_types is None and mt in SLIDING_PATTERN:
            key, pattern = SLIDING_PATTERN[mt]
            if key and text.get(key):
                pattern = text[key]
            layer_types = ["sliding_attention" if (i + 1) % pattern else "full_attention"
                           for i in range(num_layers)]
            notes.append(f"layer_types not in config.json; derived from the {mt} "
                         f"pattern (every {pattern}th layer is full attention)")
        if layer_types is None and mt in ("qwen2", "qwen3", "qwen2_moe", "qwen3_moe"):
            mwl = text.get("max_window_layers", 28)
            layer_types = ["sliding_attention" if i >= mwl else "full_attention"
                           for i in range(num_layers)]
        if layer_types is None:
            sliding = [True] * num_layers  # CacheConfig.sliding_window applies to all
        else:
            sliding = [t == "sliding_attention" for t in layer_types[:num_layers]]
    if not any(sliding):
        kind, window = "full", None
    elif all(sliding):
        kind = "sliding"
    else:
        kind = "hybrid"
    return ModelShape(mt, kind, num_layers, total_kv, head_size, window, sliding,
                      get("max_position_embeddings"), notes)


def build_layers(shape: ModelShape, *, tensor_parallel: int = 1, kv_dtype: str = "auto",
                 model_dtype_bytes: int = 2, block_size: int = 16) -> list[Layer]:
    if kv_dtype not in KV_DTYPE_BYTES:
        raise Unsupported(f"kv_cache_dtype {kv_dtype}")
    dtype_bytes = model_dtype_bytes if kv_dtype == "auto" else KV_DTYPE_BYTES[kv_dtype]
    if shape.kind == "mla":
        return [Layer("mla", 1, shape.head_size, 0, dtype_bytes, block_size)
                for _ in range(shape.num_layers)]
    kv = max(1, shape.total_kv_heads // tensor_parallel)  # ModelConfig.get_num_kv_heads
    out = []
    for is_sliding in shape.sliding_layers:
        if is_sliding:
            out.append(Layer("sliding", kv, shape.head_size, shape.head_size, dtype_bytes,
                             block_size, shape.sliding_window))
        else:
            out.append(Layer("full", kv, shape.head_size, shape.head_size, dtype_bytes,
                             block_size))
    return out


# --------------------------------------------------------------------------
# Startup log
# --------------------------------------------------------------------------

LOG_PATTERNS = {
    "available_gib": r"Available KV cache memory: ([\d.]+) GiB",
    "tokens": r"KV cache size: ([\d,]+) tokens",
    "concurrency": r"Maximum concurrency for ([\d,]+) tokens per request: ([\d.]+)x",
    "gpu_blocks": r"# (?:GPU|cuda) blocks: (\d+)",
    "weights_gib": r"Model loading took ([\d.]+) GiB",
    "needed": (r"max seq len \((\d+)\), \(([\d.]+) GiB KV cache is needed, which is "
               r"larger than the available KV cache memory \(([\d.]+) GiB\)"),
    "est_max_len": r"estimated maximum model length is (\d+)",
    "free": (r"Free memory on device .*?\(([\d.]+)/([\d.]+) GiB\) on startup is less "
             r"than desired GPU memory utilization \(([\d.]+), ([\d.]+) GiB\)"),
    "reserved_gib": r"reserved ([\d.]+) GiB memory for KV Cache as specified by",
    "v0_kv_gib": r"memory reserved for KV Cache is ([\d.]+) ?GiB",
}


def parse_log(text: str) -> dict:
    out: dict = {}
    for key, pat in LOG_PATTERNS.items():
        m = re.search(pat, text)
        if not m:
            continue
        g = [x.replace(",", "") for x in m.groups()]
        if key == "concurrency":
            out["max_model_len"], out["concurrency"] = int(g[0]), float(g[1])
        elif key == "needed":
            out["max_model_len"] = int(g[0])
            out["needed_gib"], out["available_gib"] = float(g[1]), float(g[2])
        elif key == "free":
            out["free_gib"], out["total_gib"] = float(g[0]), float(g[1])
            out["utilization"], out["requested_gib"] = float(g[2]), float(g[3])
        elif key in ("tokens", "gpu_blocks", "est_max_len"):
            out[key] = int(g[0])
        else:
            out[key] = float(g[0])
    if "tokens" not in out and "gpu_blocks" in out:
        out["tokens"] = out["gpu_blocks"] * 16
    if "available_gib" not in out and "reserved_gib" in out:
        out["available_gib"] = out["reserved_gib"]
    if "available_gib" not in out and "v0_kv_gib" in out:
        out["available_gib"] = out["v0_kv_gib"]
    return out


def from_log(parsed: dict, *, new_available_gib: float | None = None,
             new_max_model_len: int | None = None) -> dict:
    """Rescale a measured run. Exact for full-attention and MLA models (KV per
    token is constant); an approximation for sliding-window models."""
    res: dict = {}
    if "needed_gib" in parsed and "max_model_len" in parsed:
        res["bytes_per_token"] = parsed["needed_gib"] * GIB / parsed["max_model_len"]
    elif "available_gib" in parsed and "tokens" in parsed and parsed["tokens"]:
        res["bytes_per_token"] = parsed["available_gib"] * GIB / parsed["tokens"]
    else:
        return res
    avail = new_available_gib if new_available_gib is not None else parsed.get("available_gib")
    length = new_max_model_len or parsed.get("max_model_len")
    if avail is not None:
        res["tokens"] = int(avail * GIB / res["bytes_per_token"])
        if length:
            res["max_model_len"] = length
            res["concurrency"] = res["tokens"] / length
            res["fits"] = res["concurrency"] >= 1
    return res


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _fmt_bytes(n: float) -> str:
    return f"{n / GIB:.2f} GiB" if n >= GIB else f"{n / 1024:.1f} KiB"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="from config.json, before launch")
    p.add_argument("--config", required=True)
    p.add_argument("--max-model-len", type=int)
    p.add_argument("--gpu-gib", type=float, help="total memory of one GPU, GiB")
    p.add_argument("--gpu-memory-utilization", type=float, default=0.92)
    p.add_argument("--weights-gib", type=float, default=0.0,
                   help="weights on one GPU, GiB (divide by --tensor-parallel-size)")
    p.add_argument("--overhead-gib", type=float, default=1.5,
                   help="activation peak + CUDA graphs + non-torch, GiB (assumption)")
    p.add_argument("--kv-cache-memory-gib", type=float,
                   help="KV memory directly (Available KV cache memory / "
                        "--kv-cache-memory-bytes)")
    p.add_argument("--tensor-parallel-size", type=int, default=1)
    p.add_argument("--kv-cache-dtype", default="auto")
    p.add_argument("--model-dtype-bytes", type=int, default=2)
    p.add_argument("--block-size", type=int, default=16)
    p.add_argument("--max-num-batched-tokens", type=int)
    p.add_argument("--concurrent-batches", type=int, default=2,
                   help="2 with async scheduling (default), 1 without")
    p.add_argument("--disable-hybrid-kv-cache-manager", action="store_true")
    p.add_argument("--typical-request-tokens", type=int)
    p.add_argument("--json", action="store_true")
    q = sub.add_parser("log", help="from a vLLM startup log")
    q.add_argument("--file", default="-")
    q.add_argument("--max-model-len", type=int)
    q.add_argument("--kv-cache-memory-gib", type=float)
    q.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "log":
        text = sys.stdin.read() if a.file == "-" else open(a.file, errors="replace").read()
        parsed = parse_log(text)
        if not parsed:
            print("no KV cache lines found in the log", file=sys.stderr)
            return 2
        res = from_log(parsed, new_available_gib=a.kv_cache_memory_gib,
                       new_max_model_len=a.max_model_len)
        if a.json:
            print(json.dumps({"log": parsed, "result": res}, indent=2))
            return 0
        print("from the log:", parsed)
        if res:
            print(f"KV per token: {res['bytes_per_token'] / 1024:.1f} KiB")
            if "concurrency" in res:
                print(f"KV cache size: {res['tokens']:,} tokens, "
                      f"{res['concurrency']:.2f}x at {res['max_model_len']:,} tokens")
        return 0

    try:
        shape = read_config(json.load(open(a.config)))
        layers = build_layers(shape, tensor_parallel=a.tensor_parallel_size,
                              kv_dtype=a.kv_cache_dtype,
                              model_dtype_bytes=a.model_dtype_bytes,
                              block_size=a.block_size)
    except Unsupported as e:
        print(f"not covered from config.json: {e}\nStart vLLM once and use "
              f"`kvplan.py log` on the startup log instead.", file=sys.stderr)
        return 3
    if a.kv_cache_memory_gib is not None:
        avail = int(a.kv_cache_memory_gib * GIB)
    elif a.gpu_gib is not None:
        avail = kv_memory_bytes(int(a.gpu_gib * GIB), a.gpu_memory_utilization,
                                int((a.weights_gib + a.overhead_gib) * GIB))
    else:
        ap.error("give --gpu-gib or --kv-cache-memory-gib")
    length = a.max_model_len or shape.max_position_embeddings
    if not length:
        ap.error("give --max-model-len")
    seqs, batched = default_batch(a.gpu_gib or 0)
    in_flight = a.concurrent_batches * (a.max_num_batched_tokens or batched)
    res = plan(layers, avail, length, in_flight_tokens=in_flight,
               disable_hybrid=a.disable_hybrid_kv_cache_manager)
    out = {
        "vllm": VLLM_VERSION, "model_type": shape.model_type, "kind": shape.kind,
        "layers": shape.num_layers, "kv_memory_gib": round(avail / GIB, 2),
        "block_bytes": res.block_bytes, "num_blocks": res.num_blocks,
        "kv_cache_size_tokens": res.tokens, "max_model_len": length,
        "max_concurrency": round(res.concurrency, 2), "fits": res.fits,
        "estimated_max_model_len": res.estimated_max_model_len,
        "default_max_num_seqs": seqs, "notes": shape.notes,
    }
    if a.typical_request_tokens:
        out["requests_of_typical_length"] = requests_that_fit(
            layers, res.num_blocks, a.typical_request_tokens,
            in_flight_tokens=in_flight,
            disable_hybrid=a.disable_hybrid_kv_cache_manager)
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"{shape.model_type}: {shape.kind}, {shape.num_layers} layers "
          f"(follows vLLM {VLLM_VERSION})")
    for n in shape.notes:
        print("  note:", n)
    print(f"KV memory            {avail / GIB:.2f} GiB")
    print(f"one block            {res.block_bytes:,} bytes "
          f"({layers[0].block_size} tokens x widest group)")
    print(f"blocks               {res.num_blocks:,}")
    print(f"GPU KV cache size    {res.tokens:,} tokens")
    print(f"Maximum concurrency  {res.concurrency:.2f}x for {length:,} tokens per request")
    if not res.fits:
        print(f"DOES NOT START: one {length:,}-token request does not fit; "
              f"estimated maximum model length {res.estimated_max_model_len:,}")
    if "requests_of_typical_length" in out:
        print(f"requests of {a.typical_request_tokens:,} tokens held at once: "
              f"{out['requests_of_typical_length']:,} "
              f"(default max_num_seqs here: {seqs})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
