# en/openai-python-import-name-version-lookup: how the page is built

Shared scripts (as in ../lc-imports) plus proxy_hist.py: from 1.2.0, `openai/__init__.py` star-imports
`lib/_old_api.py`, which binds the 0.x names (ChatCompletion, Completion, ...) to placeholders in a loop; proxy_hist reads
its SYMBOLS list at each release and lists the names under "proxies". 0.x lives in `openai/`, 1.x and later in
`src/openai/`, so the two are read separately and merged. tool.js is read from ../pta-imports (window.LOOKUP_PROXY_MSG is
set by the page). A vendored six.py also defines a `_LazyModule`; names_hist only follows the package's own tables.

```
git clone --bare --filter=blob:none https://github.com/openai/openai-python oa.git
curl -sS https://pypi.org/pypi/openai/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
TAG_BELOW=1.0.0 python3 -I names_hist.py oa.git dates.json openai > h0.json
TAG_MIN=1.0.0 python3 -I names_hist.py oa.git dates.json src/openai > h1.json
python3 -I merge_hist.py h0.json h1.json > h.json
python3 -I proxy_hist.py oa.git h.json > h_p.json
python3 -I build_data.py openai h_p.json dates.json <as-of> out
python3 -I test_data.py openai oa.git dates.json h_p.json out/openai.json "openai|1.=src/openai|2.=src/openai|3.=src/openai" chk.json
python3 -I build_page.py out <repo>/en/openai-python-import-name-version-lookup <published> <today> chk.json
node check_browser.js http://127.0.0.1:8765   # the repo served locally; written-by-hand expectations
```

- build_page.py asserts every fact the prose names (OpenAI/AzureOpenAI/AsyncOpenAI 1.0.0, openai.error gone in 1.0.0,
  ChatCompletion 0.27.0 to 0.28.1 and a placeholder from 1.2.0, 15 placeholders, last 0.x release 0.28.1,
  types.beta.VectorStore to types.VectorStore at 1.66.0).
- Only the first release of each minor version (and the newest) is read.
