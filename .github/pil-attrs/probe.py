"""usage: <python with one Pillow> probe.py dir > dir.json
          <python with one Pillow> probe.py get names.json > get.json
Objects: the PIL modules and the classes people call methods on (Image.Image, ImageDraw.ImageDraw, ImageFont.FreeTypeFont, ImageFont.ImageFont). `dir` lists the public names of each and its __all__ (or the import
error); `get` runs getattr for the union of names and records ok, the first warning, or the error."""
import importlib, json, pkgutil, sys, warnings
warnings.simplefilter("ignore")
MODS = ["PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont", "PIL.ImageOps", "PIL.ImageFilter", "PIL.ImageEnhance", "PIL.ImageChops",
        "PIL.ImageColor", "PIL.ImageFile", "PIL.ImageGrab", "PIL.ImageSequence", "PIL.ImageStat", "PIL.ImageTk", "PIL.ImageQt", "PIL.ImageMath",
        "PIL.ImageCms", "PIL.ImagePalette", "PIL.ImagePath", "PIL.ImageShow", "PIL.ImageTransform", "PIL.ImageWin", "PIL.ExifTags", "PIL.TiffTags",
        "PIL.features", "PIL.PngImagePlugin", "PIL.JpegImagePlugin", "PIL.GifImagePlugin", "PIL.TiffImagePlugin"]
CLASSES = ["PIL.Image:Image", "PIL.ImageDraw:ImageDraw", "PIL.ImageFont:FreeTypeFont", "PIL.ImageFont:ImageFont"]


def load(spec):
    m, _, c = spec.partition(":")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        o = importlib.import_module(m)
        return getattr(o, c) if c else o


O, ERR = {}, {}
for s in MODS + CLASSES:
    try:
        O[s] = load(s)
    except Exception as e:
        ERR[s] = "%s: %s" % (type(e).__name__, e)
import PIL
if sys.argv[1] == "dir":
    json.dump({"pillow": PIL.__version__, "python": sys.version.split()[0], "import_errors": ERR,
               "dir": {k: sorted(n for n in dir(v) if not n.startswith("_")) for k, v in O.items()},
               "all": {k: sorted(getattr(v, "__all__")) for k, v in O.items() if isinstance(getattr(v, "__all__", None), (list, tuple))},
               "submodules": {k: sorted(m.name for m in pkgutil.iter_modules(v.__path__) if not m.name.startswith("_") and m.name != "tests")
                              for k, v in O.items() if hasattr(v, "__path__")}}, sys.stdout)
else:
    out = {}
    for k, names in json.load(open(sys.argv[2])).items():
        res = {}
        for n in names:
            if k not in O:
                res[n] = {"ok": False, "error": ERR.get(k, "missing"), "warn": []}
                continue
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                try:
                    getattr(O[k], n)
                    res[n] = {"ok": True, "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
                except Exception as e:
                    try:   # a submodule that is not imported by its package: `import sklearn.ensemble.forest`
                        if not hasattr(O[k], "__path__"):
                            raise
                        importlib.import_module("%s.%s" % (k, n))
                        res[n] = {"ok": True, "module": True, "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
                    except Exception as e2:
                        res[n] = {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "warn": [(x.category.__name__, str(x.message)) for x in w][:1]}
        out[k] = res
    json.dump({"pillow": PIL.__version__, "import_errors": ERR, "get": out}, sys.stdout)
