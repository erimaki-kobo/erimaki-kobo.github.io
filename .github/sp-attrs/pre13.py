"""usage: python3 -I pre13.py <bare clone of scipy/scipy> > pre13.json
Names scipy.misc had in 1.2 and not in 1.3.0 (before the first release installed, 1.3.3), read from the source at the tags:
the image functions of scipy/misc/pilutil.py (they needed Pillow) and the scipy.special names re-exported with a
deprecation. Their deprecation text is the message= of their @numpy.deprecate decorator, or the _msg template of
scipy/misc/__init__.py filled in."""
import ast, json, subprocess, sys
REPO = sys.argv[1]
show = lambda t, p: subprocess.run(["git", "--git-dir", REPO, "show", "%s:%s" % (t, p)], capture_output=True, text=True)
pil = ast.parse(show("v1.2.0", "scipy/misc/pilutil.py").stdout)
out = {}
for d in pil.body:
    if isinstance(d, ast.FunctionDef):
        for dec in d.decorator_list:
            if isinstance(dec, ast.Call):
                for k in dec.keywords:
                    if k.arg == "message":
                        out[d.name] = {"message": " ".join(ast.literal_eval(k.value).split()), "file": "scipy/misc/pilutil.py"}
init12, init13 = show("v1.2.0", "scipy/misc/__init__.py").stdout, show("v1.3.0", "scipy/misc/__init__.py").stdout
tmpl = "Importing `%(name)s` from scipy.misc is deprecated in scipy 1.0.0. Use `scipy.special.%(name)s` instead."
assert '"Importing `%(name)s` from scipy.misc is deprecated in scipy 1.0.0. Use "' in init12 and '"`scipy.special.%(name)s` instead.")' in init12
for n in ("comb", "factorial", "factorial2", "factorialk", "logsumexp"):
    assert "%s = np.deprecate(" % n in init12 and n not in init13, n
    out[n] = {"message": tmpl % {"name": n}, "file": "scipy/misc/__init__.py"}
assert show("v1.3.0", "scipy/misc/pilutil.py").returncode != 0 and "pilutil" not in init13
assert sorted(out) == sorted(["bytescale", "imread", "imsave", "fromimage", "toimage", "imrotate", "imshow", "imresize", "imfilter",
                              "comb", "factorial", "factorial2", "factorialk", "logsumexp"]), sorted(out)
json.dump(out, sys.stdout, indent=0)
print(len(out), "names", file=sys.stderr)
