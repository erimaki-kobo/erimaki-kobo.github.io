# en/langchain-import-name-version-lookup: how the page is built

Shared scripts (as in ../st-imports; fetch.py here reads monorepo tags with TAG_PREFIX / TAG_MIN / TAG_BELOW) plus:
merge_hist.py (langchain 0.x and 1.x live in different folders), getattr_hist.py (names a module serves through a
module-level __getattr__: __all__, DEPRECATED_LOOKUP, _dynamic_imports, create_importer(...); names forwarded to another
package, langchain_community, are marked "deferred" with their target), check_getattr.py (regex second reading of those).
tool.js is read from ../pta-imports (window.LOOKUP_SIBLINGS, LOOKUP_PARTIAL, LOOKUP_PIP are set by the page).

```
git clone --bare --filter=blob:none https://github.com/langchain-ai/langchain lc.git
for p in langchain langchain-classic langchain-core; do curl -sS https://pypi.org/pypi/$p/json -o pypi_$p.json; python3 -I ../tf-imports/pypi_dates.py pypi_$p.json > dates_$p.json; done
TAG_PREFIX="" TAG_MIN=0.1.0 TAG_BELOW=0.1.17 python3 -I names_hist.py lc.git dates_langchain.json libs/langchain/langchain --every-release > h_lc01.json
TAG_PREFIX="langchain==" TAG_MIN=0.1.17 TAG_BELOW=1.0.0 python3 -I names_hist.py lc.git dates_langchain.json libs/langchain/langchain --every-release > h_lc03.json
TAG_PREFIX="langchain==" TAG_MIN=1.0.0 python3 -I names_hist.py lc.git dates_langchain.json libs/langchain_v1/langchain --every-release > h_lc1.json
TAG_PREFIX="langchain-classic==" python3 -I names_hist.py lc.git dates_langchain-classic.json libs/langchain/langchain_classic --every-release > h_cl.json
TAG_PREFIX="langchain-core==" python3 -I names_hist.py lc.git dates_langchain-core.json libs/core/langchain_core > h_core.json
python3 -I merge_hist.py h_lc01.json h_lc03.json h_lc1.json > h_lc_m.json
python3 -I getattr_hist.py lc.git h_lc_m.json "libs/langchain/langchain|1.=libs/langchain_v1/langchain" > h_lc.json
python3 -I getattr_hist.py lc.git h_cl.json libs/langchain/langchain_classic > h_cl2.json
python3 -I getattr_hist.py lc.git h_core.json libs/core/langchain_core > h_core2.json
python3 -I build_data.py langchain h_lc.json dates_langchain.json <today> out     # and langchain_classic h_cl2, langchain_core h_core2
python3 -I test_data.py langchain lc.git dates_langchain.json h_lc.json out/langchain.json "libs/langchain/langchain|1.=libs/langchain_v1/langchain" chk_langchain.json
python3 -I check_getattr.py lc.git h_lc.json "libs/langchain/langchain|1.=libs/langchain_v1/langchain"   # sum the three runs for the page
python3 -I build_page.py out <repo>/en/langchain-import-name-version-lookup <published> <today> chk_langchain.json chk_langchain_classic.json chk_langchain_core.json <getattr names>
```

- Results on 2026-11-18: langchain 130 releases (0.1.0 to 1.5.0, every release), langchain-classic 9 (1.0.0 to 1.0.8),
  langchain-core 13 (0.1.47 to 1.8.2, first of each minor); 35,388 module-and-name pairs; 1,243 names forwarded to
  langchain_community. Checks: 8,586 top-level pairs as text, 29,928 definitions by regular expression, 161,854
  __getattr__-served names by regular expression (summed over releases), 17 anchors; check_browser 12 lookups x 2 widths.
- langchain 0.0.x is not read. Not on the daily refresh.
