"""usage: <python with one OpenCV package> probe.py > dir.json
Walks the cv2 binding as installed: cv2 and every cv2 submodule reachable from it (cv2.aruco, cv2.dnn, cv2.gapi.wip.draw, ...),
and every class defined by cv2. For each module: its public names (dir) and what each is (m cv2 submodule, x other module,
c class, f callable, k number or string, o other). For each class: its public members, without those of non-cv2 bases.
A class is keyed by its flat name (aruco_Dictionary for both cv2.aruco_Dictionary and cv2.aruco.Dictionary). cv2.cv2, where it
exists, is the native module itself: its names are listed, its classes and submodules are not walked twice. Also the files
in the cv2 package folder, and whether `import cv2.<name>` works for each file-based name (each in its own process)."""
import json, os, subprocess, sys, types, warnings
warnings.simplefilter("ignore")
import cv2

def is_cv_mod(o):
    return isinstance(o, types.ModuleType) and (getattr(o, "__name__", "") == "cv2" or str(getattr(o, "__name__", "")).startswith("cv2."))

def is_cv_cls(o):
    return isinstance(o, type) and str(getattr(o, "__module__", "")).split(".")[0] == "cv2"

def kind(o):
    if is_cv_mod(o):
        return "m"
    if isinstance(o, types.ModuleType):
        return "x"
    if isinstance(o, type):
        return "c" if is_cv_cls(o) else "o"
    if callable(o):
        return "f"
    if isinstance(o, (int, float, str, bytes)):
        return "k"
    return "o"

mods, classes, cpaths, tp, seen = {}, {}, {}, {}, {}
todo = [("cv2", cv2)]
while todo:
    path, m = todo.pop(0)
    if id(m) in seen:
        continue
    seen[id(m)] = path
    names, kinds = [], []
    for n in sorted(dir(m)):
        if n.startswith("_"):
            continue
        try:
            o = getattr(m, n)
        except Exception:
            continue
        k = kind(o)
        names.append(n)
        kinds.append(k)
        if path == "cv2.cv2":   # the native module itself (`import cv2.cv2`, old layout): same objects as cv2, names only
            continue
        if k == "m" and path.count(".") < 5:
            todo.append((path + "." + n, o))
        elif k == "c":
            flat = (path[4:].replace(".", "_") + "_" if path != "cv2" else "") + n
            cpaths.setdefault(flat, []).append(path + "." + n)
            if flat not in classes:
                skip = set()
                for b in o.__mro__[1:]:
                    if not is_cv_cls(b):
                        skip.update(dir(b))
                classes[flat] = sorted(x for x in dir(o) if not x.startswith("_") and x not in skip)
                tp[flat] = "%s.%s" % (o.__module__, getattr(o, "__qualname__", o.__name__))
    mods[path] = {"names": names, "kinds": "".join(kinds)}

pkg = os.path.dirname(cv2.__file__)
files = sorted(os.listdir(pkg))
cands = sorted({f.split(".")[0] for f in files if not f.startswith("_") and (f.endswith(".py") or f.endswith(".so") or os.path.isdir(os.path.join(pkg, f)))}
               | {"cv2", "cv", "data", "version", "typing"})
imports = {}
for n in cands:
    if "-" in n:
        continue
    r = subprocess.run([sys.executable, "-I", "-c", "import cv2.%s" % n], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    imports[n] = {"ok": r.returncode == 0, "error": "" if r.returncode == 0 else r.stderr.decode("utf-8", "replace").strip().splitlines()[-1][:200] if r.stderr.strip() else "exit %d" % r.returncode}

try:
    from importlib import metadata
    dist = sorted("%s==%s" % (d.metadata["Name"], d.version) for d in metadata.distributions() if str(d.metadata["Name"]).lower().startswith("opencv"))
except Exception as e:
    dist = [repr(e)]
json.dump({"cv2": cv2.__version__, "dist": dist, "python": sys.version.split()[0], "numpy": __import__("numpy").__version__, "files": files,
           "imports": imports, "mods": mods, "classes": classes, "class_paths": cpaths, "tp": tp}, sys.stdout, separators=(",", ":"))
