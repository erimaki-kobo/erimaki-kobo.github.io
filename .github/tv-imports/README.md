# en/torchvision-import-name-version-lookup: how the page is built

fetch.py, names_hist.py, build_data.py, getattr_hist.py and test_data.py come from ../fa-imports (test_data.py skips the
files fb_fix.py removed); wheel_repo.py from ../li-imports (falls back to old CPython wheels). The data is read from the
PyPI wheels (first release of every minor, plus the latest; they match the git tags except version.py and a prototype
package in 0.16.0 and 0.22.0). fb_fix.py drops what torchvision 0.26+ imports from pytorch.vision.fb (Meta-internal, not on
PyPI): names inside try/except ImportError, and io.video from 0.28.0, which imports it at module level. torch_pins.py
reads the torch requirement of every release's wheel. tool.js is read from ../pta-imports. wheels.json has the wheel
file names and sha256.

```
curl -sS https://pypi.org/pypi/torchvision/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
python3 -I wheel_repo.py pypi.json torchvision 0.3.0 - whl.git > wheels.json
python3 -I names_hist.py whl.git dates.json torchvision > hw.json
python3 -I getattr_hist.py whl.git hw.json torchvision > hw_ga.json; python3 -I fb_fix.py whl.git hw_ga.json > hw_fx.json
python3 -I build_data.py torchvision hw_fx.json dates.json <as-of> out
python3 -I test_data.py torchvision whl.git dates.json hw_fx.json out/torchvision.json torchvision chk.json
python3 -I anchors.py pypi.json out/torchvision.json > anchors.json; python3 -I torch_pins.py pypi.json > torch_pins.json
python3 -I build_page.py out <repo>/en/torchvision-import-name-version-lookup <published> <today> chk.json anchors.json torch_pins.json
node check_browser.js http://127.0.0.1:PORT
```

- Results on 2026-11-25: 28 releases (0.3.0 to 0.29.2; 0.11.0 and 0.15.0 are yanked), 252 modules (69 gone), 7,344
  module-and-name pairs, 73 hints. test_data: 652 top-level name-release pairs, 14,932 definitions in 1,706 file versions
  (3 skipped by fb_fix); anchors.py 19 checks; torch pins for 51 releases; check_browser 10 lookups x 2 widths, examples,
  deep link.
