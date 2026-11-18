# en/datasets-import-name-version-lookup: how the page is built

The scripts are the ones in ../pta-imports (fetch.py, names_hist.py, build_data.py, test_data.py; tool.js is read from
there), copied here as they were used; build_page.py is this page's. Nothing is installed, imported or run.

```
git clone --bare --filter=blob:none https://github.com/huggingface/datasets datasets.git
curl -sS https://pypi.org/pypi/datasets/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
python3 -I names_hist.py datasets.git dates.json src/datasets > hist.json
python3 -I build_data.py datasets hist.json dates.json <today> out
python3 -I test_data.py datasets datasets.git dates.json hist.json out/datasets.json src/datasets chk.json
python3 -I build_page.py out <repo>/en/datasets-import-name-version-lookup <published> <today> chk.json
node check_browser.js http://127.0.0.1:PORT
```

- datasets tags have no `v` (2.21.0, not v2.21.0). build_page.py asserts the facts the prose names (30 names gone in
  3.0.0, 2.21.0 the last with them, set_caching_enabled 1.3.0 to 2.21.0, List from 4.0.0, SchemaInferenceError from 2.7.0).
- Results on 2026-11-18: 60 releases (1.0.0 to 5.2.0), 237 top-level names (119 gone), 189 modules (36 gone), 4,933
  module-and-name pairs. test_data: 7,032 top-level name-release pairs as text, 23,287 definitions by regular expression,
  8 anchors; check_browser 12 lookups x 2 widths.
