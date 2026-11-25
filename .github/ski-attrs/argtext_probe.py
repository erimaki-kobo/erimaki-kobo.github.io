"""usage: <python with one scikit-image> argtext_probe.py want_args.json > argtext.json
want_args.json: [[module, function, parameter], ...]. For each, scikit-image's own text about that argument in this release:
the message of a warn(...) call or of a raise in the function's source that names the parameter."""
import ast, importlib, inspect, json, os, re, sys, textwrap, warnings
REAL, sys.stdout = sys.stdout, open(os.devnull, "w")
warnings.simplefilter("ignore")


def text_of(node):
    parts = []
    for x in ast.walk(node):
        if isinstance(x, ast.Constant) and isinstance(x.value, str):
            parts.append((getattr(x, "lineno", 0), getattr(x, "col_offset", 0), x.value))
    return " ".join("".join(s for _, _, s in sorted(parts)).split())


out = {}
for m, n, p in json.load(open(sys.argv[1])):
    try:
        f = getattr(importlib.import_module(m), n)
        f = inspect.unwrap(f.__init__ if inspect.isclass(f) else f)
        tree = ast.parse(textwrap.dedent(inspect.getsource(f)))
    except Exception:
        continue
    msgs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) in ("warn", "warn_explicit") and node.args:
            s = text_of(node.args[0])
        elif isinstance(node, ast.Raise) and node.exc is not None:
            s = text_of(node.exc)
        else:
            continue
        if s and re.search(r"(?<![\w.])%s(?![\w.])" % re.escape(p), s) and s not in msgs:
            msgs.append(s)
    if msgs:
        out["%s|%s|%s" % (m, n, p)] = msgs
json.dump(out, REAL)
