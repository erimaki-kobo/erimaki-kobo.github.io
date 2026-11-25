# en/matplotlib-removed-name-lookup: how the page is built

Same method as ../pil-attrs and ../sk-attrs (build_page.py started from pil-attrs), with three additions:
every patch release is read (cm.get_cmap is gone in 3.9.0, back in 3.9.1/3.9.2, gone for good in 3.11.0);
inst_probe.py runs hasattr on real objects (attributes set in __init__ are not on the class, e.g. Legend.legendHandles
before 3.7, Axes3D.dist); style_probe.py tries every style name with plt.style.context.
msg_probe.py turns `@_api.deprecated("3.8", alternative="buffer_rgba")` and `x = _api.deprecate_privatize_attribute("3.6")`
into a sentence of the same content.

```
curl -sS https://pypi.org/pypi/matplotlib/json -o pypi.json
# every release >= 3.1.2 with a linux x86_64 wheel, not yanked: Python 3.8 (numpy 1.19.5; 1.21.6 for 3.6.x, 1.23.5 for 3.7.x)
# up to 3.7.5, 3.9 (numpy 1.21.6) for 3.8.x, 3.12 for 3.9.0 and later (3.4.0/3.5.0 3.9, 3.6.0 3.10, 3.7.0 3.11, 3.11.2 3.13 from the first pass)
uv venv -q --python $PY v_$V; uv pip install -q --python v_$V/bin/python "matplotlib==$V" ["numpy==$NP"]
v_$V/bin/python -I probe.py dir > probes/dir_$V.json
# names.json = union of the dir lists (dir + submodules)
v_$V/bin/python -I probe.py get names.json > probes/get_$V.json
v_$V/bin/python -I inst_probe.py names.json > probes/inst_$V.json
v_$V/bin/python -I style_probe.py stylenames.json > probes/style_$V.json   # stylenames = union of style.available, no "_" names
# want_X.json = names X has (class attribute or on the object) and the next release does not
v_X/bin/python -I msg_probe.py want_X.json > probes/msg_X.json
python3 -I build_page.py probes notes.json pypi.json <repo>/en/matplotlib-removed-name-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
Independent check: the warnings matplotlib prints when cm.get_cmap (3.10.9), Axes.plot_date and plt.plot_date (3.10.9),
tostring_rgb (3.9.4), legendHandles and register_cmap (3.8.4) are used match the page's "Instead" text.

The probe results are in probes.tar.xz (`tar xJf probes.tar.xz` gives probes/).
