"""Run vLLM's own MoE backend selection (oracle/*.py) for a fake CUDA GPU.
usage: CUDA_VISIBLE_DEVICES= python3 run_select.py <vllm worktree> <cap e.g. 120> <flashinfer 0/1> <humming 0/1> [moe_backend]
prints one JSON line per scenario."""
import sys, os, json, io, contextlib, dataclasses, inspect, logging
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here); sys.path.insert(0, sys.argv[1])
import stubenv
stubenv.STUB_PKGS.add('triton_kernels')
import re as _re0
_req = open(os.path.join(sys.argv[1], 'requirements/cuda.txt')).read()
_m0 = _re0.search(r'(?m)^flashinfer-python==([0-9][^\s;#]*)', _req)
if _m0 and sys.argv[3] == '1':
    stubenv.FLASHINFER_VERSION = _m0.group(1)
    try:
        import importlib.util as _iu
        if _iu.find_spec('flashinfer') is None: stubenv.STUB_PKGS.add('flashinfer')
    except Exception: stubenv.STUB_PKGS.add('flashinfer')
stubenv.STUB_PREFIXES += ('vllm.third_party.triton_kernels',)
if os.environ.get('STUB_FA'): stubenv.STUB_PREFIXES += ('vllm.vllm_flash_attn',)
CAP = int(sys.argv[2]); FI = sys.argv[3] == "1"; HUM = sys.argv[4] == "1"
FORCE = sys.argv[5] if len(sys.argv) > 5 else "auto"
TAG = os.path.basename(sys.argv[1].rstrip("/")).replace("wt_", "")
def vtuple(t): return tuple(int(x) for x in t.lstrip("v").split(".")[:3])
V = vtuple(TAG)

import vllm.platforms as P
from vllm.platforms.cuda import CudaPlatform
from vllm.platforms.interface import DeviceCapability
class FakeCuda(CudaPlatform):
    @classmethod
    def get_device_capability(cls, device_id=0): return DeviceCapability(CAP // 10, CAP % 10)
    @classmethod
    def get_device_name(cls, device_id=0): return f"FAKE_SM{CAP}"
    @classmethod
    def has_device_capability(cls, capability, device_id=0):
        if isinstance(capability, tuple): capability = capability[0] * 10 + capability[1]
        return CAP >= capability
    @classmethod
    def is_device_capability(cls, capability, device_id=0):
        if isinstance(capability, tuple): capability = capability[0] * 10 + capability[1]
        return CAP == capability
    @classmethod
    def is_device_capability_family(cls, capability, device_id=0):
        return CAP // 10 == capability // 10
P.current_platform = FakeCuda()

# --- C++ predicates, re-implemented from csrc at the tag (see README.md) ---
import vllm._custom_ops as ops
def _cgg(cap):
    if V >= (0, 15, 1) and (cap < 90 or cap >= 110): return False
    return cap >= 90            # SM90 needs CUDA>=12.3, SM100 CUDA>=12.8; official wheels are >=12.8
ops.cutlass_group_gemm_supported = _cgg
# not used by MoE backend choice; dense-GEMM predicates only (cap>=89 fp8, >=90 block fp8 in csrc)
ops.cutlass_scaled_mm_supports_fp8 = lambda cap: cap >= 89
ops.cutlass_scaled_mm_supports_block_fp8 = lambda cap: cap >= 90
ops.mxfp4_experts_quant_supported = lambda cap: 100 <= cap < 120
# --- optional packages ---
import vllm.utils.flashinfer as F
for n in dir(F):
    if n.startswith("has_flashinfer"):
        setattr(F, n, (lambda *a, **k: FI))
import vllm.utils.import_utils as IU
if hasattr(IU, "has_humming"): IU.has_humming = lambda: HUM
for n in ("has_deep_gemm",):
    if hasattr(IU, n): setattr(IU, n, lambda: False)
try:
    import vllm.utils.deep_gemm as DG
    DG.is_deep_gemm_supported = lambda: False
except Exception: pass
if hasattr(IU, "has_triton_kernels"): IU.has_triton_kernels = lambda: True   # vendored in vllm.third_party since v0.10.2

import torch
from vllm.model_executor.layers.fused_moe import config as C
import vllm.model_executor.layers.quantization.utils.quant_utils as Q

def make_moe(activation="silu", has_bias=False, swiglu_limit=None):
    Act = getattr(C, "MoEActivation", None)
    try:
        from vllm.model_executor.layers.fused_moe.activation import MoEActivation as Act
    except Exception: pass
    act = getattr(Act, activation.upper()) if Act and not isinstance(Act, type(None)) and hasattr(Act, activation.upper()) else activation
    from vllm.model_executor.layers.fused_moe.config import RoutingMethodType
    pc = C.FusedMoEParallelConfig.make_no_parallel() if hasattr(C.FusedMoEParallelConfig, "make_no_parallel") else None
    want = dict(num_experts=128, experts_per_token=8, hidden_dim=2048, intermediate_size=768,
                num_local_experts=128, num_logical_experts=128, activation=act, device="cuda",
                routing_method=RoutingMethodType.Renormalize, moe_parallel_config=pc,
                in_dtype=torch.bfloat16, router_logits_dtype=torch.bfloat16, moe_backend=FORCE,
                has_bias=has_bias, swiglu_limit=swiglu_limit, intermediate_size_per_partition=768,
                max_num_tokens=8192)
    fields = {f.name: f for f in dataclasses.fields(C.FusedMoEConfig)}
    kw = {k: v for k, v in want.items() if k in fields and fields[k].init}
    missing = [f.name for f in fields.values() if f.init and f.name not in kw and f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING]
    if missing: raise RuntimeError(f"missing FusedMoEConfig fields {missing}")
    return C.FusedMoEConfig(**kw)

def k(name): return getattr(Q, name, None)
SCEN = [
  ("nvfp4", "nvfp4", dict(weight_key=k("kNvfp4Static"), activation_key=k("kNvfp4Dynamic")), {}),
  ("fp8_block", "fp8", dict(weight_key=k("kFp8Static128BlockSym"), activation_key=k("kFp8Dynamic128Sym"), allow_vllm_cutlass=False), {}),
  ("fp8_tensor", "fp8", dict(weight_key=k("kFp8StaticTensorSym"), activation_key=k("kFp8DynamicTensorSym"), allow_vllm_cutlass=False), {}),
  ("ct_fp8_channel", "fp8", dict(weight_key=k("kFp8StaticChannelSym"), activation_key=k("kFp8DynamicTokenSym"), allow_vllm_cutlass=True), {}),
  ("ct_fp8_tensor_static", "fp8", dict(weight_key=k("kFp8StaticTensorSym"), activation_key=k("kFp8StaticTensorSym"), allow_vllm_cutlass=True), {}),
  ("modelopt_fp8", "fp8", dict(weight_key=k("kFp8StaticTensorSym"), activation_key=k("kFp8StaticTensorSym")), {}),
  ("ct_fp8_block", "fp8", dict(weight_key=k("kFp8Static128BlockSym"), activation_key=k("kFp8Dynamic128Sym"), allow_vllm_cutlass=True), {}),
  ("mxfp4_gptoss", "mxfp4", {}, dict(activation="swigluoai", has_bias=True, swiglu_limit=7.0)),
]
SCEN = [x for x in SCEN if not os.environ.get('SCEN_ONLY') or x[0] in os.environ['SCEN_ONLY'].split(',')]
import importlib
LOGS = []
import vllm.logger as VL
_orig = logging.Logger.info
def _cap(self, msg, *a, **kw):
    try: LOGS.append(msg % a if a else str(msg))
    except Exception: LOGS.append(str(msg))
logging.Logger.info = _cap
from vllm.config import VllmConfig, set_current_vllm_config
from types import SimpleNamespace
_vc = VllmConfig()
def set_model(model_type):
    object.__setattr__(_vc, "model_config", SimpleNamespace(quantization_config=None, hf_text_config=SimpleNamespace(model_type=model_type), hf_config=SimpleNamespace(model_type=model_type)))
_ctx = set_current_vllm_config(_vc); _ctx.__enter__()
out = []
for sid, oracle, kwargs, moekw in SCEN:
    rec = {"tag": TAG, "cap": CAP, "fi": FI, "force": FORCE, "scenario": sid}
    set_model('gpt_oss' if oracle == 'mxfp4' else 'qwen3_moe')
    try:
        LOGS.clear()
        try:
            import vllm.logger as _VL
            for _n in ("_print_info_once", "_print_debug_once", "_print_warning_once"):
                if hasattr(getattr(_VL, _n, None), "cache_clear"): getattr(_VL, _n).cache_clear()
        except Exception: pass
        if oracle == "mxfp4":
            import re as _re
            qsrc = open(os.path.join(sys.argv[1], "vllm/model_executor/layers/quantization/mxfp4.py")).read()
            m_ = _re.search(r"self\.mxfp4_backend(?:, self\.experts_cls)? = (select_\w+|get_mxfp4_backend)\(", qsrc)
            fname = m_.group(1)
            rec["selector"] = fname
            if fname == "get_mxfp4_backend":
                O = importlib.import_module("vllm.model_executor.layers.quantization.mxfp4")
                b = O.get_mxfp4_backend(False)
                rec.update(ok=True, backend=getattr(b, "name", str(b)), kernel=None, log=[m for m in LOGS if "backend" in m.lower()][-2:])
                print(json.dumps(rec)); continue
            O = importlib.import_module("vllm.model_executor.layers.fused_moe.oracle.mxfp4")
            fn = getattr(O, fname)
        else:
            O = importlib.import_module(f"vllm.model_executor.layers.fused_moe.oracle.{oracle}")
            fn = getattr(O, f"select_{oracle}_moe_backend")
        sig = inspect.signature(fn).parameters
        moe = make_moe(**moekw)
        if oracle == "mxfp4":
            r = fn(moe)
        else:
            kw = {kk: vv for kk, vv in kwargs.items() if kk in sig}
            first = list(sig)[0]
            r = fn(**{first: moe}, **kw)
        b, cls = r if isinstance(r, tuple) else (r, None)
        rec.update(ok=True, backend=getattr(b, "value", str(b)), kernel=getattr(cls, "__name__", None))
        rec["log"] = [m for m in LOGS if "potential backends" in m][-1:]
    except Exception as e:
        rec.update(ok=False, error=type(e).__name__, msg=str(e)[:600])
    # every backend of this oracle: is it supported here, and why not
    cand = {}
    try:
        Enum = [v for kk, v in vars(O).items() if kk.lower() == f"{oracle}moebackend".lower() or kk.lower()==f"{oracle}_moe_backend".replace("_","")]
        Enum = Enum[0] if Enum else None
        import vllm.model_executor.layers.fused_moe.modular_kernel as mk
        af = mk.FusedMoEActivationFormat.Standard
        wk, ak = kwargs.get("weight_key"), kwargs.get("activation_key")
        if oracle == "mxfp4": wk = k("kMxfp4Static")
        for m in (Enum or []):
            try:
                kc = O.backend_to_kernel_cls(m)
                if not isinstance(kc, (list, tuple)): kc = [kc]
            except Exception as e:
                cand[m.value] = "no kernel class (" + type(e).__name__ + ")"; continue
            res = []
            for kcls in kc:
                a2 = ak
                if oracle == "mxfp4" and hasattr(O, "_backend_activation_key"):
                    try: a2 = O._backend_activation_key(m)
                    except Exception: pass
                try:
                    ok_, why = kcls.is_supported_config(kcls, moe, wk, a2, af)
                except Exception as e:
                    ok_, why = False, "check raised " + type(e).__name__
                res.append("ok" if ok_ else (why or "unsupported"))
                if ok_: break
            cand[m.value] = "ok" if "ok" in res else res[-1] if res else "no kernel class"
    except Exception as e:
        cand["_error"] = type(e).__name__ + ": " + str(e)[:200]
    rec["candidates"] = cand
    mp = {}
    try:
        import typing
        from vllm.config import kernel as KC
        lits = [x for x in typing.get_args(getattr(KC, "MoEBackend")) if x != "auto"]
        fns = [v for kk, v in vars(O).items() if kk.startswith("map_") and kk.endswith("backend") and callable(v)]
        for lit in lits:
            try:
                if fns:
                    r2 = fns[0](lit); mp[lit] = [getattr(x, "value", str(x)) for x in r2] if isinstance(r2, (list, tuple)) else getattr(r2, "value", str(r2))
                elif hasattr(O, "_get_requested_backends"):
                    r2 = O._get_requested_backends(lit, None); mp[lit] = [getattr(x, "value", str(x)) for x in r2] or None
            except Exception:
                pass
    except Exception as e:
        mp["_error"] = type(e).__name__
    rec["map"] = mp
    print(json.dumps(rec))
