"""usage: python3 -I fb_fix.py <bare clone> hist.json > hist_fixed.json
torchvision 0.26+ binds some names in torchvision.io only through `from pytorch.vision.fb... import`, a Meta-internal
package that is not on PyPI. In the published wheels those imports fail: inside try/except ImportError the names are
not bound; at module level (io/video.py from 0.28.0) the whole module raises on import. Remove them from the history."""
import ast, json, subprocess, sys
REPO, H = sys.argv[1], json.load(open(sys.argv[2]))
FB = "pytorch.vision.fb"
log = []
for tag, mods in H["mods"].items():
    files = subprocess.run(["git", "--git-dir", REPO, "grep", "-l", FB, tag, "--", "torchvision"], capture_output=True, text=True).stdout.split()
    for f in files:
        path = f.split(":", 1)[1]
        mod = path[len("torchvision/"):-3].replace("/", ".")
        mod = mod[:-len(".__init__")] if mod.endswith(".__init__") else ("" if mod == "__init__" else mod)
        tree = ast.parse(subprocess.run(["git", "--git-dir", REPO, "show", f], capture_output=True, text=True, check=True).stdout)
        fatal = any(isinstance(s, ast.ImportFrom) and (s.module or "").startswith(FB) for s in tree.body)
        if fatal:
            assert mod in mods, (tag, mod)
            del mods[mod]
            parent, _, leaf = mod.rpartition(".")
            if leaf in mods.get(parent, []):
                mods[parent].remove(leaf)
            log.append((tag, mod, "module removed"))
            continue
        fbn, other = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node in tree.body:
                other.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = {a.asname or a.name.split(".")[0] for a in node.names}
                (fbn if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(FB) else other).update(names)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                other.add(node.id)
        gone = sorted(n for n in fbn - other if n in mods.get(mod, []))
        mods[mod] = [n for n in mods[mod] if n not in gone]
        log.append((tag, mod, gone))
for l in log:
    print(*l, file=sys.stderr)
json.dump(H, sys.stdout)
