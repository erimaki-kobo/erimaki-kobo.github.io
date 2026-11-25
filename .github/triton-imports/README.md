# en/triton-import-name-version-lookup: how the page is built

The triton wheel is not the git tree: the build copies third_party/nvidia and third_party/amd into triton/backends/ and
triton/language/extra/. So wheel_repo.py reads the triton/**/*.py of one Linux x86_64 wheel per release from PyPI (HTTP
range requests) into a local git repository tagged v<version>; wheels.json records each wheel's file name and sha256.
fetch.py, names_hist.py, build_data.py, test_data.py and getattr_hist.py are the ones in ../vllm-imports. anchors.py checks
the facts the page names against the triton git tags. torch_pins.json is the Triton pin of each PyTorch release
(Requires-Dist on PyPI) and the PyTorch releases whose torch/utils/_triton.py imports triton_key, read from the wheels.

```
git clone --bare --filter=blob:none https://github.com/triton-lang/triton triton.git
curl -sS https://pypi.org/pypi/triton/json -o pypi.json; python3 -I ../tf-imports/pypi_dates.py pypi.json > dates.json
python3 -I wheel_repo.py pypi.json 2.0.0 wheels.git > wheels.json                        # about 15 s
python3 -I names_hist.py wheels.git dates.json triton > hist.json
python3 -I getattr_hist.py wheels.git hist.json triton > hist_ga.json
python3 -I add_finals.py hist_ga.json dates.json > hist_f.json
python3 -I build_data.py triton hist_f.json dates.json <as-of> out
python3 -I test_data.py triton wheels.git dates.json hist_ga.json out/triton.json triton chk.json
python3 -I anchors.py triton.git out/triton.json > anchors.json
python3 -I build_page.py out <repo>/en/triton-import-name-version-lookup <published> <today> chk.json anchors.json torch_pins.json
node check_browser.js http://127.0.0.1:PORT
```

- bitsandbytes: 0.40.0 to 0.45.0 import triton.ops.matmul_perf_model in bitsandbytes/triton/int8_matmul_*_dequantize.py
  when Triton is installed (reached from `import bitsandbytes` through bitsandbytes.nn.triton_based_modules); 0.45.1 has
  its own matmul_perf_model. Read with `git grep` on the release tags.
- Results on 2026-11-25: 14 releases (2.0.0 to 3.9.0), 48 top-level names, 187 modules (39 gone), 5,531 module-and-name
  pairs. test_data: 424 top-level name-release pairs as text, 10,635 definitions in 689 file versions; anchors.py 12
  release checks against the git tags; check_browser 10 lookups x 2 widths, examples, deep link.
