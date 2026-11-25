"""usage: <python with one scikit-image> sig_probe.py > sig.json
For every public function and class of scikit-image's public subpackages: the parameter names in its signature, whether it takes
**kwargs, and the old keyword names its deprecation wrappers still accept (read from the wrapper objects scikit-image attaches to
the function: deprecate_kwarg, deprecate_multichannel_kwarg, remove_arg, deprecate_parameter)."""
import importlib, inspect, json, os, sys, warnings
REAL, sys.stdout = sys.stdout, open(os.devnull, "w")
warnings.simplefilter("ignore")
import skimage
MODS = ["skimage"] + ["skimage." + m for m in ("color", "data", "draw", "exposure", "feature", "filters", "filters.rank", "future", "future.graph", "graph", "io",
                                              "measure", "metrics", "morphology", "registration", "restoration", "segmentation", "transform", "util")]
KEEP = ("hint", "kwarg_mapping", "removed_version", "deprecated_version", "arg_name", "changed_version", "help_msg", "warning_msg",
        "deprecated_name", "new_name", "start_version", "stop_version", "position")


def helpers(f):
    """The deprecation-helper objects in the closures of f and of everything it wraps."""
    found, hops = [], 0
    while f is not None and hops < 12:
        hops += 1
        for c in getattr(f, "__closure__", None) or ():
            try:
                v = c.cell_contents
            except ValueError:
                continue
            t = type(v)
            if (getattr(t, "__module__", "") or "").startswith("skimage") and t.__name__.lower().startswith(("deprecate", "remove", "change")):
                d = {"type": t.__name__}
                for a in KEEP:
                    if hasattr(v, a):
                        x = getattr(v, a)
                        d[a] = x if isinstance(x, (str, int, float, bool, type(None), dict, list)) else repr(x)
                found.append(d)
        f = getattr(f, "__wrapped__", None)
    return found


out = {}
for m in MODS:
    try:
        mod = importlib.import_module(m)
    except Exception:
        continue
    for n in sorted(set(dir(mod)) | set(getattr(mod, "__all__", None) or ())):
        if n.startswith("_"):
            continue
        try:
            o = getattr(mod, n)
        except Exception:
            continue
        if not (inspect.isfunction(o) or inspect.isclass(o)) or not (getattr(o, "__module__", "") or "").startswith("skimage"):
            continue
        try:
            sig = inspect.signature(o)
        except (TypeError, ValueError):
            continue
        out.setdefault(m, {})[n] = {"p": [p for p in sig.parameters if sig.parameters[p].kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)],
                                    "kw": any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()),
                                    "pos": [p for p in sig.parameters if sig.parameters[p].kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)],
                                    "h": helpers(o.__init__ if inspect.isclass(o) else o)}
json.dump({"skimage": skimage.__version__, "sig": out}, REAL)
