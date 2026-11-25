# en/sklearn-removed-name-lookup: how the page is built

Same method as ../sp-attrs. probe.py runs inside an installed scikit-learn: `dir` lists the public names, __all__ and
submodules (pkgutil) of sklearn and its modules; `get` runs getattr for the union over all releases, and for a name that
is not an attribute of a package, `import package.name` (so `sklearn.ensemble.forest` counts). msg_probe.py reads the
deprecation text in the last release before each removal. pre22.py reads the removals before 0.22 (no Python 3.8 wheels)
from the source at the tags. build_page.py keeps names in __all__, submodules (not setup or tests), and sklearn.externals.

```
curl -sS https://pypi.org/pypi/scikit-learn/json -o pypi.json; git clone --bare --filter=blob:none https://github.com/scikit-learn/scikit-learn sk.git
for spec in "0.22 3.8 1.17.5 1.4.1" "0.23.0 3.8 1.18.5 1.4.1" "0.24.0 3.9 1.19.5 1.6.0" "1.0 3.9 1.21.6 1.7.3" "1.1.0 3.10 1.22.4 1.8.1" \
            "1.2.0 3.10 1.23.5 1.9.3" "1.3.0 3.11 1.24.4 1.10.1" "1.4.0 3.12 1.26.4 1.11.4" "1.5.0 3.12 1.26.4 1.13.1" \
            "1.6.0 3.12 - -" "1.7.0 3.12 - -" "1.8.0 3.12 - -" "1.9.0 3.12 - -" "1.9.1 3.12 - -"; do
  set -- $spec; uv venv -q --python $2 v_$1
  if [ "$3" = "-" ]; then uv pip install -q --python v_$1/bin/python "scikit-learn==$1"
  else uv pip install -q --python v_$1/bin/python "scikit-learn==$1" "numpy==$3" "scipy==$4"; fi
  v_$1/bin/python -I probe.py dir > probes/dir_$1.json
done
# names.json = union of dir and submodules per object; for every release: v_X/bin/python -I probe.py get names.json > probes/get_X.json
# want_X.json = names X has and the next release read does not; v_X/bin/python -I msg_probe.py want_X.json > probes/msg_X.json
python3 -I pre22.py sk.git > pre22.json
python3 -I build_page.py probes pre22.json pypi.json <repo>/en/sklearn-removed-name-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
