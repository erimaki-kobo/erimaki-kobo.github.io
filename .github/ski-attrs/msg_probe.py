"""usage: <python with one scikit-image> msg_probe.py want.json > msgs.json
want.json: {object: [names]} removed in the next release read. For each name, the deprecation text in this release:
1. in the file that defines it: warnings.warn calls in its body (a DeprecationWarning's text even without the word, local `msg = ...`
   resolved), an @_api.deprecated(since, alternative=...) decorator turned into a sentence (matplotlib's helper), strings in decorators and in
   warnings.warn calls in its body, with module-level string constants resolved;
2. otherwise any string in the installed scikit-image that names it before the word "deprecat" (marked [found by text search])."""
import ast, inspect, json, os, re, sys, warnings
warnings.simplefilter("ignore")
WANT = sys.argv[1]
sys.argv = [__file__, "dir"]   # probe.py reads argv; only its object loading runs here
exec(open(__file__.replace("msg_probe.py", "probe.py")).read().split("import skimage\nif sys.argv")[0])   # O from probe.py


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


def mpl_deprecated(call, consts, n):
    """matplotlib's helpers: _api.deprecated("3.8", alternative="buffer_rgba") and warn_deprecated(...) -> the sentence
    matplotlib/_api/deprecation.py builds from them."""
    if getattr(call.func, "id", getattr(call.func, "attr", "")) not in ("deprecated", "warn_deprecated", "deprecate_privatize_attribute"):
        return None
    kw = {k.arg: text(k.value, consts) for k in call.keywords if k.arg}
    since = text(call.args[0], consts) if call.args else kw.get("since")
    if not since:
        return None
    name, alt, add, rem = kw.get("name") or n, kw.get("alternative"), kw.get("addendum"), kw.get("removal")
    if kw.get("message"):
        m = kw["message"]
        for a, b in (("%(name)s", name), ("%(since)s", since), ("%(removal)s", rem or "two minor releases later"),
                     ("%(alternative)s", alt or ""), ("%(addendum)s", add or ""), ("%(obj_type)s", kw.get("obj_type") or "")):
            m = m.replace(a, b)
        return " ".join(m.split())
    m = "%s was deprecated in Matplotlib %s." % (name, since)
    if alt:
        m += " Use %s instead." % alt
    if add:
        m += " " + add
    return " ".join(m.replace("``", "").split())


def strings_of(call, consts, n=""):
    p = None   # (matplotlib's helper is not used by scikit-image)
    if p:
        return [p]
    out = [text(a, consts) for a in call.args] + [text(k.value, consts) for k in call.keywords if k.arg in ("message", "msg")]
    cat = [a for a in list(call.args[1:2]) + [k.value for k in call.keywords if k.arg == "category"]]
    dw = any(getattr(a, "id", getattr(a, "attr", "")) in ("DeprecationWarning", "FutureWarning", "PendingDeprecationWarning") for a in cat)
    return [" ".join(s.split()) for s in out if s and (dw or "deprecat" in s.lower())]   # warn("... Use X instead.", DeprecationWarning)


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
            try:   # scikit-image 0.20+ loads its functions lazily through the module's __getattr__
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    a = getattr(O[k], n)
            except Exception:
                continue
        f = a.fget if isinstance(a, property) else getattr(a, "__func__", a)
        try:
            path = inspect.getsourcefile(inspect.unwrap(f) if callable(f) else f)
        except (TypeError, ValueError):
            path = None
        paths = [path]
        try:   # a property made by a helper (deprecate_privatize_attribute) or a plain value: also read the file of the module or class that holds it
            paths.append(inspect.getsourcefile(O[k]))
        except (TypeError, ValueError):
            pass
        msgs = []
        doc = getattr(f, "__doc__", None) if callable(f) else None
        doc = doc if isinstance(doc, str) else ""
        if "**Deprecated" in doc:   # skimage's @deprecated / @deprecate_func put their message at the top of the docstring
            para = doc[doc.index("**Deprecated"):].split("\n\n")[0]
            para = " ".join(para.replace("**Deprecated function**.", "Deprecated function.").replace("**Deprecated:**", "").replace("``", "`").split())
            if para:
                msgs.append(para)
        for path in dict.fromkeys(p for p in paths if p):
            if msgs or not (path.endswith(".py") and os.path.exists(path)):
                continue
            t, consts = tree_of(path)
            for d in ast.walk(t):
                if isinstance(d, (ast.FunctionDef, ast.ClassDef)) and d.name == n:
                    for dec in d.decorator_list:
                        if isinstance(dec, ast.Call):
                            msgs += strings_of(dec, consts, n)
                    local = dict(consts)   # msg = "..."; warnings.warn(msg, DeprecationWarning)
                    for c in (ast.walk(d) if isinstance(d, ast.FunctionDef) else ()):
                        if isinstance(c, ast.Assign) and len(c.targets) == 1 and isinstance(c.targets[0], ast.Name) and text(c.value, local):
                            local[c.targets[0].id] = text(c.value, local)
                    for c in (ast.walk(d) if isinstance(d, ast.FunctionDef) else ()):   # a class body's warnings are about its methods
                        if isinstance(c, ast.Call) and getattr(c.func, "attr", getattr(c.func, "id", "")) in ("warn", "warn_deprecated", "warn_external"):
                            msgs += strings_of(c, local, n)
                    break
            if not msgs:   # get_cmap = _api.deprecated("3.7", ...)(_get_cmap); dist = _api.deprecate_privatize_attribute("3.6")
                for d in ast.walk(t):
                    if isinstance(d, ast.Assign) and isinstance(d.value, ast.Call) and any(
                            getattr(x, "id", getattr(x, "attr", None)) == n for x in d.targets):
                        for c in ast.walk(d.value):
                            if isinstance(c, ast.Call):
                                msgs += strings_of(c, consts, n)
                        if msgs:
                            break
        if msgs:
            out.setdefault(k, {})[n] = msgs[0]
pool = []
root = os.path.dirname(__import__("skimage").__file__)
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
