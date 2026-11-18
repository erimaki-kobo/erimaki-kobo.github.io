# en/peft-trl-accelerate-import-name-lookup: how the page is built

Nothing is installed, imported or run. `fetch.py` and `names_hist.py` are the diffusers ones (../df-imports) with the
source root as a third argument (fetch.py here also reads tags without a `v`, as datasets has); `pypi_dates.py` is in
../tf-imports. `tool.js` is shared: a page sets `window.LOOKUP_LIBS` (default peft, trl, accelerate) and `window.PTA_HINTS`.

```
for r in accelerate:src/accelerate peft:src/peft trl:trl; do n=${r%%:*}; root=${r#*:}
  git clone --bare --filter=blob:none https://github.com/huggingface/$n $n.git
  curl -sS https://pypi.org/pypi/$n/json -o pypi_$n.json; python3 -I ../tf-imports/pypi_dates.py pypi_$n.json > dates_$n.json
  python3 -I names_hist.py $n.git dates_$n.json $root > hist_$n.json
  python3 -I build_data.py $n hist_$n.json dates_$n.json <today> out
  python3 -I test_data.py $n $n.git dates_$n.json hist_$n.json out/$n.json $root chk_$n.json
done
python3 -I build_page.py out <repo>/en/peft-trl-accelerate-import-name-lookup <published> <today> chk_peft.json chk_trl.json chk_accelerate.json
node check_browser.js http://127.0.0.1:PORT        # serve the repository root
```

- build_page.py asserts every fact the prose names (DataCollatorForCompletionOnlyLM 0.20.0, setup_chat_format 0.26.0,
  33 names gone in trl 0.29.0, PPOTrainer in trl.experimental.ppo from 0.26.0 to 1.12.x, prepare_model_for_int8_training
  0.10.0, is_npu_available 0.21.0, PartialState 0.17.0, is_tpu_available 0.28.0, is_safetensors_available 0.25.0) and that
  every replacement in HINTS is for a name that is gone. Replacements are quoted from the source of the release before.
- Results on 2026-11-18: peft 23 releases (0.0.1 to 0.21.3), trl 48 (0.2.0 to 1.18.1), accelerate 51 (0.1.0 to 1.16.0);
  14,806 module-and-name pairs; trl 11 stale lazy entries. test_data: trl type-checking copy identical in 214 of 231 lazy
  packages (9 names in one place only), 7,221 top-level name-release pairs as text (star imports followed), 30,884 definitions by regular
  expression (keywords such as `try` left out), 18 anchors; check_browser 17 lookups x 2 widths.
- trl 0.9.2 is on PyPI without a git tag; the 0.9 line is read at 0.9.3. Not on the daily refresh.
