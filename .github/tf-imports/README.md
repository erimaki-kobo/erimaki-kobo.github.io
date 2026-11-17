# en/transformers-import-name-version-lookup: how the page is built

Nothing from transformers is installed, imported or run; the release tags are read as text with `ast`.

```
git clone --bare --filter=blob:none https://github.com/huggingface/transformers tf.git      # 5 s, 80 MB; grows to ~130 MB
curl -sS https://pypi.org/pypi/transformers/json -o pypi.json
python3 -I .github/tf-imports/pypi_dates.py pypi.json > tf_pypi.json                         # dates, yanked releases
python3 -I .github/tf-imports/names_hist.py tf.git tf_pypi.json > names_hist.json            # ~1.5 min
python3 -I .github/tf-imports/test_data.py tf.git names_hist.json checks.json                # second reading; ~1 min
# which versions of other libraries import a removed name (same script as the huggingface_hub page; clones and dates as in ../hub-imports/README.md)
export TARGET_MODS=transformers:top,transformers.utils:utils,transformers.file_utils:file_utils
for spec in "diffusers src/diffusers" "sentence-transformers sentence_transformers" "peft src/peft" "accelerate src/accelerate" "optimum optimum" "trl trl"; do
  set -- $spec; python3 -I .github/hub-imports/downstream_hist.py $1.git dates_$1.json $2 > ds_$1.json; done
python3 -I .github/tf-imports/build_data.py names_hist.json tf_pypi.json <today> diffusers=ds_diffusers.json sentence-transformers=ds_sentence-transformers.json \
  peft=ds_peft.json accelerate=ds_accelerate.json optimum=ds_optimum.json trl=ds_trl.json > data.json
python3 -I .github/tf-imports/test_users.py data.json checks.json diffusers=diffusers.git:src/diffusers:ds_diffusers.json ...   # lib=<clone>:<package dir>:<ds json>, all six
python3 -I .github/tf-imports/build_page.py data.json en/transformers-import-name-version-lookup <published> <today> checks.json
python3 -m http.server 8771 &   # repository root
node .github/tf-imports/check_browser.js http://127.0.0.1:8771        # LATEST_RELEASE=x.y.z when the newest release changed
```

- `names_hist.py` reads the first release of every minor version that pip can install (not yanked) plus the newest release:
  eager `__init__.py` up to 4.1.x, `_import_structure` from 4.2.0, plus the `__all__` of every file under `models/` where
  `__init__.py` calls `define_import_structure` (4.52.1 on). For 5.x it records which alias rules `_LazyModule.__getattr__`
  has and the `SLOW_TO_FAST_CONVERTERS` table. It asserts that the method looks at no name ending other than the four it
  knows; if upstream adds a rule, the build stops there and the rule has to be modelled in `build_data.py` (`alias_target`).
- `build_page.py` asserts the facts the prose names (AdamW 2.0.0-4.49.x, the agents gone in 4.52.1, 24 names gone in 5.20.0,
  the alias of BertTokenizerFast ...). A release that changes one stops the build; read the release and fix the prose.
  The replacements in `HINTS` are quoted from the deprecation message in the last release that had the name
  (`git show vX:src/transformers/<file> | grep -n deprecat`). Add one only with such a message.
- If the newest release is a patch of an already listed minor, `build_data.py` stops; nothing to rebuild.
- `verify_installed.py` compares the reading with an installed package (`pip install --target`). It could not be run in the
  chat container on 2026-11-17 (running the installed package was refused), so the page says "nothing was installed".
  Running it on a machine that allows it would be the stronger check, especially for the 5.x alias rules.
- Results on 2026-11-17: 100 releases (2.0.0 to 5.23.0), 5,893 top-level names; test_data: 80 lazy releases, no mirrored name
  missing, `__all__` 4,932 files identical, 19 anchors; check_browser: 30 lookups x 2 widths.
- 2026-11-18: added "users" (44 runs over 38 names, all confirmed by plain-text search; check_browser 34 lookups x 2 widths). No
  "which transformers does library X need" table on purpose: diffusers and optimum load most files on demand, so the range
  computed from all files contradicts itself there (a file needing >= 5.0.0 next to one needing < 5.0.0).
