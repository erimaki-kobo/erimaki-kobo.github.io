#!/usr/bin/env python3
"""Build en/opencv-removed-name-lookup/ (index.html and opencv_names.json).

Usage: python3 -I build_page.py probes/ notes.json out_dir PUBLISHED MODIFIED
probes/: dir_<m|c>_<version>.json from probe.py (m = opencv-python-headless, c = opencv-contrib-python-headless, one file per
installed release), doc_c_<version>.json from doc_probe.py (OpenCV's own @deprecated lines, read in the last release that has
the name), dates.json (PyPI upload dates, latest versions), gui.json (what the non-headless packages add).
notes.json: the rows of the first table and their notes; every note was run in the release it names.
ASCII only; the facts the prose names are asserted. style.css is shared with .github/llama-args."""
import collections, glob, html, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PD, NOTES, OUT, PUB, MOD = sys.argv[1], json.load(open(sys.argv[2])), Path(sys.argv[3]), sys.argv[4], sys.argv[5]
key = lambda v: tuple(int(x) for x in v.split("."))
e = html.escape
PKG = {"m": "opencv-python", "c": "opencv-contrib-python"}

R = {}
for f in glob.glob(os.path.join(PD, "dir_*.json")):
    m = re.match(r"dir_([mc])_(.+)\.json$", os.path.basename(f))
    R[(m.group(1), m.group(2))] = json.load(open(f))
VS = sorted({v for _, v in R}, key=key)
LATEST = VS[-1]
INFO = json.load(open(os.path.join(PD, "dates.json")))
GUI = json.load(open(os.path.join(PD, "gui.json")))
assert ("m", LATEST) in R and ("c", LATEST) in R and all(v == LATEST for v in INFO["latest"].values()), INFO["latest"]
DATE = {v: INFO["c"].get(v) or INFO["m"][v] for v in VS}
for (p, v), d in R.items():   # one package per environment, the version asked for, the same Python and numpy everywhere
    assert d["dist"] == ["%s-headless==%s" % (PKG[p], v)] and d["python"] == "3.8.20" and d["numpy"] == "1.24.4", (p, v, d["dist"])

# what each release has: S[(p, v)][obj] = set of names. obj is a module path ("cv2.aruco") or a class ("cv2:aruco_Dictionary")
S, KIND = {}, {}
for (p, v), d in sorted(R.items(), key=lambda x: (x[0][0] == "c", key(x[0][1]))):
    s = S[(p, v)] = {}
    for path, m in d["mods"].items():
        if path == "cv2.cv2":
            continue
        s[path] = set()
        for n, k in zip(m["names"], m["kinds"]):
            if k != "x" and n:
                s[path].add(n)
                KIND[(path, n)] = k
    for c, ms in d["classes"].items():
        s["cv2:" + c] = set(ms)
U = collections.defaultdict(set)
for s in S.values():
    for obj, names in s.items():
        U[obj] |= names


def pat(p, obj, n):
    return "".join("-" if (p, v) not in S else "o" if n in S[(p, v)].get(obj, ()) else "g" for v in VS)


def last_state(s):
    t = s.replace("-", "")
    return t[-1] if t else None


def removed_at(s):   # (first release without it after the last one with it, that last one), or None
    if "o" not in s or last_state(s) != "g":
        return None
    i = s.rindex("o")
    return VS[next(j for j in range(i + 1, len(s)) if s[j] == "g")], VS[i]


def first_at(s):   # where the final run of releases with it starts; None if it does not have it now or has it from the first release read
    if last_state(s) != "o":
        return None
    idx = [i for i, ch in enumerate(s) if ch != "-"]
    k = len(idx) - 1
    while k > 0 and s[idx[k - 1]] == "o":
        k -= 1
    return VS[idx[k]] if k > 0 else None


PAT = {(obj, n): (pat("m", obj, n), pat("c", obj, n)) for obj, names in U.items() for n in names}
for (obj, n), (pm, pc) in PAT.items():   # the contrib package has every name the main package has, release by release
    assert all(a != "o" or b in "o-" for a, b in zip(pm, pc)), (obj, n, pm, pc)
DOC = {}
for f in glob.glob(os.path.join(PD, "doc_c_*.json")):
    v = os.path.basename(f)[6:-5]
    for obj, x in json.load(open(f))["doc"].items():
        for n, t in x.items():
            DOC[(obj, n)] = (t, v)
NOTE = {(o, n): t for o, n, t in NOTES["rows"]}
NOTE.update({tuple(k.split("|")): t for k, t in NOTES.get("more", {}).items()})
for (o, n) in NOTE:
    assert (o, n) in PAT, (o, n)
LC, LM = S[("c", LATEST)], S[("m", LATEST)]
MODS_C = [o for o in LC if ":" not in o]


def lab(obj, n):
    return ("cv2.%s.%s" % (obj[4:], n)) if ":" in obj else "%s.%s" % (obj, n)


def hint(obj, n):   # ["n", text] our note | ["d", release, OpenCV's text] | ["w", module, in_main] same name elsewhere | ["s", dotted, in_main]
    pm, pc = PAT[(obj, n)]
    if (obj, n) in NOTE:
        return ["n", NOTE[(obj, n)]]
    if last_state(pm) == "o":
        return None
    if (obj, n) in DOC:
        return ["d", DOC[(obj, n)][1], DOC[(obj, n)][0]]
    if last_state(pc) == "o" or ":" in obj:
        return None
    where = sorted(o for o in MODS_C if o != obj and n in LC[o])
    if where:
        return ["w", where[0], int(n in LM.get(where[0], ()))]
    for i in [i for i, ch in enumerate(n) if ch == "_"]:
        cls, meth = n[:i], n[i + 1:]
        flat = "cv2:" + (obj[4:].replace(".", "_") + "_" if obj != "cv2" else "") + cls
        if meth and meth in LC.get(flat, ()):
            return ["s", "%s.%s.%s" % (obj, cls, meth), int(meth in LM.get(flat, ()))]
    return None


def hint_text(h):
    if h is None:
        return ""
    if h[0] == "n":
        return h[1]
    if h[0] == "d":
        return "OpenCV's own text in %s: \"%s\"" % (h[1].rsplit(".", 1)[0], h[2])
    pk = "both packages" if h[2] else "opencv-contrib-python"
    if h[0] == "w":
        return "%s has a name spelled the same in %s (%s)." % (h[1], LATEST, pk)
    return "%s is in %s (%s)." % (h[1], LATEST, pk)


HINT = {}
for (obj, n) in PAT:
    h = hint(obj, n)
    if h:
        HINT[(obj, n)] = h


def rlabel(r):
    return "4.x (not in 4.1.2.30; last in 3.4.18.65)" if r[0] == "4.1.2.30" and r[1].startswith("3.4.") else "%s (last in %s)" % r


def cell(s):
    if last_state(s) == "o":
        f = first_at(s)
        return "has it" + (" (from %s)" % f if f else "")
    r = removed_at(s)
    return "removed in %s" % rlabel(r) if r else "never had it"


# facts the prose names
def P(o, n):
    return PAT[(o, n)]


def gone(o, n, p, v, last):
    assert removed_at(P(o, n)[p == "c"]) == (v, last), (o, n, p, removed_at(P(o, n)[p == "c"]))


for n in ("CascadeClassifier", "HOGDescriptor", "ml", "gapi", "groupRectangles"):   # out of opencv-python in 5.0, still in contrib
    gone("cv2", n, "m", "5.0.0.93", "4.14.0.94")
    assert last_state(P("cv2", n)[1]) == "o", n
for n in ("readNetFromCaffe", "readNetFromDarknet", "readNetFromTorch"):
    gone("cv2.dnn", n, "m", "5.0.0.93", "4.14.0.94"); gone("cv2.dnn", n, "c", "5.0.0.93", "4.14.0.94")
gone("cv2.dnn", "readNetFromTensorflow", "m", "5.1.0.95", "5.0.0.93"); gone("cv2.dnn", "readNetFromTensorflow", "c", "5.1.0.95", "5.0.0.93")
for n in ("readNet", "readNetFromONNX", "readNetFromTFLite"):
    assert last_state(P("cv2.dnn", n)[0]) == "o", n
for n in ("KAZE_create", "AKAZE_create", "BRISK_create", "logPolar", "linearPolar"):
    gone("cv2", n, "m", "5.0.0.93", "4.14.0.94"); gone("cv2", n, "c", "5.0.0.93", "4.14.0.94")
for n in ("KAZE_create", "AKAZE_create", "BRISK_create"):
    assert P("cv2.xfeatures2d", n)[1].rstrip("o").endswith("g") and P("cv2.xfeatures2d", n)[1].endswith("oo") and last_state(P("cv2.xfeatures2d", n)[0]) != "o"
for n in ("ORB_create", "SIFT_create", "warpPolar", "drawFrameAxes", "estimateAffinePartial2D", "estimateAffine2D", "Stitcher_create"):
    assert last_state(P("cv2", n)[0]) == "o", n
for n in ("xfeatures2d", "face", "ximgproc", "bgsegm", "optflow"):   # only ever in the contrib package
    assert "o" not in P("cv2", n)[0] and set(P("cv2", n)[1]) == {"o"}, n
assert "o" not in P("cv2", "legacy")[0] and first_at(P("cv2", "legacy")[1]) == "4.5.1.48"
for n in ("Dictionary_get", "DetectorParameters_create", "drawMarker", "GridBoard_create", "CharucoBoard_create", "custom_dictionary", "Board_create"):
    gone("cv2.aruco", n, "c", "4.7.0.68", "4.6.0.66")
    assert "o" not in P("cv2.aruco", n)[0]
gone("cv2.aruco", "drawAxis", "c", "4.6.0.66", "4.5.5.64")
for n in ("detectMarkers", "estimatePoseSingleMarkers"):
    gone("cv2.aruco", n, "c", "5.0.0.93", "4.14.0.94")
    assert "o" not in P("cv2.aruco", n)[0]
for n in ("getPredefinedDictionary", "ArucoDetector", "DetectorParameters", "generateImageMarker", "extendDictionary", "CharucoBoard", "GridBoard", "Board"):
    assert first_at(P("cv2.aruco", n)[0]) == "4.7.0.72" and last_state(P("cv2.aruco", n)[1]) == "o", n
assert first_at(P("cv2", "aruco")[0]) == "4.7.0.72" and set(P("cv2", "aruco")[1]) == {"o"}
assert first_at(P("cv2", "barcode")[0]) == "4.8.0.76" and first_at(P("cv2", "barcode")[1]) == "4.5.3.56"
for n in ("TrackerMOSSE_create", "TrackerBoosting_create", "TrackerMedianFlow_create", "TrackerTLD_create", "MultiTracker_create"):
    gone("cv2", n, "c", "4.5.1.48", "4.4.0.46")
    assert "o" not in P("cv2", n)[0] and first_at(P("cv2.legacy", n)[1]) == "4.5.1.48", n
for n in ("TrackerKCF_create", "TrackerCSRT_create"):
    assert "o" not in P("cv2", n)[0] and set(P("cv2", n)[1]) == {"o"}
assert first_at(P("cv2", "TrackerMIL_create")[0]) == "4.5.1.48"
gone("cv2", "TrackerGOTURN_create", "c", "5.0.0.93", "4.14.0.94")
for n in ("estimateRigidTransform", "createStitcher", "createOptFlow_DualTVL1"):
    gone("cv2", n, "m", "4.1.2.30", "3.4.18.65"); gone("cv2", n, "c", "4.1.2.30", "3.4.18.65")
gone("cv2", "createShapeContextDistanceExtractor", "m", "4.1.2.30", "3.4.18.65")
assert last_state(P("cv2", "createShapeContextDistanceExtractor")[1]) == "o"
assert first_at(P("cv2", "SIFT_create")[0]) == "4.4.0.46" and first_at(P("cv2", "SIFT_create")[1]) == "4.4.0.42" and P("cv2", "SIFT_create")[0][VS.index("3.4.11.43")] == "o"
assert set(P("cv2.xfeatures2d", "SIFT_create")[1]) == {"o"} and set(P("cv2.xfeatures2d", "SURF_create")[1]) == {"o"}
for n in ("getLogLevel", "setLogLevel"):
    gone("cv2", n, "m", "4.13.0.90", "4.12.0.88")
    assert last_state(P("cv2.utils.logging", n)[0]) == "o"
gone("cv2", "haarcascades", "m", "4.5.4.58", "4.5.3.56")
assert last_state(P("cv2.data", "haarcascades")[0]) == "o"
gone("cv2", "cv2", "m", "4.6.0.66", "4.5.5.64")
IMP = {(p, v): d["imports"] for (p, v), d in R.items()}
for p in "mc":   # import cv2.cv2: works up to 4.5.5.64 and 3.4.17.63, fails from 4.6.0.66 and 3.4.18.65
    for v in VS:
        if (p, v) in IMP:
            assert IMP[(p, v)]["cv2"]["ok"] == (key(v) < (3, 4, 18) or (4,) <= key(v) < (4, 6)), (p, v)
            assert IMP[(p, v)]["typing"]["ok"] == (key(v) >= (4, 8, 0, 76)), (p, v)
CV2CV2_34 = IMP[("m", "3.4.18.65")]["cv2"]["error"]
assert CV2CV2_34 == "ModuleNotFoundError: No module named 'cv2.cv2'; 'cv2' is not a package" == IMP[("c", "3.4.18.65")]["cv2"]["error"], CV2CV2_34
for (p, v), x in IMP.items():   # every 4.6+ and 5.x release fails the same way
    assert key(v) < (4, 6) or x["cv2"]["error"].startswith("ImportError: Bindings generation error."), (p, v, x["cv2"])
CV2CV2 = IMP[("m", "4.6.0.66")]["cv2"]["error"]
assert CV2CV2 == "ImportError: Bindings generation error. Submodule name should always start with a parent module name. Parent name: cv2.cv2. Submodule name: cv2" == IMP[("c", LATEST)]["cv2"]["error"]
assert first_at(P("cv2.dnn", "DictValue")[0]) == "4.6.0.66" and first_at(P("cv2.gapi.wip.draw", "Text")[1]) == "4.5.4.58"
for g, x in GUI.items():
    assert x["only_gui"] == ["cv2.qt"] and x["only_headless"] == [], g
assert DOC[("cv2.aruco", "detectMarkers")][0] == "Use class ArucoDetector::detectMarkers" and DOC[("cv2.aruco", "estimatePoseSingleMarkers")][0] == "Use cv::solvePnP"
assert "warpPolar" in DOC[("cv2", "logPolar")][0] and DOC[("cv2.aruco", "drawAxis")][0] == "use cv::drawFrameAxes"
for o, ns in (("cv2.ml", ("SVM_create", "KNearest_create")), ("cv2.face", ("LBPHFaceRecognizer_create",)), ("cv2.optflow", ("DualTVL1OpticalFlow_create",)),
              ("cv2:aruco_CharucoBoard", ("getChessboardCorners", "generateImage")), ("cv2.utils.logging", ("LOG_LEVEL_ERROR",))):
    for n in ns:
        assert n in LC[o], (o, n)
assert "o" not in P("cv2", "ml")[0][VS.index("5.0.0.93"):] and "WARP_POLAR_LOG" in LM["cv2"] and "WARP_POLAR_LINEAR" in LM["cv2"] and "DICT_4X4_50" in LM["cv2.aruco"]
assert VS[0] == "3.4.8.29" and "4.1.2.30" in VS and not any(key(v)[:1] == (4,) and key(v) < (4, 1, 2) for v in VS)

# the data the lookup reads
POOL, IDX = [], {}
def pid(s):
    if s not in IDX:
        IDX[s] = len(POOL)
        POOL.append(s)
    return IDX[s]
NJ = {}
for obj in sorted(U):
    g = collections.defaultdict(list)
    for n in sorted(U[obj]):
        pm, pc = PAT[(obj, n)]
        g[(pid(pm), pid(pc))].append(n)
    NJ[obj] = [[a, b, " ".join(ns)] for (a, b), ns in sorted(g.items())]
n_m, n_c = sum(1 for p, _ in R if p == "m"), sum(1 for p, _ in R if p == "c")
DATA = {"vs": [[v, DATE[v]] for v in VS], "pat": POOL, "n": NJ, "h": {"%s|%s" % k: h for k, h in sorted(HINT.items())},
        "imp": {"cv2": CV2CV2, "cv2_34": CV2CV2_34}}
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json
n_names = len(PAT)
n_mod = sum(1 for o in U if ":" not in o)
n_cls = sum(1 for o in U if ":" in o)

# every change, by release
A, B = collections.defaultdict(list), collections.defaultdict(list)   # gone from the contrib package (so from both) | from opencv-python only
def parent_gone(p, obj, v):   # the module or class itself is not in that release: list it once, not each of its names
    return obj not in S[(p, v)] if (p, v) in S else False
for (obj, n), (pm, pc) in PAT.items():
    rc, rm = removed_at(pc), removed_at(pm)
    if rc and not parent_gone("c", obj, rc[0]):
        A[rc[0]].append((obj, n))
    if rm and last_state(pc) == "o" and not parent_gone("m", obj, rm[0]):
        B[rm[0]].append((obj, n))
n_A, n_B = sum(len(x) for x in A.values()), sum(len(x) for x in B.values())
def names_html(items):
    mods = sorted(lab(o, n) for o, n in items if ":" not in o)
    mem = sorted(lab(o, n) for o, n in items if ":" in o)
    out = "<p><code>%s</code></p>" % e(", ".join(mods)) if mods else ""
    if mem:
        out += "<p>Class members (the class is still there): <code>%s</code></p>" % e(", ".join(mem))
    return out
rel_blocks = []
for v in sorted(set(A) | set(B), key=key, reverse=True):
    a, b = A.get(v, []), B.get(v, [])
    vl = "4.1.2.30 (the first 4.x release read; these are in 3.4.18.65)" if v == "4.1.2.30" else v
    rel_blocks.append("<details><summary><strong>%s</strong> (%s): %d gone from opencv-contrib-python, %d more gone from opencv-python only</summary>\n%s%s</details>"
                      % (e(vl), DATE[v], len(a), len(b),
                         ("<p><em>Gone from opencv-contrib-python (and from opencv-python, where it had them):</em></p>" + names_html(a)) if a else "",
                         ("<p><em>Gone from opencv-python, still in opencv-contrib-python %s:</em></p>" % LATEST + names_html(b)) if b else ""))
rel_html = "\n".join(rel_blocks)

URL = "https://erimaki-kobo.github.io/en/opencv-removed-name-lookup/"
TITLE = "module 'cv2' has no attribute 'CascadeClassifier' (OpenCV 5), any name: fix"
H1 = ("AttributeError: module 'cv2' has no attribute 'CascadeClassifier' (or 'xfeatures2d', 'TrackerMOSSE_create', module 'cv2.aruco' has no attribute "
      "'Dictionary_get', module 'cv2.dnn' has no attribute 'readNetFromCaffe', any name): which OpenCV package and release has it")
DESC = ("opencv-python 5 no longer has cv2.CascadeClassifier, HOGDescriptor or cv2.ml (contrib only now); 4.7 removed aruco.Dictionary_get. "
        "%d package releases installed and read." % len(R))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))

tab = []
for o, n, t in NOTES["rows"]:
    pm, pc = PAT[(o, n)]
    tab.append("<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(lab(o, n)), e(cell(pm)), e(cell(pc)), e(t)))
tab_html = "\n".join(tab)
D50, D51, D47, D451 = DATE["5.0.0.93"], DATE["5.1.0.95"], DATE["4.7.0.68"], DATE["4.5.1.48"]
FAQ = [
    ("How do I fix \"module 'cv2' has no attribute 'CascadeClassifier'\"?",
     "opencv-python 5.0.0.93 (%s) is the first release without cv2.CascadeClassifier; 4.14.0.94 is the last with it. opencv-contrib-python 5 still has it, "
     "and in 5.1.0.95 only the contrib package ships haarcascade_frontalface_default.xml in cv2.data. Either pip uninstall opencv-python and "
     "pip install opencv-contrib-python, or pip install \"opencv-python<5\". The same holds for cv2.HOGDescriptor, cv2.ml (SVM, KNearest) and cv2.gapi." % D50),
    ("How do I fix \"module 'cv2.dnn' has no attribute 'readNetFromCaffe'\" (or readNetFromDarknet, readNetFromTensorflow)?",
     "OpenCV 5.0.0.93 removed readNetFromCaffe, readNetFromDarknet and readNetFromTorch; 5.1.0.95 (%s) removed readNetFromTensorflow. In 5.1.0, "
     "cv2.dnn.readNet on a .caffemodel raises \"Caffe importer has been removed\" and asks for an ONNX-converted model or an older OpenCV. "
     "readNetFromONNX, readNetFromTFLite and readNet are still there. To keep the old readers: pip install \"opencv-python<5\"." % D51),
    ("How do I fix \"module 'cv2' has no attribute 'xfeatures2d'\" (or 'face', 'ximgproc', 'legacy', 'bgsegm')?",
     "These modules have only ever been in opencv-contrib-python, in every release read (3.4.8.29 to %s). Uninstall opencv-python (and opencv-python-headless) "
     "and install opencv-contrib-python: one OpenCV package per environment. SIFT needs no contrib: cv2.SIFT_create is in opencv-python from 4.4.0.46. "
     "cv2.xfeatures2d.SURF_create exists in the contrib wheels but raises \"This algorithm is patented and is excluded in this configuration\" (tried in 4.14.0 and 5.1.0)." % LATEST),
    ("How do I fix \"module 'cv2.aruco' has no attribute 'Dictionary_get'\" (or 'DetectorParameters_create')?",
     "opencv-contrib-python 4.7.0.68 (%s) removed them; 4.6.0.66 is the last with them. Use cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), "
     "cv2.aruco.DetectorParameters(), and cv2.aruco.ArucoDetector(dictionary, parameters).detectMarkers(image). drawMarker became generateImageMarker, "
     "CharucoBoard_create became CharucoBoard((squaresX, squaresY), squareLength, markerLength, dictionary). opencv-python has cv2.aruco only from 4.7.0.72. "
     "OpenCV 5.0 then removed the cv2.aruco.detectMarkers function and estimatePoseSingleMarkers (OpenCV's text: \"Use cv::solvePnP\")." % D47),
    ("How do I fix \"module 'cv2' has no attribute 'TrackerMOSSE_create'\" (or 'MultiTracker_create')?",
     "opencv-contrib-python 4.5.1.48 (%s) moved the MOSSE, Boosting, MedianFlow and TLD trackers and MultiTracker to cv2.legacy: "
     "cv2.legacy.TrackerMOSSE_create(), cv2.legacy.MultiTracker_create(). They were never in opencv-python. TrackerKCF_create and TrackerCSRT_create "
     "are at the top level of the contrib package in every release; TrackerMIL_create is in opencv-python from 4.5.1.48." % D451),
    ("What does \"ImportError: Bindings generation error. Submodule name should always start with a parent module name. Parent name: cv2.cv2\" mean?",
     "import cv2.cv2 (an old trick for editor completion) works up to 4.5.5.64 and raises this error in every release from 4.6.0.66. "
     "In the 3.4 line it works up to 3.4.17.63; 3.4.18.65 raises \"No module named 'cv2.cv2'; 'cv2' is not a package\". Write import cv2."),
    ("How do I fix \"module 'cv2.gapi.wip.draw' has no attribute 'Text'\" or \"module 'cv2.dnn' has no attribute 'DictValue'\"?",
     "Both names are read by cv2/typing/__init__.py, which the packages ship from 4.8.0.76. Every clean install here imported without error. The first "
     "error appeared in each of four tries where a newer opencv-python-headless (4.8.0.76, 4.8.1.78, 4.9.0.80) and then an older "
     "opencv-contrib-python-headless (4.5.4.58 to 4.5.5.64) were installed into one environment: the newer package's cv2/typing folder stays behind and the "
     "older one loads it. The second error did not appear in those tries; it comes from the same file. pip uninstall all four packages (opencv-python, "
     "opencv-contrib-python and the two -headless ones), then install exactly one."),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["OpenCV", "opencv-python", "AttributeError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "OpenCV (cv2) name lookup", "url": URL + "#lookup",
     "description": "Paste an AttributeError from cv2 and get, for opencv-python and opencv-contrib-python, which releases from %s to %s have the name, and what to use instead." % (VS[0], LATEST),
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "cv2 names by OpenCV package and release", "url": URL + "opencv_names.json", "dateModified": MOD,
     "description": "The %d names of cv2, its %d submodules and %d classes in %d installed releases of opencv-python-headless and opencv-contrib-python-headless (%s to %s)." % (n_names, n_mod - 1, n_cls, len(R), VS[0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "opencv_names.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += ("\n.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\ntd code,p code,li code,h1,h2,h3,details code{overflow-wrap:anywhere}"
        "main p,main li,td{overflow-wrap:break-word}\n.s-ok{color:var(--ok,#1a7f37)}.s-gone{color:#cf222e}.s-na{opacity:.6}\ndetails{margin:.5rem 0}details code{font-size:.8rem}summary{cursor:pointer}\n")
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("AttributeError: module 'cv2' has no attribute 'CascadeClassifier'", "CascadeClassifier"),
      ("AttributeError: module 'cv2.dnn' has no attribute 'readNetFromCaffe'", "readNetFromCaffe"),
      ("AttributeError: module 'cv2' has no attribute 'xfeatures2d'", "xfeatures2d"),
      ("AttributeError: module 'cv2.aruco' has no attribute 'Dictionary_get'", "aruco.Dictionary_get"),
      ("AttributeError: module 'cv2' has no attribute 'TrackerMOSSE_create'", "TrackerMOSSE_create"),
      ("AttributeError: module 'cv2' has no attribute 'SIFT_create'", "SIFT_create")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  var VS = D.vs, P = D.pat, N = {}, LAST = VS[VS.length - 1][0], FIRST = VS[0][0];
  Object.keys(D.n).forEach(function (o) { N[o] = {}; D.n[o].forEach(function (g) { g[2].split(" ").forEach(function (n) { N[o][n] = [P[g[0]], P[g[1]]]; }); }); });
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function objKey(path) {
    path = path.replace(/^cv2\.cv2(?=\.|$)/, "cv2");
    if (N[path]) return path;
    var flat = "cv2:" + path.slice(4).replace(/\./g, "_");
    return path.length > 4 && N[flat] ? flat : null;
  }
  function find(t) {
    var out = [], m;
    var re = /module '(cv2(?:\.\w+)*)' has no attribute '(\w+)'|(?:type object )?'cv2\.([\w.]+)' (?:object )?has no attribute '(\w+)'|cannot import name '(\w+)' from '(cv2(?:\.\w+)*)'|No module named '(cv2(?:\.\w+)+)'|\bcv2?\.((?:\w+\.)*\w+)/g;
    while ((m = re.exec(t))) {
      if (m[1]) out.push([m[1], m[2]]);
      else if (m[3]) out.push(["cv2." + m[3], m[4]]);
      else if (m[5]) out.push([m[6], m[5]]);
      else {
        var s = ("cv2." + (m[7] ? m[7].slice(4) : m[8])).split(".");
        if (s.length > 2 || m[7] || N.cv2[s[1]] || /^[A-Za-z_]\w+$/.test(s[1])) out.push([s.slice(0, -1).join("."), s[s.length - 1], !m[7]]);
      }
    }
    var ex = out.filter(function (f) { return !f[2]; });
    return ex.length ? ex : out;
  }
  function lastState(p) { for (var i = p.length - 1; i >= 0; i--) if (p[i] !== "-") return p[i]; return null; }
  function removedAt(p) {
    var i = p.lastIndexOf("o");
    if (i < 0 || lastState(p) !== "g") return null;
    for (var j = i + 1; j < p.length; j++) if (p[j] === "g") return [VS[j][0], VS[i][0]];
    return null;
  }
  function firstAt(p) {
    if (lastState(p) !== "o") return null;
    var idx = [], i;
    for (i = 0; i < p.length; i++) if (p[i] !== "-") idx.push(i);
    var k = idx.length - 1;
    while (k > 0 && p[idx[k - 1]] === "o") k--;
    return k > 0 ? VS[idx[k]][0] : null;
  }
  function rlabel(r) { return r[0] === "4.1.2.30" && r[1].indexOf("3.4.") === 0 ? "4.x (not in 4.1.2.30, the first 4.x release read; last in 3.4.18.65)" : r[0] + " (last in " + r[1] + ")"; }
  function label(o, n) { return (o.indexOf(":") > 0 ? "cv2." + o.slice(4) : o) + "." + n; }
  function hintText(h) {
    if (!h) return "";
    if (h[0] === "n") return h[1];
    if (h[0] === "d") return "OpenCV's own text in " + h[1].replace(/\.\d+$/, "") + ': "' + h[2] + '"';
    var pk = h[2] ? "both packages" : "opencv-contrib-python";
    return h[0] === "w" ? h[1] + " has a name spelled the same in " + LAST + " (" + pk + ")." : h[1] + " is in " + LAST + " (" + pk + ").";
  }
  function table(pm, pc, lab) {
    var rows = [], fm = null, fc = null, i, cur;
    function fill(p, i) { for (var j = i; j < p.length; j++) if (p[j] !== "-") return p[j]; return null; }
    for (i = 0; i < VS.length; i++) {
      fm = pm[i] !== "-" ? pm[i] : (fm || fill(pm, i)); fc = pc[i] !== "-" ? pc[i] : (fc || fill(pc, i));
      cur = rows[rows.length - 1];
      if (cur && cur.m === fm && cur.c === fc) { cur.to = VS[i][0]; cur.rm = cur.rm || pm[i] !== "-"; cur.rc = cur.rc || pc[i] !== "-"; }
      else rows.push({from: VS[i][0], to: VS[i][0], m: fm, c: fc, rm: pm[i] !== "-", rc: pc[i] !== "-"});
    }
    function td(st, read) { return !read ? '<td class="s-na">no release read</td>' : st === "o" ? '<td class="s-ok">has it</td>' : '<td class="s-gone">not there</td>'; }
    var h = '<div class="tw"><table><thead><tr><th>Release</th><th>opencv-python</th><th>opencv-contrib-python</th></tr></thead><tbody>';
    rows.forEach(function (r) { h += "<tr><td>" + esc(r.from) + (r.to !== r.from ? " to " + esc(r.to) : "") + "</td>" + td(r.m, r.rm) + td(r.c, r.rc) + "</tr>"; });
    return h + "</tbody></table></div>";
  }
  function answer(o, n, partial) {
    var p = N[o][n], pm = p[0], pc = p[1], lm = lastState(pm), lc = lastState(pc), rm = removedAt(pm), rc = removedAt(pc), fm = firstAt(pm), fc = firstAt(pc);
    var lab = label(o, n), h = "<h3><code>" + esc(lab) + "</code></h3><p>", hint = hintText(D.h[o + "|" + n]);
    if (lm === "o") {
      if (!fm && !fc) h += "<strong>Every release read has it</strong> (" + FIRST + " to " + LAST + ", both packages), so this error is not about your OpenCV version.";
      else h += "<strong>In both packages in " + LAST + ".</strong> opencv-python has it " + (fm ? "from " + esc(fm) : "in every release read") + "; opencv-contrib-python " + (fc ? "from " + esc(fc) : "in every release read") + ". An older install does not have it: check <code>cv2.__version__</code>.";
      h += " If your version should have it, two OpenCV packages are probably mixed in one environment (<code>pip list</code> shows more than one of opencv-python, opencv-contrib-python and their -headless variants), or a file or folder named cv2 shadows the package: uninstall all of them and install one.";
    } else if (lc === "o") {
      h += rm ? "<strong>opencv-python removed it in " + esc(rlabel(rm)) + "; opencv-contrib-python " + LAST + " still has it.</strong>" :
        "<strong>Only in opencv-contrib-python</strong>" + (fc ? " (from " + esc(fc) + ")" : " (every release read)") + "; opencv-python never had it.";
      h += " Fix: <code>pip uninstall opencv-python opencv-python-headless</code>, then <code>pip install opencv-contrib-python</code> (one OpenCV package per environment)" + (fc ? ", version " + esc(fc) + " or later." : ".");
      if (rm && rm[0] !== "4.1.2.30") h += ' Or keep it: <code>pip install "opencv-python&lt;' + esc(rm[0]) + '"</code>';
    } else if (rc || rm) {
      var r = rc || rm;
      h += "<strong>Removed in " + esc(rlabel(r)) + ".</strong>";
      if (rm && rc && rm[0] !== rc[0]) h += " opencv-python: removed in " + esc(rlabel(rm)) + ".";
      if (!rm && pm.indexOf("o") < 0) h += " It was only ever in opencv-contrib-python.";
      if (r[0] !== "4.1.2.30") h += ' To keep it: <code>pip install "' + (pm.indexOf("o") < 0 ? "opencv-contrib-python" : "opencv-python") + "&lt;" + esc(r[0]) + '"</code>';
      else h += " 4.0.0 to 4.1.1 have no wheel for the Python used here and were not installed; the 3.4 line kept it to its last release.";
    }
    if (hint) h += "</p><p><strong>" + (lm === "o" ? "Note" : "Instead") + ":</strong> " + esc(hint);
    if (partial) h += "</p><p>\"partially initialized module 'cv2'\" means cv2's own Python files asked for a name the binary next to them does not have: files of two OpenCV packages or versions are mixed. Uninstall every OpenCV package and install one.";
    return h + "</p>" + table(pm, pc, lab);
  }
  function show() {
    var h = "", seen = {}, count = 0, t = q.value, partial = /partially initialized/.test(t);
    if (/Parent name: cv2\.cv2|import cv2\.cv2|No module named 'cv2\.cv2'/.test(t)) {
      h += "<h3><code>import cv2.cv2</code></h3><p><strong>Works up to 4.5.5.64 (and 3.4.17.63 in the 3.4 line); every release from 4.6.0.66 raises</strong> " + esc(D.imp.cv2) + ". 3.4.18.65 raises " + esc(D.imp.cv2_34) + ". Write <code>import cv2</code>.</p>";
    }
    find(t).forEach(function (f) {
      if (count >= 6) return;
      var o = objKey(f[0]), n = f[1];
      if (o && N[o][n]) { if (seen[o + "|" + n]) return; seen[o + "|" + n] = 1; count++; h += answer(o, n, partial); return; }
      if (seen["?" + n]) return; seen["?" + n] = 1;
      var where = Object.keys(N).filter(function (k) { return N[k][n] && lastState(N[k][n][1]) === "o"; });
      var ever = Object.keys(N).filter(function (k) { return N[k][n]; });
      if (f[2] && !ever.length) return;
      count++;
      h += "<h3><code>" + esc(f[0] + "." + n) + "</code></h3><p>" + (ever.length ?
        "Not at " + esc(f[0]) + " in any release read. The name is in: " + ever.slice(0, 8).map(function (k) { return "<code>" + esc(label(k, n)) + "</code>" + (where.indexOf(k) < 0 ? " (gone)" : ""); }).join(", ") + ". Paste that spelling for its releases." :
        "No release of opencv-python or opencv-contrib-python from " + FIRST + " to " + LAST + " has this name" + (o ? " in " + esc(f[0]) : "") + ". OpenCV 2.4 names (cv2.cv, cv2.CV_AA, cv2.CV_LOAD_IMAGE_COLOR) and names from other builds (CUDA, nonfree) are outside these packages.") + "</p>";
    });
    if (!h) h = "<p>Paste the error line, for example module 'cv2' has no attribute 'CascadeClassifier'.</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.CV_READY = true;
})();
"""
assert "</script" not in JS
py_note = "Python 3.8.20 and numpy 1.24.4 in every environment"
page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(TITLE, quote=False)}</title>
<meta name="description" content="{e(DESC)}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESC)}">
<meta property="og:url" content="{URL}">
<style>
{css}</style>
<script type="application/ld+json">{LD}</script>
</head>
<body>
<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>{e(H1, quote=False)}</h1>
<p class="lede"><strong>opencv-python 5.0 ({D50}) no longer has <code>cv2.CascadeClassifier</code>, <code>cv2.HOGDescriptor</code>, <code>cv2.ml</code> or <code>cv2.gapi</code>: opencv-contrib-python 5 still has them, and <code>pip install "opencv-python&lt;5"</code> keeps them. OpenCV 5 also removed <code>cv2.dnn.readNetFromCaffe</code>, <code>readNetFromDarknet</code> and <code>readNetFromTorch</code> (5.0) and <code>readNetFromTensorflow</code> (5.1.0, {D51}): load an ONNX model, or stay below 5. <code>cv2.xfeatures2d</code>, <code>cv2.face</code>, <code>cv2.ximgproc</code> and <code>cv2.legacy</code> have only ever been in opencv-contrib-python. 4.7.0 removed <code>cv2.aruco.Dictionary_get</code> (use <code>getPredefinedDictionary</code>); 4.5.1 moved <code>cv2.TrackerMOSSE_create</code> to <code>cv2.legacy</code>.</strong> Paste the error below: the answer says which releases of each package have the name.</p>
<p class="meta">Published {PUB} &middot; {len(R)} package releases installed and read ({n_m} opencv-python-headless, {n_c} opencv-contrib-python-headless), {VS[0]} to {LATEST} &middot; {n_names:,} names &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<label for="q">The error line, or the code</label>
<textarea id="q" spellcheck="false" placeholder="AttributeError: module 'cv2' has no attribute 'CascadeClassifier'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="opencv_names.json">opencv_names.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="table">Which package and release has it, and what replaces it?</h2>
<p><strong>The names people hit most.</strong> The two middle columns are measured; each "Instead" was run in the release it names (5.1.0.95 unless it says otherwise).</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>opencv-python</th><th>opencv-contrib-python</th><th>Instead</th></tr></thead>
<tbody>
{tab_html}
</tbody></table></div>

<h2 id="releases">What did each release remove?</h2>
<p><strong>{n_A:,} names went from opencv-contrib-python (and from opencv-python, where it had them) and {n_B:,} more from opencv-python only</strong> (those are still in opencv-contrib-python {LATEST}). A module or class that went as a whole is listed once, not name by name. The lookup above answers for every one, and for names that are still there.</p>
{rel_html}

<h2 id="how">How was this measured?</h2>
<p><strong>Every release of opencv-python-headless ({n_m}) and opencv-contrib-python-headless ({n_c}) on PyPI from {VS[0]} to {LATEST} that is not yanked and has a wheel for Python 3.8 (cp38 or abi3) was installed in its own environment, and the names of <code>cv2</code>, of every submodule reachable from it, and of every class it defines were listed with <code>dir()</code>.</strong> The binding is a compiled extension module, so <code>dir()</code> lists every name it has; OpenCV raises no Python deprecation warnings, so there is no "warns" state. {py_note}. 4.0.0 to 4.1.1 have wheels only up to Python 3.7 and were not installed, so a name that the 3.4 line has and 4.1.2.30 does not is reported as "not in 4.1.2.30", not as removed in a particular 4.0 or 4.1 release.</p>
<p>The headless packages are the same build without a GUI backend. Compared at 5.1.0.95 (both packages) and 4.6.0.66 (contrib), opencv-python and opencv-contrib-python have the same names plus <code>cv2.qt</code>. "OpenCV's own text" is the <code>@deprecated</code> line of the function's docstring in the last release that has it. <code>import cv2.&lt;name&gt;</code> was tried for each file in the package folder, each in its own process.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The <a href="https://pypi.org/project/opencv-python-headless/#history">opencv-python-headless</a> and <a href="https://pypi.org/project/opencv-contrib-python-headless/#history">opencv-contrib-python-headless</a> wheels on PyPI, installed and run; the release dates are PyPI's.</li>
<li>The docstrings and error messages of those builds (OpenCV's own text).</li>
</ul>
<p>The same data as JSON: <a href="opencv_names.json">opencv_names.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a> &middot; <a href="/en/pillow-removed-name-lookup/">"module 'PIL.Image' has no attribute 'ANTIALIAS'"</a> &middot; <a href="/en/matplotlib-removed-name-lookup/">"module 'matplotlib.cm' has no attribute 'get_cmap'"</a>.</p>
</main>
<script type="application/json" id="data">{data_json}</script>
<script>
{JS}</script>
</body>
</html>
"""
page.encode("ascii")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "index.html").write_text(page, encoding="ascii")
(OUT / "opencv_names.json").write_text(json.dumps(DATA, separators=(",", ":")), encoding="ascii")
print("index.html %d bytes (data %d) | names %d, patterns %d, hints %d | gone from both %d, main only %d | releases %d (%d + %d)"
      % (len(page), len(data_json), n_names, len(POOL), len(HINT), n_A, n_B, len(R), n_m, n_c), file=sys.stderr)
