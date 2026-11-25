"""usage: <python with one moviepy> probe.py workdir > dir.json
What one installed MoviePy has, the way a script meets it:
- `import moviepy.editor` first (1.x users write `from moviepy.editor import *`, and that import attaches the effect methods
  resize, crop, fadein, ... to the clip classes);
- every module file of the package (pkgutil), and whether importing it works;
- for each importable module: its public names that MoviePy defines (c class, f function, m moviepy module, k UPPERCASE value);
- for each class MoviePy defines: its public members (without those of object), and the parameters of each method;
- the parameters of each function;
- real objects (ColorClip, ImageClip, AudioClip, CompositeVideoClip, a concatenation, a VideoFileClip and AudioFileClip of a
  one-second file written here with the bundled ffmpeg, TextClip where it can be built): their public attributes."""
import importlib, inspect, json, os, pkgutil, sys, types, warnings
warnings.simplefilter("ignore")
os.chdir(sys.argv[1])
REAL_STDOUT, sys.stdout = sys.stdout, open(os.devnull, "w")   # some modules print when imported
import moviepy
out = {"python": sys.version.split()[0], "version_attr": getattr(moviepy, "__version__", None)}
try:
    from importlib import metadata
    out["dist"] = metadata.version("moviepy")
    out["deps"] = {n: metadata.version(n) for n in ("numpy", "pillow", "imageio", "imageio-ffmpeg", "decorator", "proglog")}
except Exception as e:
    out["dist"] = repr(e)
try:
    import moviepy.editor
    out["editor"] = "ok"
except Exception as e:
    out["editor"] = "%s: %s" % (type(e).__name__, e)

mods, imp = {}, {}
names = sorted({"moviepy"} | {m.name for m in pkgutil.walk_packages(moviepy.__path__, "moviepy.", onerror=lambda n: None)})
classes = {}
def kind(o):
    if isinstance(o, types.ModuleType):
        return "m" if o.__name__.split(".")[0] == "moviepy" else "x"
    if isinstance(o, type):
        return "c" if str(getattr(o, "__module__", "")).split(".")[0] == "moviepy" else "x"
    if callable(o):
        return "f" if str(getattr(o, "__module__", "")).split(".")[0] == "moviepy" else "x"
    return "k"
def params(f):
    try:
        return [p.name for p in inspect.signature(f).parameters.values() if p.name not in ("self", "cls")]
    except (TypeError, ValueError):
        return None
fparams = {}
for name in names:
    try:
        m = importlib.import_module(name)
        imp[name] = "ok"
    except BaseException as e:
        imp[name] = "%s: %s" % (type(e).__name__, str(e)[:120])
        continue
    ns, ks = [], []
    for n in sorted(dir(m)):
        if n.startswith("_"):
            continue
        try:
            o = getattr(m, n)
        except Exception:
            continue
        k = kind(o)
        if k == "x" or (k == "k" and not n.isupper()):
            continue
        ns.append(n)
        ks.append(k)
        if k == "c":
            classes.setdefault(n, o)
        elif k == "f":
            fparams.setdefault(name, {})[n] = params(o)
    mods[name] = {"names": ns, "kinds": "".join(ks)}
out["imports"], out["mods"], out["fparams"] = imp, mods, fparams
base = set(dir(object))
out["classes"] = {n: sorted(x for x in dir(c) if not x.startswith("_") and x not in base) for n, c in classes.items()}
out["class_module"] = {n: c.__module__ for n, c in classes.items()}
out["init"] = {n: params(c.__init__) for n, c in classes.items()}
out["mparams"] = {n: {x: params(getattr(c, x)) for x in out["classes"][n] if callable(getattr(c, x, None))} for n, c in classes.items()}

# real objects
import numpy as np
inst, errs = {}, {}
def pub(o):
    return sorted(x for x in dir(o) if not x.startswith("_") and x not in base)
def first(*fs):
    errs_ = []
    for f in fs:
        try:
            return f()
        except Exception as e:
            errs_.append("%s: %s" % (type(e).__name__, str(e)[:160]))
    raise RuntimeError(" | then: ".join(errs_))
def build(label, *fs):
    try:
        o = first(*fs)
        inst[label] = pub(o)
        return o
    except Exception as e:
        errs[label] = "%s: %s" % (type(e).__name__, str(e)[:160])
        return None
C = classes
color = build("ColorClip", lambda: C["ColorClip"]((64, 48), color=(255, 0, 0), duration=1))
build("ImageClip", lambda: C["ImageClip"](np.zeros((48, 64, 3), "uint8"), duration=1))
build("VideoClip", lambda: C["VideoClip"](frame_function=lambda t: np.zeros((48, 64, 3), "uint8"), duration=1),
      lambda: C["VideoClip"](make_frame=lambda t: np.zeros((48, 64, 3), "uint8"), duration=1))
audio = build("AudioClip", lambda: C["AudioClip"](frame_function=lambda t: np.sin(440 * 2 * np.pi * t), duration=1, fps=22050),
              lambda: C["AudioClip"](make_frame=lambda t: np.sin(440 * 2 * np.pi * t), duration=1, fps=22050))
if color is not None:
    build("CompositeVideoClip", lambda: C["CompositeVideoClip"]([color]))
    cat = importlib.import_module("moviepy.editor" if out["editor"] == "ok" else "moviepy").concatenate_videoclips
    build("concatenate_videoclips()", lambda: cat([color, color]))
    try:
        c2 = first(lambda: color.with_fps(10), lambda: color.set_fps(10))
        if audio is not None:
            c2 = first(lambda: c2.with_audio(audio), lambda: c2.set_audio(audio))
        first(lambda: c2.write_videofile("t.mp4", fps=10, logger=None), lambda: c2.write_videofile("t.mp4", fps=10, verbose=False, logger=None))
        build("VideoFileClip", lambda: C["VideoFileClip"]("t.mp4"))
        build("AudioFileClip", lambda: C["AudioFileClip"]("t.mp4"))
    except Exception as e:
        errs["write_videofile"] = "%s: %s" % (type(e).__name__, str(e)[:200])
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
build("TextClip", lambda: C["TextClip"](text="hi", font=FONT, font_size=20, color="white", duration=1),
      lambda: C["TextClip"]("hi", fontsize=20, color="white").set_duration(1))
out["inst"], out["inst_errors"] = inst, errs
json.dump(out, REAL_STDOUT, separators=(",", ":"))
