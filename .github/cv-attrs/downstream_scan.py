"""usage: python3 -I downstream_scan.py opencv_names.json meta_dir src_dir > downstream.json
Reads (ast, nothing is run) every .py file of each unpacked package, outside tests/docs/examples folders. A use of cv2 is an
attribute chain that starts at a name bound to cv2 (import cv2, import cv2 as cv, from cv2 import aruco, import cv2.aruco as
aruco), or `from cv2[.x] import name`. A use is kept when some OpenCV release in the page's data has the name and
opencv-python LATEST does not. status: c5 = left opencv-python in 5.x, opencv-contrib-python LATEST has it; x5 = gone from
both in 5.x; old = already gone in the newest 4.x; contrib = only ever in opencv-contrib-python (LATEST has it).
guarded = the use sits in a try whose handlers catch AttributeError/Exception (or everything), or under an if that calls hasattr."""
import ast, json, os, re, sys
D = json.load(open(sys.argv[1]))
META, SRC = sys.argv[2], sys.argv[3]
VS = [v for v, _ in D["vs"]]
N = {}
for o, groups in D["n"].items():
    N[o] = {}
    for a, b, names in groups:
        for n in names.split(" "):
            N[o][n] = (D["pat"][a], D["pat"][b])
LATEST, I4 = VS[-1], max(i for i, v in enumerate(VS) if v.startswith("4."))
SKIP_DIRS = {"tests", "test", "testing", "docs", "doc", "examples", "example", "demo", "demos", "benchmarks", "benchmark", "scripts", "tools", "notebooks"}


def last(s):
    t = s.replace("-", "")
    return t[-1] if t else None


def removed(s):
    i = s.rindex("o")
    return VS[next(j for j in range(i + 1, len(s)) if s[j] == "g")]


def status(obj, n):
    if obj not in N or n not in N[obj]:
        return None
    pm, pc = N[obj][n]
    if last(pm) == "o":
        return None
    if last(pc) == "o":
        return ("c5", removed(pm)) if "o" in pm and pm[I4] == "o" else ("contrib", None) if "o" not in pm else ("oldmain", removed(pm))
    if "o" not in pc:
        return None
    return ("x5", removed(pc)) if pc[I4] == "o" else ("old", removed(pc))


class V(ast.NodeVisitor):
    def __init__(self):
        self.bind, self.uses, self.stack, self.imports_cv2 = {}, [], [], False

    def generic_visit(self, node):
        self.stack.append(node)
        super().generic_visit(node)
        self.stack.pop()

    def guarded(self, node):
        child = node
        for anc in reversed(self.stack):
            if isinstance(anc, ast.Try) and any(child is x for x in anc.body):
                for h in anc.handlers:
                    names = [] if h.type is None else [getattr(t, "id", getattr(t, "attr", "")) for t in (h.type.elts if isinstance(h.type, ast.Tuple) else [h.type])]
                    if h.type is None or set(names) & {"AttributeError", "Exception", "BaseException"}:
                        return True
            if isinstance(anc, ast.If) and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "hasattr" for c in ast.walk(anc.test)):
                return True
            child = anc
        return False

    def visit_Import(self, node):
        for a in node.names:
            if a.name == "cv2" or a.name.startswith("cv2."):
                self.imports_cv2 = True
                if a.asname:
                    self.bind[a.asname] = a.name.replace("cv2.cv2", "cv2")
                else:
                    self.bind["cv2"] = "cv2"

    def visit_ImportFrom(self, node):
        m = node.module or ""
        if node.level == 0 and (m == "cv2" or m.startswith("cv2.")):
            self.imports_cv2 = True
            m = m.replace("cv2.cv2", "cv2")
            for a in node.names:
                full = m + "." + a.name
                if full in N:
                    self.bind[a.asname or a.name] = full
                elif a.name != "*":
                    self.uses.append((m, a.name, node.lineno, self.guarded(node)))

    def visit_Attribute(self, node):
        if self.stack and isinstance(self.stack[-1], ast.Attribute) and self.stack[-1].value is node:
            return self.generic_visit(node)
        parts, cur = [], node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name) and cur.id in self.bind:
            path = self.bind[cur.id].split(".") + parts[::-1]
            k = 1
            while k < len(path) - 1 and ".".join(path[:k + 1]) in N:
                k += 1
            obj, rest = ".".join(path[:k]), path[k:]
            if rest:
                g = self.guarded(node)
                self.uses.append((obj, rest[0], node.lineno, g))
                flat = "cv2:" + (obj[4:].replace(".", "_") + "_" if obj != "cv2" else "") + rest[0]
                if len(rest) > 1 and flat in N:
                    self.uses.append((flat, rest[1], node.lineno, g))
        self.generic_visit(node)


out = {}
for pkg in sorted(os.listdir(SRC)):
    meta = json.load(open(os.path.join(META, pkg + ".json")))
    info = meta["info"]
    req = [r for r in (info.get("requires_dist") or []) if re.match(r"opencv[-_]", r, re.I)]
    n_py = n_cv = 0
    uses = {}
    for root, dirs, files in os.walk(os.path.join(SRC, pkg)):
        rel = os.path.relpath(root, os.path.join(SRC, pkg)).split(os.sep)
        if set(x.lower() for x in rel[1:]) & SKIP_DIRS or (len(rel) > 1 and rel[1].lower() in SKIP_DIRS):
            continue
        for f in files:
            if not f.endswith(".py") or f.startswith("test_") or f in ("setup.py", "conftest.py"):
                continue
            p = os.path.join(root, f)
            n_py += 1
            try:
                tree = ast.parse(open(p, encoding="utf-8", errors="replace").read())
            except (SyntaxError, ValueError, RecursionError):
                continue
            # two passes: imports anywhere in the file bind first, then the chains
            v = V()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    v.visit_Import(node)
                elif isinstance(node, ast.ImportFrom):
                    v.stack = []
                    v.visit_ImportFrom(node)
            if not v.imports_cv2:
                continue
            n_cv += 1
            v.uses = [u for u in v.uses]   # names imported with from-import (guard unknown at this pass)
            v.visit(tree)
            relp = "/".join(os.path.relpath(p, os.path.join(SRC, pkg)).split(os.sep)[1:]) or f
            for obj, n, line, g in v.uses:
                st = status(obj, n)
                if st:
                    key = "%s|%s" % (obj, n)
                    u = uses.setdefault(key, {"status": st[0], "removed": st[1], "first": "%s:%d" % (relp, line), "count": 0, "guarded": 0, "files": set()})
                    u["count"] += 1
                    u["guarded"] += int(bool(g))
                    u["files"].add(relp)
    for u in uses.values():
        u["files"] = len(u["files"])
    dates = sorted(f["upload_time"][:10] for f in meta["urls"])
    out[info["name"]] = {"version": info["version"], "date": dates[0] if dates else None, "requires": req, "py": n_py, "cv2_files": n_cv, "uses": uses}
json.dump({"latest": LATEST, "packages": out}, sys.stdout, indent=0, sort_keys=True)
