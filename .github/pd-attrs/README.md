# en/pandas-removed-attribute-lookup: how the page is built

probe.py runs inside an installed pandas: `dir` lists the public names of the pandas module, DataFrame, Series, Index,
DatetimeIndex, Timestamp, the groupby objects and the .str accessor; `get` runs getattr for the union of names over all
releases. msg_probe.py runs in the last release before each removal and reads the deprecation text from the installed
source (inspect + ast; fallback: a warnings.warn string elsewhere in pandas that names the attribute before the word
"deprecat"). build_page.py adds our own note for the few with no text (NOTE) and marks them on the page. Results in probes/.

```
curl -sS https://pypi.org/pypi/pandas/json -o pypi.json
for spec in "0.25.3 3.8 1.19.5" "1.0.0 3.8 1.19.5" "1.1.0 3.8 1.19.5" "1.2.0 3.9 1.19.5" "1.3.0 3.9 1.21.6" "1.4.0 3.10 1.22.4" \
            "1.5.0 3.10 1.23.5" "2.0.0 3.11 1.24.4" "2.1.0 3.11 1.26.4" "2.2.0 3.12 1.26.4" "2.3.0 3.12 2.2.6" "3.0.0 3.12 -" "3.1.0 3.12 -" "3.1.1 3.12 -"; do
  set -- $spec; uv venv -q --python $2 v_$1
  if [ "$3" = "-" ]; then uv pip install -q --python v_$1/bin/python "pandas==$1"; else uv pip install -q --python v_$1/bin/python "pandas==$1" "numpy==$3"; fi
  v_$1/bin/python -I probe.py dir > probes/dir_$1.json
done
# names.json = union of the dir lists per object; then for every release: v_X/bin/python -I probe.py get names.json > probes/get_X.json
# want_X.json = names that X has and the next release read does not; v_X/bin/python -I msg_probe.py want_X.json > probes/msg_X.json
python3 -I build_page.py probes pypi.json <repo>/en/pandas-removed-attribute-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
