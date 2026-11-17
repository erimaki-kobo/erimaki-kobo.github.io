#!/usr/bin/env python3
"""HF class name -> GGUF architecture string, from llama.cpp's converter at one build.

Usage: python3 -I gguf_map.py <dir with conversion/ and gguf-py/gguf/constants.py>  (prints JSON)
Reads `@ModelBase.register("HfClass", ...)` on each converter class and that class's `model_arch`
(inherited from a base class when it does not set one), and MODEL_ARCH_NAMES for the string.
Vision projector classes (model_arch MMPROJ) are left out: their text half is registered separately.
"""
import ast, json, sys
from pathlib import Path


def gguf_map(root):
    root = Path(root)
    names = {}
    for n in ast.walk(ast.parse((root / "gguf-py/gguf/constants.py").read_text())):
        tgt = n.target if isinstance(n, ast.AnnAssign) else n.targets[0] if isinstance(n, ast.Assign) else None
        if isinstance(tgt, ast.Name) and tgt.id == "MODEL_ARCH_NAMES" and isinstance(n.value, ast.Dict):
            for k, v in zip(n.value.keys, n.value.values):
                names[k.attr] = v.value
    assert len(names) > 50, len(names)
    classes = {}          # (module, class) -> (bases, arch enum or None, registered names)
    files = sorted((root / "conversion").glob("*.py")) + [root / "convert_hf_to_gguf.py"]
    for f in files:
        if not f.exists():
            continue
        for n in ast.parse(f.read_text()).body:
            if not isinstance(n, ast.ClassDef):
                continue
            arch = None
            for b in n.body:
                tgt = b.targets[0] if isinstance(b, ast.Assign) else b.target if isinstance(b, ast.AnnAssign) else None
                val = getattr(b, "value", None)
                if isinstance(tgt, ast.Name) and tgt.id == "model_arch" and isinstance(val, ast.Attribute):
                    arch = val.attr
            reg = []
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "register":
                    reg += [a.value for a in d.args if isinstance(a, ast.Constant)]
            bases = [b.id if isinstance(b, ast.Name) else b.attr for b in n.bases if isinstance(b, (ast.Name, ast.Attribute))]
            classes[(f.stem, n.name)] = (bases, arch, reg)

    def resolve(mod, cls, seen=()):
        key = (mod, cls) if (mod, cls) in classes else next((k for k in classes if k[1] == cls), None)
        if key is None or key in seen:
            return None
        bases, arch, _ = classes[key]
        if arch:
            return arch
        for b in bases:
            r = resolve(key[0], b, seen + (key,))
            if r:
                return r
        return None

    out = {}
    for (mod, cls), (_, _, reg) in classes.items():
        if not reg:
            continue
        arch = resolve(mod, cls)
        if arch is None or arch == "MMPROJ":
            continue
        for hf in reg:
            out.setdefault(hf, names[arch])
    return out


if __name__ == "__main__":
    print(json.dumps(gguf_map(sys.argv[1]), indent=0, sort_keys=True))
