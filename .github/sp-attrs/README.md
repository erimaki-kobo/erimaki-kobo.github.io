# en/scipy-removed-name-lookup: how the page is built

probe.py runs inside an installed SciPy: `dir` lists the public names and __all__ of scipy, its submodules and the sparse
matrix classes; `get` runs getattr for the union over all releases. msg_probe.py runs in the last release before each
removal and reads the deprecation text from the installed source (decorator and warnings.warn strings of the definition,
module-level string constants resolved; fallback: any deprecation string in SciPy that names it near the start). pre13.py
reads the scipy.misc names removed in 1.3.0 from the source at v1.2.0 and v1.3.0 (no Python 3.8 wheels before 1.3.3).
build_page.py drops names outside a module's __all__ and __future__/typing/stdlib names, and for names with no text names
the module that still has the same name in the latest release. Results in probes/.

```
curl -sS https://pypi.org/pypi/scipy/json -o pypi.json; git clone --bare --filter=blob:none https://github.com/scipy/scipy sc.git
for spec in "1.3.3 3.8 1.17.5" "1.4.0 3.8 1.18.5" "1.5.0 3.8 1.19.5" "1.6.0 3.9 1.19.5" "1.7.0 3.9 1.21.6" "1.8.0 3.10 1.22.4" \
            "1.9.0 3.10 1.23.5" "1.10.0 3.11 1.24.4" "1.11.1 3.11 1.25.2" "1.12.0 3.12 1.26.4" "1.13.0 3.12 1.26.4" "1.14.0 3.12 2.0.2" \
            "1.15.0 3.12 2.2.6" "1.16.0 3.12 -" "1.17.0 3.12 -" "1.18.0 3.12 -" "1.18.1 3.12 -"; do
  set -- $spec; uv venv -q --python $2 v_$1
  if [ "$3" = "-" ]; then uv pip install -q --python v_$1/bin/python "scipy==$1"; else uv pip install -q --python v_$1/bin/python "scipy==$1" "numpy==$3"; fi
  v_$1/bin/python -I probe.py dir > probes/dir_$1.json
done
# names.json = union of the dir lists per object; for every release: v_X/bin/python -I probe.py get names.json > probes/get_X.json
# want_X.json = names X has and the next release read does not; v_X/bin/python -I msg_probe.py want_X.json > probes/msg_X.json
python3 -I pre13.py sc.git > pre13.json
python3 -I build_page.py probes pre13.json pypi.json <repo>/en/scipy-removed-name-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
