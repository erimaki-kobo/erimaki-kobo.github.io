# en/scikit-image-removed-name-lookup: how the page is built

scikit-image 0.16.2 to 0.26.0 (22 releases, the yanked 0.23.0 included), each in its own uv venv: Python 3.8 for 0.16.2-0.21.0,
3.9 for 0.22.0, 3.10 for 0.23.0-0.25.2, 3.11 for 0.26.0; NumPy/SciPy of the time (numpy 1.19.5 + scipy 1.5.4 for 0.16.2-0.17.2,
1.21.6 + 1.7.3 for 0.18.x, 1.22.4 + 1.8.1 for 0.19.x, 1.24.4 for 0.20.0-0.21.0, "numpy<2" for 0.22.0-0.24.0); matplotlib added to
every venv (without it skimage.viewer's submodules fail to import in 0.19.x and look removed one release early).
Releases before 0.16.2 have no wheel for Python 3.8+ and are not covered.

- probe.py dir / get: public names, __all__ and submodule files of skimage and its subpackages; then getattr (or import) of the union.
- msg_probe.py: the deprecation text of each name in the last release that had it (the "**Deprecated" paragraph scikit-image's
  decorators put in the docstring, else the warnings.warn text in the body); falls back to getattr for lazily loaded names (0.20+).
- sig_probe.py: parameters of every public function/class (inspect.signature) and the deprecation wrappers found in its closures
  (deprecate_kwarg, deprecate_multichannel_kwarg, remove_arg, deprecate_parameter, deprecate_func) with their mapping and versions.
- kwprobe.py: real calls on a 32x32 test image: old-argument calls (does it raise TypeError for that argument?), the new spellings,
  and old/new pairs whose results are compared by digest ("same result" on the page only when the digests are equal).
- build_page.py: removed names; removed arguments (accepted in one release; later neither in the signature, nor wrapped, nor
  **kwargs), with that rule asserted against every real call; what the latest release still wraps as deprecated. notes.json: the
  four names scikit-image gave no text for.

```
curl -sS https://pypi.org/pypi/scikit-image/json -o pypi.json      # probes/pypi.json keeps upload_time, yanked, filename
uv venv -q --python $PY v_$V; uv pip install -q --python v_$V/bin/python "scikit-image==$V" $PINS matplotlib
v_$V/bin/python -I probe.py dir > probes/dir_$V.json           # then names.json = union of all names
v_$V/bin/python -I probe.py get names.json > probes/get_$V.json
v_$V/bin/python -I msg_probe.py want_$V.json > probes/msg_$V.json   # want_$V.json: names whose last release is $V
v_$V/bin/python -I sig_probe.py > probes/sig_$V.json
(mkdir kw_$V && cd kw_$V && ../v_$V/bin/python -I kwprobe.py > ../probes/kw_$V.json)
python3 -I build_page.py probes notes.json probes/pypi.json <repo>/en/scikit-image-removed-name-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
Not compared: structure_tensor_eigvals against structure_tensor_eigenvalues (a tuple of arrays against one stacked array).
structural_similarity takes **kwargs, so multichannel= is not in the arguments table for it: from 0.20.0 it is swallowed and a
color image fails with "win_size exceeds image extent" (asserted, and in the FAQ).
The probe results are in probes.tar.xz (`tar xJf probes.tar.xz` gives probes/).
