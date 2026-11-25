# en/numpy-removed-attribute-lookup: how the page is built

np_attrs.py reads, at the first release of every minor from 1.16 plus the latest, the tables numpy's module __getattr__
answers from (evaluated with stand-ins, no numpy code runs). names.json is every name in those tables plus a few removed
without an entry. probe.py is run inside each installed release; verify.py checks that the tables predict what the release
did (609 entries, no mismatch on 2026-11-25). removal_msgs.py reads the deprecation warning of the names removed without a
message. The probe results are in probes/.

```
git clone --bare --filter=blob:none https://github.com/numpy/numpy np.git; curl -sS https://pypi.org/pypi/numpy/json -o pypi.json
python3 -I np_attrs.py np.git pypi.json > np_attrs.json
for spec in "1.19.5 3.9" "1.20.0 3.9" "1.21.0 3.9" "1.22.0 3.10" "1.23.0 3.10" "1.24.0 3.11" "1.25.0 3.11" "1.26.0 3.11" \
            "2.0.0 3.12" "2.1.0 3.12" "2.2.0 3.12" "2.3.0 3.12" "2.4.1 3.12" "2.5.0 3.12" "2.5.5 3.12"; do
  set -- $spec; uv venv -q --python $2 venv_$1; uv pip install -q --python venv_$1/bin/python "numpy==$1"
  venv_$1/bin/python -I probe.py names.json > probes/$1.json
done
python3 -I verify.py np_attrs.json probes > verify.json; python3 -I removal_msgs.py np.git > removal_msgs.json
python3 -I build_page.py np_attrs.json probes verify.json removal_msgs.json pypi.json <repo>/en/numpy-removed-attribute-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```

A new NumPy minor: add its first release to the loop (with a Python it has wheels for), rerun, and read the asserts in
build_page.py that fail.
