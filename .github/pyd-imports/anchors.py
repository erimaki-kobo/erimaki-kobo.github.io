"""usage: python3 -I anchors.py <bare clone> out/pydantic.json > anchors.json
The facts the page names, checked by regular-expression search in the files at the release tags (the pydantic wheels
match the tags: compared by blob hash at 1.10.0, 2.0, 2.7.0 and 2.14.4), then compared with the data. Written by hand."""
import json, re, subprocess, sys
REPO, D = sys.argv[1], json.load(open(sys.argv[2]))
R, T = D["releases"], D["ranges"]


def has(m, n, v):
    i = [k for k, r in enumerate(R) if r[0] == v][0]
    ri = D["names"].get(m, {}).get(n)
    if ri is None:
        return False
    r = T[ri]
    return any(a <= i and (not b or i < b) for a, b in zip(r[::2], r[1::2]))


def text(v, path):
    p = subprocess.run(["git", "--git-dir", REPO, "show", "v%s:pydantic/%s" % (v, path)], capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


# (module, name, release, importable?, file, regular expression, found?)
FACTS = [
    ("", "BaseSettings", "1.10.0", True, "env_settings.py", r"^class BaseSettings\b", True),
    ("", "BaseSettings", "2.0", False, "_migration.py", r"`BaseSettings` has been moved to the `pydantic-settings` package", True),
    ("main", "ModelMetaclass", "1.10.0", True, "main.py", r"^class ModelMetaclass\b", True),
    ("main", "ModelMetaclass", "2.0", False, "main.py", r"^class ModelMetaclass\b|^from .* import .*\bModelMetaclass\b", False),
    ("", "field_validator", "1.10.0", False, "functional_validators.py", r"^def field_validator\b", False),
    ("", "field_validator", "2.0", True, "functional_validators.py", r"^def field_validator\b", True),
    ("", "ConfigDict", "1.9.0", False, "config.py", r"^\s*class ConfigDict\b", False),
    ("", "ConfigDict", "1.10.0", True, "config.py", r"^\s*class ConfigDict\b", True),
    ("", "TypeAdapter", "2.0", True, "type_adapter.py", r"^class TypeAdapter\b", True),
    ("utils", "deep_update", "2.0", True, "_migration.py", r"'deep_update'", True),
    ("", "Required", "1.10.0", True, "fields.py", r"^Required\b.*=", True),
    ("", "Required", "2.0", False, "_migration.py", r"'pydantic:Required'", True),
    ("", "with_config", "2.6.0", False, "config.py", r"^def with_config\b", False),
    ("", "with_config", "2.7.0", True, "config.py", r"^def with_config\b", True),
    ("generics", "GenericModel", "2.0", False, "_migration.py", r"'pydantic.generics:GenericModel'", False),
    ("generics", "GenericModel", "2.1.0", True, "_migration.py", r"'pydantic.generics:GenericModel'", True),
    ("v1", "BaseModel", "2.0", True, "v1/__init__.py", r"\bBaseModel\b", True),
]
out = []
for m, n, v, imp, path, rx, found in FACTS:
    t = bool(re.search(rx, text(v, path), re.M))
    d = has(m, n, v)
    out.append({"module": m, "name": n, "release": v, "expected": imp, "text": t == found, "data": d})
    print(m, n, v, imp, t, d, file=sys.stderr)
    assert t == found and d == imp, out[-1]
# pydantic.v1 in 1.x: an alias module from 1.10.15 (patch releases are not in the data, so this is text only)
for v, want in (("1.10.14", False), ("1.10.15", True)):
    t = bool(re.search(r"aliases the pydantic namespace as pydantic.v1", text(v, "v1.py")))
    out.append({"module": "v1", "name": None, "release": v, "expected": want, "text": t == want, "data": None})
    assert t == want, out[-1]
json.dump(out, sys.stdout, indent=0)
