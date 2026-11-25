"""usage: <python with one scikit-learn> msg_probe.py want.json > msgs.json
want.json: {object: [names]} removed in the next release read. For each name, the deprecation text in this release:
1. in the file that defines it: the strings in its decorators (@_deprecated(msg), @np.deprecate(message=...)) and in
   warnings.warn calls in its body, with module-level string constants resolved;
2. otherwise any string in the installed scikit-learn that names it before the word "deprecat" (marked [found by text search])."""
import ast, inspect, json, os, re, sys, warnings
warnings.simplefilter("ignore")
WANT = sys.argv[1]
sys.argv = [__file__, "dir"]   # probe.py reads argv; only its object loading runs here
exec(open(__file__.replace("msg_probe.py", "probe.py")).read().split("import sklearn\nif sys.argv")[0])   # O from probe.py


def text(node, consts):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id]
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{...}" for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        a = text(node.left, consts)
        if isinstance(node.op, ast.Mod):
            return a
        b = text(node.right, consts)
        return a + b if a is not None and b is not None else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return text(node.func.value, consts)
    return None


def strings_of(call, consts):
    out = [text(a, consts) for a in call.args] + [text(k.value, consts) for k in call.keywords if k.arg in ("message", "msg")]
    return [" ".join(s.split()) for s in out if s and "deprecat" in s.lower()]


parsed = {}
def tree_of(path):
    if path not in parsed:
        t = ast.parse(open(path, encoding="utf-8").read())
        consts = {}
        for n in t.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                s = text(n.value, consts)
                if s:
                    consts[n.targets[0].id] = s
        parsed[path] = (t, consts)
    return parsed[path]


out = {}
for k, names in json.load(open(WANT)).items():
    for n in names:
        if k not in O:
            continue
        try:
            a = inspect.getattr_static(O[k], n)
        except AttributeError:
            continue
        f = a.fget if isinstance(a, property) else getattr(a, "__func__", a)
        try:
            path = inspect.getsourcefile(inspect.unwrap(f) if callable(f) else f)
        except (TypeError, ValueError):
            path = None
        msgs = []
        if path and path.endswith(".py") and os.path.exists(path):
            t, consts = tree_of(path)
            for d in ast.walk(t):
                if isinstance(d, (ast.FunctionDef, ast.ClassDef)) and d.name == n:
                    for dec in d.decorator_list:
                        if isinstance(dec, ast.Call):
                            msgs += strings_of(dec, consts)
                    for c in ast.walk(d):
                        if isinstance(c, ast.Call) and getattr(c.func, "attr", getattr(c.func, "id", "")) == "warn":
                            msgs += strings_of(c, consts)
                    break
        if msgs:
            out.setdefault(k, {})[n] = msgs[0]
pool = []
root = os.path.dirname(__import__("sklearn").__file__)
for d, _, fs in os.walk(root):
    if "tests" in d.split(os.sep):
        continue
    for fn in fs:
        if fn.endswith(".py"):
            try:
                t, consts = tree_of(os.path.join(d, fn))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for c in ast.walk(t):
                if isinstance(c, (ast.Constant, ast.JoinedStr, ast.BinOp)):
                    s = text(c, consts)
                    if s and "deprecat" in s.lower() and len(s) < 400:
                        pool.append(" ".join(s.split()))
for k, names in json.load(open(WANT)).items():
    for n in names:
        if n in out.get(k, {}):
            continue
        rx = re.compile((r"[.'`]" if len(n) <= 3 else r"(?<![\w])[.'`\"]?") + r"%s\b(?![_(]?\w)" % re.escape(n))
        hits = []
        for t in pool:
            m, d = rx.search(t), t.lower().find("deprecat")
            if m and m.start() < min(d, 70):
                hits.append(t)
        if hits:
            out.setdefault(k, {})[n] = min(hits, key=len) + " [found by text search]"
json.dump(out, sys.stdout, indent=0)
