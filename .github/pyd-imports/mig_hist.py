"""usage: python3 -I mig_hist.py <bare clone> hist.json > hist_mig.json   (also writes mig.json)
pydantic 2.x modules end with `__getattr__ = getattr_migration(__name__)` (pydantic/_migration.py). For names in
MOVED_IN_V2, DEPRECATED_MOVED_IN_V2 and REDIRECT_TO_V1 that function returns the object from its new place (with a
warning), so `from pydantic.utils import deep_update` still works: add those names to the module where the module exists
and installs the hook. BaseSettings on pydantic and the names in REMOVED_IN_V2 raise PydanticImportError: they are left
out and written, with the message, to stderr as JSON (per tag) for the page's hints."""
import ast, json, subprocess, sys
REPO, H = sys.argv[1], json.load(open(sys.argv[2]))
TABLES = ("MOVED_IN_V2", "DEPRECATED_MOVED_IN_V2", "REDIRECT_TO_V1", "REMOVED_IN_V2")
show = lambda t, p: subprocess.run(["git", "--git-dir", REPO, "show", "%s:%s" % (t, p)], capture_output=True, text=True)
out, n_added = {}, 0
for tag, mods in H["mods"].items():
    r = show(tag, "pydantic/_migration.py")
    if r.returncode:
        continue
    tree = ast.parse(r.stdout)
    env = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", None) in TABLES:
            env[node.targets[0].id] = eval(compile(ast.Expression(node.value), "_migration", "eval"), {"__builtins__": {}}, dict(env))
    assert {"MOVED_IN_V2", "DEPRECATED_MOVED_IN_V2", "REMOVED_IN_V2"} <= set(env), (tag, sorted(env))   # REDIRECT_TO_V1 came later
    env.setdefault("REDIRECT_TO_V1", {})
    assert "'pydantic:BaseSettings'" in r.stdout and "pydantic-settings" in r.stdout, tag
    hooked = {}
    for m in mods:
        p = "pydantic/" + (m.replace(".", "/") + ("/__init__.py" if m in H["pkgs"][tag] else ".py") if m else "__init__.py")
        src = show(tag, p).stdout
        hooked[m] = "getattr_migration(__name__)" in src
    rec = {"moved": {}, "removed": sorted(env["REMOVED_IN_V2"]) + ["pydantic:BaseSettings"]}
    for t in TABLES[:3]:
        for old, new in env[t].items():
            mod, name = old.split(":")
            m = mod[len("pydantic."):] if mod != "pydantic" else ""
            rec["moved"][old] = [new, t]
            if hooked.get(m) and name not in mods[m]:
                mods[m].append(name)
                n_added += 1
    out[tag] = rec
print("names added through getattr_migration:", n_added, "in", len(out), "releases", file=sys.stderr)
json.dump(H, sys.stdout)
open("mig.json", "w").write(json.dumps(out))
