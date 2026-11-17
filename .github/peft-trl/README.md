# en/peft-trl-args-version-lookup: how the page is built

Question: `X.__init__() got an unexpected keyword argument 'y'` for PEFT configs (adapter_config.json keys),
Transformers `TrainingArguments` / `Trainer`, and TRL configs / trainers. The page embeds its data.

## Rebuild (when PEFT, TRL or Transformers tags a final release; about 2 minutes)

```
mkdir hist && cd hist
git clone --bare https://github.com/huggingface/peft peft.git
git clone --bare https://github.com/huggingface/trl trl.git
git clone --bare --filter=blob:none https://github.com/huggingface/transformers transformers.git
cd ..
python3 -I .github/peft-trl/args_hist.py hist > args_hist.json            # about 30 s; fetches the Transformers blobs in one batch
python3 -I .github/peft-trl/build_page.py args_hist.json out 2026-11-17 <modified YYYY-MM-DD>
python3 -I .github/peft-trl/test_data.py args_hist.json hist             # independent check, regex on the source text
node .github/peft-trl/check_browser.js file://$PWD/out/index.html         # 28 cases x 2 widths
cp out/index.html en/peft-trl-args-version-lookup/index.html              # and bump lastmod in sitemap.xml
```

## What to know before changing it

- `args_hist.py` reads classes with `ast`. A config class counts its own dataclass fields plus those of base classes
  in the same package; a class with its own `__init__` counts that signature. `@deprecate_kwarg` names are aliases.
- TRL configs extend `transformers.TrainingArguments`. A name that a TRL config stops re-declaring is not removed if
  `TrainingArguments` still has it (`neftune_noise_alpha`, `gradient_accumulation_steps`); `build_page.py` and
  `tool.js` both handle that. The TRL base config (`BaseConfig` in v0.29.x, `_BaseConfig` from v1.0.0) is resolved as
  an ordinary base class.
- `build_page.py` asserts every release named in the prose and every curated replacement (the `HV` list) against the
  data. If an assert fails after a new release, the facts changed: fix the prose, not the assert. A replacement that
  has itself been removed stops the build.
- Replacement texts come from the deprecation message in the last release that had the old name
  (`src/transformers/training_args.py` `__post_init__`, TRL trainers). Re-read them when adding rows.
- "PEFT v0.14.0 ignores unknown keys with a warning" is found by `peft_forward()` (first tag whose
  `src/peft/config.py` catches the TypeError); the commit is 85e3202a (#2038).
- `check_browser.js` expectations were written by hand from a table produced earlier by a different script
  (project doc claude/kiban/年表_設定の引数.md), not from this page's data. When a newest-release number in an
  expectation changes (for example "Accepted by PEFT v0.21.3"), update that string.

## Checks on 2026-11-17 (first publication)

- `test_data.py`: 342/342 (seven classes, up to 18 arguments each, present at first and last release, absent outside).
- `check_browser.js`: ALL PASS (56 cases), no horizontal overflow at 375 px, no page errors.
- HTML parsed with `html.parser`; one h1; ASCII only; no external scripts; JSON-LD parses
  (TechArticle, WebApplication, Dataset, FAQPage, BreadcrumbList).
- Not done: nothing was executed against real libraries. Changed defaults and values are out of scope.

## Why this beats what ranks today (checked 2026-11-17)

Search results for the LoraConfig error are forum threads, Space error logs and PEFT's troubleshooting entry, which
says to upgrade or delete the key. None gives the release each key needs, reads an adapter_config.json, or explains
that PEFT 0.14.0 and later only warn.
