# en/sentence-transformers-import-name-version-lookup: how the page is built

The shared scripts (as in ../timm-imports) plus alias_hist.py, which adds the module aliases sentence-transformers installs
at import time: the DEPRECATED_MODULE_PATHS table and its import hook (5.4.0 on) and direct `sys.modules[...]`
assignments (4.0.0 on). Without it, a static reading would call `sentence_transformers.models` gone in 5.4.0, which is
wrong: the old paths still import, with a DeprecationWarning. tool.js is read from ../pta-imports.

```
git clone --bare --filter=blob:none https://github.com/huggingface/sentence-transformers st.git
curl -sS https://pypi.org/pypi/sentence-transformers/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
python3 -I names_hist.py st.git dates.json sentence_transformers > hist.json
python3 -I alias_hist.py st.git hist.json sentence_transformers > hist_a.json
python3 -I build_data.py sentence_transformers hist_a.json dates.json <today> out
python3 -I test_data.py sentence_transformers st.git dates.json hist_a.json out/sentence_transformers.json sentence_transformers chk.json
python3 -I check_aliases.py st.git hist_a.json        # then add "CHK_ALIASES": <n> to chk.json
python3 -I build_page.py out <repo>/en/sentence-transformers-import-name-version-lookup <published> <today> chk.json hist_a.json
node check_browser.js http://127.0.0.1:PORT
```

- Results on 2026-11-18: 34 releases (0.1.0 to 6.3.0), 375 modules (27 gone), 6,679 module-and-name pairs, 133 aliases
  in 6.3.0 (1,100 summed over releases, the same by regular expression); test_data 1,149 top-level pairs as text, 4,645
  definitions by regular expression, 8 anchors; check_browser 9 lookups x 2 widths.
- The pip name differs from the import name: the page sets window.LOOKUP_PIP so pins say sentence-transformers.
