"""Load vLLM's own KV-cache planning code from a source checkout, with stubs for
torch and the config objects, and expose one function: real_plan().

Usage: import real_vllm; real_vllm.load("<dir containing vllm/>")
Only the planning files are read; no GPU, no torch.
"""
import ast
import importlib
import importlib.util
import os
import sys
import types
from types import SimpleNamespace as NS


class _DType:
    def __init__(self, name, size):
        self.name, self.itemsize = name, size

    def __repr__(self):
        return "torch." + self.name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, o):
        return isinstance(o, _DType) and o.name == self.name


def _mod(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


class _Anything:
    """Stands in for names that are imported but never used by the plan path."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, n):
        return _Anything()

    def __call__(self, *a, **k):
        return _Anything()


def load(root):
    for k in [k for k in sys.modules if k == "vllm" or k.startswith("vllm.")]:
        del sys.modules[k]
    torch = _mod("torch")
    torch.dtype = _DType
    torch.Tensor = object
    for n, s in [("float16", 2), ("bfloat16", 2), ("float32", 4), ("uint8", 1),
                 ("int8", 1), ("int32", 4), ("float8_e4m3fn", 1), ("float8_e5m2", 1)]:
        setattr(torch, n, _DType(n, s))

    class _Log:
        def __getattr__(self, n):
            return lambda *a, **k: None

    for pkg in ["vllm", "vllm.utils", "vllm.v1", "vllm.v1.core", "vllm.v1.attention",
                "vllm.v1.attention.backends", "vllm.v1.hisparse", "vllm.config"]:
        m = _mod(pkg)
        m.__path__ = [os.path.join(root, *pkg.split("."))]
    _mod("vllm.logger", init_logger=lambda n: _Log())
    _mod("vllm.utils.torch_utils", get_dtype_size=lambda d: d.itemsize)
    _mod("vllm.utils.mem_utils", format_gib=lambda b: f"{b / (1 << 30):.2f}")
    _mod("vllm.utils.import_utils", resolve_obj_by_qualname=lambda q: getattr(
        sys.modules["vllm.v1.core.kv_cache_planning"], "DefaultKVCacheConfigBuilder"))
    _mod("vllm.platforms", current_platform=NS(
        get_kv_cache_config_builder_cls=lambda cfg: "default"))
    sys.modules["vllm.config"].SpeculativeConfig = type("SpeculativeConfig", (), {})
    sys.modules["vllm.config"].VllmConfig = type("VllmConfig", (), {})
    import enum

    class MambaAttentionBackendEnum(enum.Enum):
        MAMBA1 = 1
        MAMBA2 = 2

    _mod("vllm.v1.attention.backends.registry",
         MambaAttentionBackendEnum=MambaAttentionBackendEnum)
    _mod("vllm.v1.attention.backend", MultipleOf=type("MultipleOf", (), {}))
    _mod("vllm.v1.hisparse.layout",
         get_hisparse_host_pool_bytes=lambda *a, **k: 0,
         get_hisparse_kv_cache_config=lambda *a, **k: None,
         get_hisparse_pool_bytes_per_block=lambda *a, **k: None,
         get_hisparse_kv_cache_groups=lambda *a, **k: None,
         **{n: _Anything() for n in ("get_hisparse_host_num_blocks",
                                      "get_hisparse_page_size",
                                      "validate_hisparse_kv_cache")})
    # kv_cache_utils.py pulls in the whole engine; take only what planning needs.
    src = open(os.path.join(root, "vllm/v1/core/kv_cache_utils.py")).read()
    tree = ast.parse(src)
    want = {"get_max_concurrency_for_kv_cache_config", "get_kv_cache_capacity",
            "_kv_cache_device_name"}
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
    assert {n.name for n in body} == want, {n.name for n in body}
    kvu = _mod("vllm.v1.core.kv_cache_utils")
    from vllm.utils.math_utils import cdiv
    kvu.cdiv = cdiv
    kvu.VllmConfig = kvu.KVCacheConfig = object
    kvu.update_kv_cache_capacity = lambda *a, **k: None
    code = compile(ast.Module(body=body, type_ignores=[]), "kv_cache_utils.py", "exec")
    exec(code, kvu.__dict__)
    # hisparse layout names vary by version: let any missing name resolve.
    hl = sys.modules["vllm.v1.hisparse.layout"]
    hl.__getattr__ = lambda n: _Anything()
    iface = importlib.import_module("vllm.v1.kv_cache_interface")
    plan = importlib.import_module("vllm.v1.core.kv_cache_planning")
    # Register the spec classes with vLLM's own registration table (the function
    # body is taken from the source; manager classes are placeholders).
    src = open(os.path.join(root, "vllm/v1/core/single_type_kv_cache_manager.py")).read()
    fn = [n for n in ast.parse(src).body
          if isinstance(n, ast.FunctionDef) and n.name == "register_all_kvcache_specs"]
    assert len(fn) == 1

    class _NS(dict):
        def __missing__(self, k):
            if hasattr(iface, k):
                return getattr(iface, k)
            if k.endswith("Manager"):
                v = type(k, (), {})
                self[k] = v
                return v
            raise KeyError(k)

    ns = _NS(KVCacheSpecRegistry=iface.KVCacheSpecRegistry)
    sys.modules["vllm.platforms"].current_platform.register_custom_kv_cache_specs = (
        lambda cfg: None)
    exec(compile(ast.Module(body=fn, type_ignores=[]), "register", "exec"), ns)
    ns["register_all_kvcache_specs"](None)
    return NS(torch=torch, iface=iface, plan=plan, utils=kvu)


def make_config(m, *, max_model_len, in_flight, disable_hybrid, tp=1):
    cfg = sys.modules["vllm.config"].VllmConfig()
    layout = getattr(m.iface, "KVCacheLayout")
    cfg.model_config = NS(max_model_len=max_model_len, original_max_model_len=max_model_len,
                          supports_kv_cache_grouping=False, architectures=["X"],
                          registry=NS(resolve_model_cls=lambda *a, **k: (object, "X")))
    cfg.cache_config = NS(num_gpu_blocks_override=None, num_gpu_blocks=None,
                          enable_extensible_kv_cache=False,
                          resolved_gpu_memory_utilization=0.92, gpu_memory_utilization=0.92,
                          mamba_cache_mode="none", prefix_cache_retention_interval=None,
                          kv_cache_config_builder=None,
                          get_resolved_kv_cache_layout=lambda *a, **k: layout.BLNHD
                          if hasattr(layout, "BLNHD") else list(layout)[0])
    cfg.scheduler_config = NS(disable_hybrid_kv_cache_manager=disable_hybrid,
                              max_num_encoder_input_tokens=0,
                              max_num_batched_tokens=in_flight)
    cfg.parallel_config = NS(tensor_parallel_size=tp, decode_context_parallel_size=1,
                             pipeline_parallel_size=1, prefill_context_parallel_size=1)
    cfg.attention_config = NS(hisparse_config=None)
    cfg.device_config = NS(device_type="cuda")
    cfg.speculative_config = None
    cfg.max_in_flight_tokens = in_flight
    cfg.num_prefill_lookahead_tokens = 0
    cfg.num_lookahead_tokens = 0
    return cfg


def real_plan(m, layers, available_bytes, max_model_len, in_flight, disable_hybrid):
    """layers: list of dicts kind/num_kv_heads/head_size/head_size_v/dtype_bytes/
    block_size/sliding_window. Returns dict or {'error': str}."""
    I, P, t = m.iface, m.plan, m.torch
    dt = {2: t.float16, 4: t.float32, 1: t.uint8}
    specs = {}
    for i, l in enumerate(layers):
        common = dict(block_size=l["block_size"], num_kv_heads=l["num_kv_heads"],
                      head_size=l["head_size"], dtype=dt[l["dtype_bytes"]])
        if l["kind"] == "full":
            s = I.FullAttentionSpec(**common)
        elif l["kind"] == "mla":
            s = I.MLAAttentionSpec(**common)
        else:
            s = I.SlidingWindowSpec(**common, sliding_window=l["sliding_window"])
        specs[f"layer.{i}"] = s
    cfg = make_config(m, max_model_len=max_model_len, in_flight=in_flight,
                      disable_hybrid=disable_hybrid)
    try:
        groups = P.get_global_kv_cache_groups(cfg, [specs])
        kv = P.get_kv_cache_configs(cfg, [specs], [available_bytes], groups)[0]
        fits = True
        err = None
    except ValueError as e:
        fits, err = False, str(e)
        try:
            groups = P.get_global_kv_cache_groups(cfg, [specs])
        except Exception as e2:
            return {"error": "group: " + str(e2)[:200]}
        # rebuild the config without the admission check to compare numbers
        b = sys.modules["vllm.v1.core.kv_cache_config_builder"].get_kv_cache_config_builder(cfg)
        pg = P._project_kv_cache_groups_to_worker(groups, specs)
        bpb = P._pool_bytes_per_block_from_builder(b, cfg, pg)
        if available_bytes // bpb <= 0:
            return {"fits": False, "num_blocks": 0, "error_text": err}
        kv = b.get_kv_cache_config_from_groups(cfg, pg, available_bytes // bpb)
    tokens, conc = m.utils.get_kv_cache_capacity(cfg, kv)
    out = {"fits": fits, "num_blocks": kv.num_blocks, "tokens": tokens,
           "concurrency": conc, "num_groups": len(kv.kv_cache_groups)}
    if err:
        out["error_text"] = err
        import re
        mm = re.search(r"estimated maximum model length is (\d+)", err)
        out["est"] = int(mm.group(1)) if mm else None
    return out
