# en/opencv-removed-name-lookup: how the page is built

81 environments: every release of opencv-python-headless (37) and opencv-contrib-python-headless (44) on PyPI from 3.4.8.29
that is not yanked and has a cp38 or abi3 wheel, each in its own uv venv (Python 3.8.20, numpy 1.24.4 as resolved).
4.0.0-4.1.1 have wheels only up to cp37 and are not read. probe.py walks cv2, its submodules and its classes with dir()
(the binding is a compiled module; OpenCV raises no Python deprecation warnings) and tries `import cv2.<file>` for each file in
the package folder. doc_probe.py reads the @deprecated line of the docstring in the last release that has a name.
notes.json: the rows of the first table and their notes; each note was run in 5.1.0.95 (contrib, and main where it applies).

```
curl -sS https://pypi.org/pypi/opencv-python-headless/json -o pypi_m.json      # and opencv-contrib-python-headless
uv venv -q --python 3.8 m_$V; uv pip install -q --python m_$V/bin/python "opencv-python-headless==$V"          # c_$V for contrib
m_$V/bin/python -I probe.py > probes/dir_m_$V.json                                                             # about 5 s per release
# want_X.json = names (contrib timeline) whose last release is X
c_X/bin/python -I doc_probe.py want_X.json > probes/doc_c_X.json
# probes/dates.json: PyPI upload dates, latest versions; probes/gui.json: probe.py on opencv-python / opencv-contrib-python
# (5.1.0.95 both, 4.6.0.66 contrib) minus the headless result: only cv2.qt differs
python3 -I build_page.py probes notes.json <repo>/en/opencv-removed-name-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
Mixed-install check (FAQ): `uv pip install opencv-python-headless==4.8.0.76` then `opencv-contrib-python-headless==4.5.5.64`
in one venv -> `import cv2` raises "module 'cv2.gapi.wip.draw' has no attribute 'Text'" from cv2/typing/__init__.py.
Same result for 4.8.1.78 then 4.5.4.60, 4.9.0.80 then 4.5.5.64, 4.9.0.80 then 4.5.4.58. The DictValue variant did not appear.
Direct check, not through build_page.py: 77 hasattr checks in 18 environments, and opencv-python (the GUI package)
4.14.0.94, 5.0.0.93 and 5.1.0.95 for CascadeClassifier, HOGDescriptor, ml, gapi, dnn.readNetFromCaffe: all as the page says.
Library table (probes/down.json): `python3 -I downstream_fetch.py packages.txt meta/ src/` downloads the newest sdist (or
wheel) of each package in packages.txt and unpacks its .py files, each package in its own folder; nothing in them is run.
`python3 -I downstream_scan.py <repo>/en/opencv-removed-name-lookup/opencv_names.json meta/ src/ > probes/down.json` parses
them. The imutils row was also run (opencv-python-headless and opencv-contrib-python-headless 5.1.0.95 with imutils 0.5.4).
The probe results are in probes.tar.xz (`tar xJf probes.tar.xz` gives probes/).
