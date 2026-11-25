# en/gradio-import-name-version-lookup: how the page is built

fetch.py, names_hist.py, build_data.py, test_data.py and merge_hist.py are the ones in ../oa-imports, changed to read
tags of the form `gradio@X.Y.Z` (`re.split("==|@", t)`); test_data.py skips cli/commands/components/_docs_utils.py, which
builds Python source in f-strings. tool.js is read from ../pta-imports. gradio's git tags start at gradio@3.41.0 (the
older v3.x tags do not line up with PyPI), so 3.0 to 3.40 are read from the PyPI wheels: early_repo.py fetches the
gradio/**/*.py of the first release of each of those minors by HTTP range requests and commits them to a local repository
tagged the same way. add_finals.py then lists every PyPI release below 3.41.0, so "last release with it" is the real last
patch. anchors.py checks the facts the page names against the wheels (a source independent of the git tags).

```
git clone --bare --filter=blob:none https://github.com/gradio-app/gradio gradio.git
curl -sS https://pypi.org/pypi/gradio/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
python3 -I early_repo.py pypi.json 3.41.0 early.git > early_wheels.json                      # about 30 s
TAG_PREFIX=gradio@ python3 -I names_hist.py early.git dates.json gradio > h0.json
TAG_PREFIX=gradio@ python3 -I names_hist.py gradio.git dates.json gradio > h1.json            # about 45 s
python3 -I merge_hist.py h0.json h1.json > m.json; python3 -I add_finals.py m.json dates.json 3.41.0 > h.json
TAG_PREFIX=gradio@ python3 -I build_data.py gradio h.json dates.json <as-of> out
# checks, on each part separately (test_data.py expects the data of one repository):
TAG_PREFIX=gradio@ python3 -I build_data.py gradio h1.json dates.json <as-of> p1; TAG_PREFIX=gradio@ python3 -I build_data.py gradio h0.json dates.json <as-of> p0
TAG_PREFIX=gradio@ python3 -I test_data.py gradio gradio.git dates.json h1.json p1/gradio.json gradio chk1.json
TAG_PREFIX=gradio@ python3 -I test_data.py gradio early.git dates.json h0.json p0/gradio.json gradio chk0.json
python3 -I anchors.py pypi.json out/gradio.json > anchors.json
python3 -I build_page.py out <repo>/en/gradio-import-name-version-lookup <published> <today> chk1.json chk0.json anchors.json
node check_browser.js http://127.0.0.1:PORT        # the repository root served locally
```

- build_page.py asserts the facts the prose names (21 top-level names and gradio.components.IOComponent gone in 4.0.0,
  3.50.2 the last with them; make_waveform and HuggingFaceDatasetSaver gone in 5.0.0; ChatInterface 3.37.0, ChatMessage
  4.38.0, http_server 4.23.0, Sidebar 5.14.0 and the other additions in its table).
- Results on 2026-11-25: 170 releases (3.0.1 to 6.32.0), 246 top-level names (41 gone), 213 modules (32 gone), 6,066
  module-and-name pairs. test_data: 26,624 top-level name-release pairs as text, 29,937 definitions in 3,331 file
  versions; anchors.py 22 release checks against the wheels; check_browser 11 lookups x 2 widths, examples, deep link.
