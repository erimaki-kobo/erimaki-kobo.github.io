# en/diffusers-import-name-version-lookup: how the page is built

Nothing is installed, imported or run; release tags are read as text with `ast`. `pypi_dates.py` is the one in ../tf-imports.

```
git clone --bare --filter=blob:none https://github.com/huggingface/diffusers diffusers.git
curl -sS https://pypi.org/pypi/diffusers/json -o pypi_diffusers.json; python3 -I ../tf-imports/pypi_dates.py pypi_diffusers.json > dates.json
python3 -I names_hist.py diffusers.git dates.json > names_hist.json          # about 1 minute; fetches ~8,000 blobs the first time
python3 -I build_data.py names_hist.json dates.json <today> out
python3 -I test_data.py diffusers.git dates.json names_hist.json out checks.json   # -v lists the names upstream keeps in one place only
python3 -I build_page.py out <repo>/en/diffusers-import-name-version-lookup <published> <today> checks.json
node check_browser.js http://127.0.0.1:PORT        # serve the repository root; LATEST_RELEASE=x.y.z after a new release
```

- `names_hist.py` reads every `.py` file under src/diffusers at the first release of each minor version. Lazy packages
  (`_LazyModule`, from 0.21.0): the `_import_structure` table along the path with the backends installed, the last key that
  lists a name wins (as in `_LazyModule.__init__`), and each entry is followed to the file it names. Entries that do not
  resolve go to "stale". It stops on a statement about the table it does not know, and if `_LazyModule.__getattr__` starts
  to look at the spelling of a name.
- Names bound by importing other packages are kept (`from diffusers.models.embeddings import nn` does import), so "never
  there" is true for a module. where.json has definitions only, to say where a name lives now.
- `build_page.py` asserts the facts the prose states (FluxPipeline 0.30.0, randn_tensor 0.21.0, ONNX 0.43.0, Flax 0.40.0,
  k-diffusion 0.37.0, PositionNet 0.26.0, the stale top-level entry 0.25.0 to 0.42.x). Replacements in `HINTS` and `GROUPS`
  are quoted from the source of the last release that had the name.
- Results on 2026-11-18: 43 releases (0.0.2 to 0.43.0), 798 top-level names (51 gone), 1,380 modules (228 gone), 37,577
  module-and-name pairs, 15 stale entries; test_data: type-checking copy identical in 1,713 of 2,008 lazy packages (49 names
  upstream lists in one place only), 12,039 top-level name-and-release pairs found as text, 60,015 definitions found by a
  regular expression, 23 anchors; check_browser 22 lookups x 2 widths.
- Not done: nothing was installed. The page is not on the daily refresh; rebuild after a new minor release of diffusers.
