"""usage: <python with one pandas> msg_probe.py want.json > msgs.json
want.json: {object: [names]} removed in the next release read. For each name, the deprecation warning its own code gives
in this release: the strings passed to warnings.warn in the function (or property getter) body, read with inspect and ast
from the installed pandas. f-string parts are kept as {expression}."""
import ast, inspect, json, sys, textwrap, warnings
warnings.simplefilter("ignore")
sys.argv[0] = __file__
exec(open(__file__.replace("msg_probe.py", "probe.py")).read().split("O = objects()")[0])   # objects() from probe.py
O = objects()


def text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{%s}" % ast.unparse(v.value) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = text(node.left), text(node.right)
        return a + b if a is not None and b is not None else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return text(node.func.value)
    return None


out = {}
for k, names in json.load(open(sys.argv[1])).items():
    for n in names:
        try:
            a = inspect.getattr_static(O[k], n)
        except AttributeError:
            continue
        f = a.fget if isinstance(a, property) else getattr(a, "__func__", a)
        f = inspect.unwrap(f) if callable(f) else f
        try:
            src = textwrap.dedent(inspect.getsource(f))
        except (TypeError, OSError):
            continue
        msgs = []
        for c in ast.walk(ast.parse(src)):
            if isinstance(c, ast.Call) and isinstance(c.func, (ast.Attribute, ast.Name)) and getattr(c.func, "attr", getattr(c.func, "id", "")) == "warn" and c.args:
                t = text(c.args[0])
                if t:
                    msgs.append(" ".join(t.split()))
        if msgs:
            out.setdefault(k, {})[n] = msgs[0]
# fallback: a warnings.warn string anywhere in the installed pandas that names the attribute and says deprecated
import os, re
pool = []
root = os.path.dirname(__import__("pandas").__file__)
for d, _, fs in os.walk(root):
    if "tests" in d.split(os.sep):
        continue
    for fn in fs:
        if fn.endswith(".py"):
            try:
                tree = ast.parse(open(os.path.join(d, fn), encoding="utf-8").read())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for c in ast.walk(tree):
                if isinstance(c, ast.Call) and getattr(c.func, "attr", getattr(c.func, "id", "")) == "warn" and c.args:
                    t = text(c.args[0])
                    if t and "deprecat" in t.lower():
                        pool.append((os.path.relpath(os.path.join(d, fn), root), " ".join(t.split())))
for k, names in json.load(open(sys.argv[1])).items():
    for n in names:
        if n in out.get(k, {}):
            continue
        # the name must be named before the word "deprecat", near the start (short names only after . ' or `)
        rx = re.compile((r"[.'`]" if len(n) <= 3 else r"(?<![\w])[.'`\"]?") + r"%s\b(?![_(]?\w)" % re.escape(n))
        hits = []
        for f, t in pool:
            m, d = rx.search(t), t.lower().find("deprecat")
            if m and m.start() < min(d, 70):
                hits.append(t)
        if hits:
            out.setdefault(k, {})[n] = min(hits, key=len) + " [found by text search]"
json.dump(out, sys.stdout, indent=0)
