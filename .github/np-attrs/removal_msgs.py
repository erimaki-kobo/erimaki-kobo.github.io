"""usage: python3 -I removal_msgs.py <bare clone> > removal_msgs.json
Names that numpy removed without a message in __getattr__ (plain "module 'numpy' has no attribute ..."): the deprecation
warning each one gave in the last minor release that still had it, read from the source (the string passed to
warnings.warn, or for row_stack and the like the whole joined string). (name, tag, file, text the message contains)"""
import ast, json, subprocess, sys
REPO = sys.argv[1]
WANT = [
    ("product", "v1.25.0", "numpy/core/fromnumeric.py", "`product` is deprecated"),
    ("cumproduct", "v1.25.0", "numpy/core/fromnumeric.py", "`cumproduct` is deprecated"),
    ("alltrue", "v1.25.0", "numpy/core/fromnumeric.py", "`alltrue` is deprecated"),
    ("sometrue", "v1.25.0", "numpy/core/fromnumeric.py", "`sometrue` is deprecated"),
    ("msort", "v1.24.0", "numpy/lib/function_base.py", "msort is deprecated"),
    ("in1d", "v2.0.0", "numpy/lib/_arraysetops_impl.py", "`in1d` is deprecated"),
    ("trapz", "v2.0.0", "numpy/lib/_function_base_impl.py", "`trapz` is deprecated"),
    ("row_stack", "v2.0.0", "numpy/lib/_shape_base_impl.py", "`row_stack` alias is deprecated"),
    ("asscalar", "v1.22.0", "numpy/lib/type_check.py", "np.asscalar(a) is deprecated"),
    ("chararray", "v2.0.0", "numpy/__init__.py", "`np.chararray` is deprecated"),
]
out = {}
for name, tag, path, needle in WANT:
    src = subprocess.run(["git", "--git-dir", REPO, "show", "%s:%s" % (tag, path)], capture_output=True, text=True, check=True).stdout
    found = None
    for c in ast.walk(ast.parse(src)):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "warn" and c.args:
            a = c.args[0]
            try:
                s = ast.literal_eval(a)
            except ValueError:
                s = "".join(x.value for x in ast.walk(a) if isinstance(x, ast.Constant) and isinstance(x.value, str))
            if isinstance(s, str) and needle in s:
                found = " ".join(s.split())
                break
    assert found, (name, tag, path)
    out[name] = {"tag": tag, "file": path, "message": found}
    print(name, "|", found, file=sys.stderr)
json.dump(out, sys.stdout, indent=0)
