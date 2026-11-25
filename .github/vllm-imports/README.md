# en/vllm-import-name-version-lookup: how the page is built

fetch.py, names_hist.py, build_data.py and test_data.py are the ones in ../oa-imports (test_data.py has an empty anchor
list for vllm; anchors.py checks the facts against the PyPI wheels instead). getattr_hist.py adds the names a module serves
through a module-level __getattr__ from a table of strings (vllm/__init__.py MODULE_ATTRS, vllm/utils/__init__.py
_DEPRECATED_MAPPINGS in 0.12 and 0.13, the lazy classes of vllm.transformers_utils.configs and .processors). tool.js is read
from ../pta-imports.

```
git clone --bare --filter=blob:none https://github.com/vllm-project/vllm vllm.git          # about 1 minute
curl -sS https://pypi.org/pypi/vllm/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
python3 -I names_hist.py vllm.git dates.json vllm > hist.json                                  # about 3.5 minutes
python3 -I getattr_hist.py vllm.git hist.json vllm > hist_ga.json                              # about 1 minute
python3 -I build_data.py vllm hist_ga.json dates.json <as-of> out
python3 -I test_data.py vllm vllm.git dates.json hist_ga.json out/vllm.json vllm chk.json
python3 -I anchors.py pypi.json out/vllm.json > anchors.json                                   # range requests, under a minute
python3 -I build_page.py out <repo>/en/vllm-import-name-version-lookup <published> <today> chk.json anchors.json hist_ga.json
node check_browser.js http://127.0.0.1:PORT        # the repository root served locally
```

- The TRL table was read from huggingface/trl release tags 0.14.0 to 1.18.2 (`git grep` of the vllm imports in trl/, the
  vllm extra in setup.cfg and pyproject.toml); the import blocks of 0.26.2, 0.27.0, 0.27.2 and 0.28.0 were read by hand.
  Rerun that when a TRL release changes its vllm imports.
- build_page.py asserts every span the prose names (GuidedDecodingParams 0.7.0 to 0.11.x, vllm.utils.get_open_port to 0.13.x
  with the alias in 0.12 and 0.13 seen by getattr_hist.py, the 0.12.0 moves, entrypoints.openai.protocol gone in 0.15.0,
  ErrorResponse in serve.engine.protocol from 0.29.0, the V0 worker gone in 0.11.0).
- Results on 2026-11-25: 34 releases (0.1.0 to 0.34.0), 115 top-level names (29 gone), 4,336 modules (973 gone), 122,592
  module-and-name pairs (3.8 MB JSON, about 0.9 MB gzipped). test_data: 2,512 top-level name-release pairs as text,
  206,105 definitions in 22,937 file versions; anchors.py 18 release checks against the wheels; check_browser 11 lookups x 2
  widths, examples, deep link.
