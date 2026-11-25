"""usage: python3 -I pre22.py <bare clone of scikit-learn> > pre22.json
Removals before the first release installed (0.22; no Python 3.8 wheels before it), read from the source at the tags:
sklearn.cross_validation, grid_search and learning_curve (in 0.19.2, gone in 0.20.0; their module-level DeprecationWarning)
and sklearn.preprocessing.Imputer (in 0.21.3, gone in 0.22; its @deprecated message)."""
import ast, json, subprocess, sys
REPO = sys.argv[1]
show = lambda t, p: subprocess.run(["git", "--git-dir", REPO, "show", "%s:%s" % (t, p)], capture_output=True, text=True)
lit = lambda n: " ".join(ast.literal_eval(n).split())
out = {}
for m in ("cross_validation", "grid_search", "learning_curve"):
    src = show("0.19.2", "sklearn/%s.py" % m)
    assert src.returncode == 0 and show("0.20.0", "sklearn/%s.py" % m).returncode != 0, m
    msg = next(lit(c.value.args[0]) for c in ast.parse(src.stdout).body if isinstance(c, ast.Expr) and isinstance(c.value, ast.Call)
               and getattr(c.value.func, "attr", "") == "warn")
    out["sklearn." + m] = {"obj": "sklearn", "name": m, "removed": "0.20.0", "last": "0.19.2", "module": True, "message": msg, "file": "sklearn/%s.py" % m}
src = ast.parse(show("0.21.3", "sklearn/preprocessing/imputation.py").stdout)
cls = next(c for c in src.body if isinstance(c, ast.ClassDef) and c.name == "Imputer")
msg = lit(next(d for d in cls.decorator_list if isinstance(d, ast.Call)).args[0])
assert "Imputer" in show("0.21.3", "sklearn/preprocessing/__init__.py").stdout and "Imputer" not in show("0.22", "sklearn/preprocessing/__init__.py").stdout
out["sklearn.preprocessing.Imputer"] = {"obj": "sklearn.preprocessing", "name": "Imputer", "removed": "0.22", "last": "0.21.3", "message": msg,
                                        "file": "sklearn/preprocessing/imputation.py"}
json.dump(out, sys.stdout, indent=0)
for k, v in out.items():
    print(k, "|", v["message"][:100], file=sys.stderr)
