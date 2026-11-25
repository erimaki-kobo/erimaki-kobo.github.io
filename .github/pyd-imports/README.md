# en/pydantic-import-name-version-lookup: how the page is built

fetch.py, names_hist.py, build_data.py, getattr_hist.py and test_data.py come from ../tv-imports. Changes: fetch.py and
pypi_dates.py accept two-part versions (pydantic tags v2.0, v1.8); test_data.py also finds the top-level names in the text
of the migration table and ignores imports inside a def or under TYPE_CHECKING when it checks range edges. mig_hist.py reads
pydantic/_migration.py at each 2.x tag: the moved names still import from the old module (getattr_migration) and are added
to it; the removed names and BaseSettings raise PydanticImportError and go to mig.json for the hints. The tags match the
wheels (blob hashes compared at 1.10.0, 2.0, 2.7.0, 2.14.4). tool.js is read from ../pta-imports.

```
git clone --bare --filter=blob:none https://github.com/pydantic/pydantic pd.git
curl -sS https://pypi.org/pypi/pydantic/json -o pypi.json; python3 -I pypi_dates.py pypi.json > dates.json
python3 -I names_hist.py pd.git dates.json pydantic > h.json
python3 -I getattr_hist.py pd.git h.json pydantic > hga.json
python3 -I mig_hist.py pd.git hga.json > hm.json          # also writes mig.json
python3 -I build_data.py pydantic hm.json dates.json <as-of> out
python3 -I test_data.py pydantic pd.git dates.json hm.json out/pydantic.json pydantic chk.json
python3 -I anchors.py pd.git out/pydantic.json > anchors.json
python3 -I build_page.py out <repo>/en/pydantic-import-name-version-lookup <published> <today> chk.json anchors.json mig.json
node check_browser.js http://127.0.0.1:PORT
```

- Results on 2026-11-25: 59 releases (0.0.2 to 2.14.4), 114 modules, 6,432 module-and-name pairs; 469 module-release
  names added by mig_hist.py; 197 removed names; 1,158 hints. test_data: 7,988 top-level name-release pairs, 443 edges,
  19,496 definitions in 1,219 file versions; anchors.py 19 checks; check_browser 10 lookups x 2 widths, examples, deep link.
