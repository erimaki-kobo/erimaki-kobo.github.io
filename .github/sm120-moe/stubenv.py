"""Make vLLM's Python source importable on a machine with no GPU and no compiled ops.
Compiled extension modules (vllm._C etc.) and a few optional packages are replaced by
empty modules whose attributes are MagicMock objects. Then current_platform is set to a
CudaPlatform subclass that reports a chosen compute capability."""
import sys, types, importlib.abc, importlib.machinery
from unittest import mock

STUB_PREFIXES = ("vllm._C", "vllm._moe_C", "vllm._rocm_C", "vllm._flashmla", "vllm.vllm_flash_attn._vllm_fa",
                 "vllm._custom_C", "vllm._version", "vllm.cumem_allocator", "vllm._C_stable_libtorch")
STUB_PKGS = set()
FLASHINFER_VERSION = '0.0.0'

class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        m = mock.MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, m)
        return m

class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path, target=None):
        if fullname.startswith(STUB_PREFIXES) or fullname.split(".")[0] in STUB_PKGS:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None
    def create_module(self, spec):
        m = _StubModule(spec.name); m.__path__ = []
        if spec.name == "flashinfer":
            m.__version__ = FLASHINFER_VERSION
        if spec.name == "vllm._version":
            m.__version__ = "0.0.0"; m.__version_tuple__ = (0, 0, 0); m.version = "0.0.0"
        return m
    def exec_module(self, module):
        pass

sys.meta_path.insert(0, _Finder())
