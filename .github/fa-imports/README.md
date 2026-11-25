# en/flash-attn-import-name-version-lookup: how the page is built

fetch.py, names_hist.py, build_data.py and test_data.py are the ones in ../vllm-imports; getattr_hist.py extends the one in
../vllm-imports (dict values of any kind, sets of strings, `name == "x"` tests, helpers that return a dict literal; it found
no table-driven __getattr__ here). anchors.py checks the facts the page names by plain-text
search in the tags; det.py reads whether flash_attn_varlen_func takes deterministic= at a few tags. tool.js is read from
../pta-imports.

```
git clone --bare --filter=blob:none https://github.com/Dao-AILab/flash-attention fa.git
curl -sS https://pypi.org/pypi/flash-attn/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
python3 -I names_hist.py fa.git dates.json flash_attn > hist.json
python3 -I getattr_hist.py fa.git hist.json flash_attn > hist_ga.json
python3 -I build_data.py flash_attn hist_ga.json dates.json <as-of> out
python3 -I test_data.py flash_attn fa.git dates.json hist_ga.json out/flash_attn.json flash_attn chk.json
python3 -I anchors.py fa.git out/flash_attn.json > anchors.json; python3 -I det.py fa.git > det.json
python3 -I build_page.py out <repo>/en/flash-attn-import-name-version-lookup <published> <today> chk.json anchors.json det.json
node check_browser.js http://127.0.0.1:PORT
```

- Results on 2026-11-25: 12 releases (0.2.1 to 2.8.3, PyPI has sdists only), 24 top-level names, 91 modules (7 gone),
  1,652 module-and-name pairs. test_data: 239 top-level name-release pairs, 1,742 definitions in 251 file versions;
  anchors.py 10 checks; check_browser 8 lookups x 2 widths, examples, deep link.
