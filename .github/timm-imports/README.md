# en/timm-import-name-version-lookup: how the page is built

fetch.py, names_hist.py, build_data.py and test_data.py are the shared ones (as in ../pta-imports) with two additions made
for timm: `--every-release` (timm ships changes in 1.0.x patches, so every tagged release is read, not one per minor) and
absolute star imports inside the library (`from timm.layers.activations import *`). tool.js is read from ../pta-imports.

```
git clone --bare --filter=blob:none https://github.com/huggingface/pytorch-image-models timm.git
curl -sS https://pypi.org/pypi/timm/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
python3 -I names_hist.py timm.git dates.json timm --every-release > hist.json
python3 -I build_data.py timm hist.json dates.json <today> out
python3 -I test_data.py timm timm.git dates.json hist.json out/timm.json timm chk.json
python3 -I check_mapping.py timm.git hist.json          # then add "CHK_ML_RELEASES": <n> to chk.json
python3 -I build_page.py out <repo>/en/timm-import-name-version-lookup <published> <today> chk.json
node check_browser.js http://127.0.0.1:PORT
```

- Results on 2026-11-18: 51 tagged releases (0.1.1 to 1.0.31; the even 0.1.x and 0.3.0-0.3.2 are on PyPI without tags),
  382 modules (79 gone; 65 in 0.9.0), 12,776 module-and-name pairs; test_data 1,090 top-level pairs as text, 43,256
  definitions by regular expression, 8 anchors; check_mapping 38 releases; check_browser 10 lookups x 2 widths.
- The new reader was rerun on peft, trl and datasets: same names. accelerate gains its 0.0.1 tag (no `v`), nothing else.
