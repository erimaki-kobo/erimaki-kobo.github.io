"""Import vLLM's tool/reasoning parsers from a source tree without torch or the compiled extension.
Any module that cannot be found and is not part of the tree (torch, triton, vllm._C, ...) is replaced by a stub whose
attributes are themselves stubs, so module-level `import torch` and type annotations do not fail. The parsers' own code
(regex, json, partial_json_parser, pydantic models) runs for real. Records every stubbed module name."""
import importlib.abc, importlib.machinery, sys, types

STUBBED = []
STUB_VLLM = ["vllm._C", "vllm._moe_C", "vllm._custom_ops", "vllm.vllm_flash_attn", "vllm.utils.torch_utils", "vllm.config", "vllm.platforms",
             "vllm.model_executor", "vllm.v1", "vllm.distributed", "vllm.multimodal", "vllm.lora", "vllm.engine", "vllm.inputs", "vllm.compilation"]


class _Any:
    """A stand-in for anything from a stubbed module: callable, subscriptable, usable as a base class (drops out)."""
    def __init__(self, n="stub"):
        self._n = n
    def __getattr__(self, n):
        if n.startswith("__") and n.endswith("__"):
            raise AttributeError(n)
        return _Any(n)
    def __call__(self, *a, **k):
        if len(a) == 1 and callable(a[0]) and not k:   # used as a decorator
            return a[0]
        return _Any(self._n + "()")
    def __getitem__(self, k):
        return self
    def __or__(self, o):
        return self
    def __ror__(self, o):
        return self
    def __iter__(self):
        return iter(())
    def __bool__(self):
        return False
    def __mro_entries__(self, bases):
        return ()
    def __repr__(self):
        return "<stub %s>" % self._n
    def __get_pydantic_core_schema__(self, source, handler):
        from pydantic_core import core_schema
        return core_schema.any_schema()
    def __eq__(self, o):
        return self is o
    def __hash__(self):
        return id(self)


class StubModule(types.ModuleType):
    def __getattr__(self, n):
        if n in ("__path__", "__file__", "__spec__", "__loader__", "__all__"):
            raise AttributeError(n)
        v = _Any(n)
        setattr(self, n, v)
        return v


class Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, roots):
        self.roots = roots
    def find_spec(self, name, path, target=None):
        top = name.split(".")[0]
        if name.startswith("vllm"):
            if any(name == p or name.startswith(p + ".") for p in STUB_VLLM):
                return importlib.machinery.ModuleSpec(name, self, is_package=True)
            return None
        if top in ("vllm",) or top in self.roots:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None
    def create_module(self, spec):
        STUBBED.append(spec.name)
        m = StubModule(spec.name)
        m.__path__ = []
        if spec.name == "torch":   # torch.iinfo(torch.long) bounds request fields in older protocol.py
            m.iinfo = lambda t: types.SimpleNamespace(min=-(1 << 63), max=(1 << 63) - 1)
        return m
    def exec_module(self, module):
        pass


def _fake_versions():
    import importlib.metadata as md
    real = md.version
    def version(name):
        if name.split("[")[0].lower().replace("_", "-") in ("torch", "triton", "xgrammar", "llguidance", "flashinfer-python", "mistral-common", "openai-harmony", "oss-harmony"):
            return {"torch": "2.10.0"}.get(name, "0.0.0")
        return real(name)
    md.version = version


def install(tree, force_stub=("torch", "triton", "xgrammar", "llguidance", "outlines_core", "lm_format_enforcer", "mistral_common", "oss_harmony", "openai_harmony", "flashinfer", "cv2", "PIL", "anthropic", "mcp", "gguf")):
    for m in list(sys.modules):
        if m == "vllm" or m.startswith("vllm."):
            del sys.modules[m]
    sys.path.insert(0, tree)
    _fake_versions()
    import pydantic   # older releases put msgspec structs (SamplingParams) in plain pydantic models; the real install accepts them
    pydantic.BaseModel.model_config["arbitrary_types_allowed"] = True
    sys.meta_path.insert(0, Finder(set(force_stub)))
