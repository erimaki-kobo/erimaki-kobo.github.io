"""usage: <python with one OpenCV package> doc_probe.py want.json > doc.json
want.json: {"cv2.aruco": ["detectMarkers", ...], "cv2:aruco_Board": ["draw", ...]}. For each name, the lines of its docstring
(OpenCV's own doxygen text, as built into the binding) that say @deprecated. Run in the last release that has the name."""
import json, re, sys, warnings
warnings.simplefilter("ignore")
import cv2
out = {}
for obj, names in json.load(open(sys.argv[1])).items():
    o = cv2
    try:
        if ":" in obj:
            o = getattr(cv2, obj.split(":")[1])
        else:
            for part in obj.split(".")[1:]:
                o = getattr(o, part)
    except AttributeError:
        continue
    for n in names:
        d = getattr(getattr(o, n, None), "__doc__", None) or ""
        dep = [re.sub(r"^[.*\s]+", "", l).strip() for l in d.splitlines() if "@deprecated" in l]
        dep = [re.sub(r"^@deprecated\s*", "", l) for l in dep if l]
        if dep and dep[0]:
            out.setdefault(obj, {})[n] = " ".join(dep[0].split())[:300]
json.dump({"cv2": cv2.__version__, "doc": out}, sys.stdout)
