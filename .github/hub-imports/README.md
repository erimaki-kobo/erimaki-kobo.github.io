# en/huggingface-hub-import-name-version-lookup: how the page is built

Nothing is installed, imported or run; release tags are read as text with `ast`. `pypi_dates.py` is the one in ../tf-imports.

```
for r in huggingface/huggingface_hub huggingface/diffusers UKPLab/sentence-transformers gradio-app/gradio huggingface/datasets huggingface/peft; do
  git clone --bare --filter=blob:none https://github.com/$r $(basename $r).git; done          # under a minute in total
for n in huggingface-hub diffusers sentence-transformers gradio datasets peft; do
  curl -sS https://pypi.org/pypi/$n/json -o pypi_$n.json; python3 -I ../tf-imports/pypi_dates.py pypi_$n.json > dates_$n.json; done
python3 -I names_hist.py huggingface_hub.git dates_huggingface-hub.json > names_hist.json
python3 -I downstream_hist.py diffusers.git dates_diffusers.json src/diffusers > ds_diffusers.json
python3 -I downstream_hist.py sentence-transformers.git dates_sentence-transformers.json sentence_transformers > ds_sentence-transformers.json
python3 -I downstream_hist.py gradio.git dates_gradio.json gradio gradio > ds_gradio.json       # 4th argument: the tag prefix in gradio@X.Y.Z
python3 -I downstream_hist.py datasets.git dates_datasets.json src/datasets > ds_datasets.json
python3 -I downstream_hist.py peft.git dates_peft.json src/peft > ds_peft.json
python3 -I build_data.py names_hist.json dates_huggingface-hub.json <today> diffusers=ds_diffusers.json sentence-transformers=ds_sentence-transformers.json \
  gradio=ds_gradio.json datasets=ds_datasets.json peft=ds_peft.json > data.json
python3 -I test_data.py huggingface_hub.git names_hist.json data.json checks.json diffusers=diffusers.git:src/diffusers:ds_diffusers.json \
  sentence-transformers=sentence-transformers.git:sentence_transformers:ds_sentence-transformers.json gradio=gradio.git:gradio:ds_gradio.json \
  datasets=datasets.git:src/datasets:ds_datasets.json peft=peft.git:src/peft:ds_peft.json
python3 -I build_page.py data.json <repo>/en/huggingface-hub-import-name-version-lookup <published> <today> checks.json
node check_browser.js http://127.0.0.1:PORT        # serve the repository root; LATEST_RELEASE=x.y.z after a new hub release
```

- `names_hist.py` stops if a `__getattr__` of the hub starts looking at the spelling of a name (a rule the reading would miss),
  and if `__init__.py` yields no names (0.8.x and 0.9.x pass the table straight to `_attach(...)`; a new form would show up here).
- `build_page.py` asserts the facts the prose states (cached_download gone in 0.26.0; HfFolder, Repository, InferenceApi gone in
  1.0.0; diffusers 0.1.0-0.28.x, sentence-transformers 2.0.0-2.2.x, gradio 4.9.0-5.7.x, datasets 1.13.0-2.15.x). Replacements in
  `HINTS` are quoted from the deprecation message or docstring of the last release that had the name.
- gradio: versions below 3.0.0 are left out (`MIN_VERSION` in build_data.py); the old tags of that repository do not line up
  with the PyPI package. `constants` and `insecure_hashlib` are submodules, not names, and are ignored (`not_names` in data.json).
- Results on 2026-11-17: hub 75 releases (0.0.1 to 2.4.0), 568 top-level names, 49 gone; 331 library releases; test_data: static
  copy identical in 66 of 66 lazy releases, 8 runs confirmed by plain-text search, 16 anchors; check_browser 24 lookups x 2 widths.
- Not done: nothing was installed. More libraries (transformers, timm, open_clip, accelerate) could be added with one
  `downstream_hist.py` line each; transformers needs all `.py` blobs of 100 releases, so it was left out.
- 2026-11-25: imports under an `if` on the installed hub version or an `is_*_available()` check now count as soft
  (datasets 4.8.0 to 5.0.x gate `BucketNotFoundError` on `config.HF_HUB_VERSION >= 1.6.0`; the table had said they need hub 1.5.0).
  Checked by installing: datasets 5.0.1 imports with hub 0.36.0; datasets 5.1.0 with hub 1.4.1 or 0.36.0 fails with
  "cannot import name 'BucketNotFoundError' from 'huggingface_hub.errors'". peft 0.22.0 added.
