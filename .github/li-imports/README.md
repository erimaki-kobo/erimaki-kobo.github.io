# en/llama-index-import-name-version-lookup: how the page is built

fetch.py, names_hist.py, build_data.py, test_data.py, getattr_hist.py and merge_hist.py come from ../vllm-imports and
../lc-imports. The git tags are not the published packages (v0.10.0 exports Settings, the 0.10.0 wheel does not), so
wheel_repo.py reads every release's py3 wheel from PyPI by HTTP range requests and commits it to a local git repo tagged
v<version>; names_hist.py then reads those repos. llama-index 0.10+ is a namespace package, so llama_index/core is read and
prefix_core.py puts "core." in front of its modules. tool.js is read from ../pta-imports.

```
curl -sS https://pypi.org/pypi/llama-index/json -o pypi_li.json; curl -sS https://pypi.org/pypi/llama-index-core/json -o pypi_core.json
python3 -I ../tf-imports/pypi_dates.py pypi_li.json > dates.json; python3 -I ../tf-imports/pypi_dates.py pypi_core.json > dates_core.json
EVERY=1 python3 -I wheel_repo.py pypi_li.json llama_index 0.7.0 0.10.0 old.git > wheels_old.json
EVERY=1 python3 -I wheel_repo.py pypi_core.json llama_index/core 0.10.0 - core.git > wheels_core.json
python3 -I names_hist.py old.git dates.json llama_index --every-release > h0.json
python3 -I names_hist.py core.git dates_core.json llama_index/core --every-release > h1.json
python3 -I prefix_core.py h1.json > h1p.json; python3 -I merge_hist.py h0.json h1p.json > h.json
python3 -I merge_dates.py dates.json dates_core.json > dates_m.json
python3 -I build_data.py llama_index h.json dates_m.json <as-of> out
python3 -I test_data.py llama_index old.git dates.json h0.json p0/llama_index.json llama_index chk0.json   # p0, p1: build_data per part
python3 -I test_data.py llama_index core.git dates_core.json h1.json p1/llama_index.json llama_index/core chk1.json
python3 -I anchors.py pypi_li.json pypi_core.json out/llama_index.json > anchors.json
git --git-dir li.git show v0.14.26:llama-index-core/llama_index/core/command_line/mappings.json > mappings.json   # li.git: blobless clone of run-llama/llama_index
python3 -I build_page.py out <repo>/en/llama-index-import-name-version-lookup <published> <today> chk0.json chk1.json anchors.json mappings.json
node check_browser.js http://127.0.0.1:PORT
```

- Results on 2026-11-25: 319 releases (llama-index 0.7.0 to 0.9.48, llama-index-core 0.10.0 to 0.14.26), 1,362 modules
  (882 gone), 24,694 module-and-name pairs, 580 hints from mappings.json. test_data: 37,235 top-level name-release pairs,
  31,574 definitions in 7,397 file versions; anchors.py 14 checks; check_browser 11 lookups x 2 widths, examples, deep link.
