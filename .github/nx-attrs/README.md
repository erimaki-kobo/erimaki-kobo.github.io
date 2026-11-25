# en/networkx-removed-name-lookup: how the page is built

Same method as ../mpl-attrs (build_page.py and msg_probe.py started from there). probe.py lists and getattr-s 31 networkx
modules and the four graph classes; inst_probe.py builds a small graph of each class and runs hasattr (networkx 1.x set
G.node and G.edge on the object) and adds the object's own names to the union. msg_probe.py also takes the text of
`warnings.warn(msg, DeprecationWarning)` without the word "deprecat" and resolves a local `msg = ...`. notes.json holds the
replacements for names removed without a warning (most of the 1.x API in 2.0), from networkx's migration guides and release
notes (doc/release/ in the networkx repository); each was run in 3.7.

```
curl -sS https://pypi.org/pypi/networkx/json -o pypi.json
# every release from 1.11: Python 3.8 up to 3.1, 3.9 for 3.2.x, 3.10 for 3.3-3.4.2, 3.11 for 3.5-3.6.1, 3.12 for 3.7
# 1.11-2.5.1 with decorator==4.4.2; 1.11-2.2 also need "setuptools<70" (they import pkg_resources)
uv venv -q --python $PY v_$V; uv pip install -q --python v_$V/bin/python "networkx==$V" [decorator==4.4.2]
v_$V/bin/python -I probe.py dir > probes/dir_$V.json
v_$V/bin/python -I inst_probe.py names.json > probes/inst_$V.json   # names.json = union of dir + submodules (+ inst "dir")
v_$V/bin/python -I probe.py get names.json > probes/get_$V.json
# want_X.json = names X has (on the class or the object) and the next release does not
v_X/bin/python -I msg_probe.py want_X.json > probes/msg_X.json
python3 -I build_page.py probes notes.json pypi.json <repo>/en/networkx-removed-name-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
The probe results are in probes.tar.xz (`tar xJf probes.tar.xz` gives probes/).
