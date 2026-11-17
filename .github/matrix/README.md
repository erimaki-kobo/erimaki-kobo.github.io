# en/vllm-torch-cuda-driver-matrix: how the page is built

`en/vllm-torch-cuda-driver-matrix/matrix.json` is the data (one record per stable vLLM release, oldest first).
`build_page.py` turns it into `index.html`; `style.css` and `tool.js` are embedded as they are.

## When a new vLLM release is tagged

Gather these for the new tag (nothing is installed or run):

| field | where it comes from |
|---|---|
| `date` | `git for-each-ref --format='%(creatordate:short)' refs/tags/vX` (tag date in the tagger's own time zone, as for the other 50 rows) |
| `pypi_date`, `python`, `platform`, wheel size | `https://pypi.org/pypi/vllm/X/json` (`urls[]`, `info.requires_python`) |
| `torch` | `requires_dist` in the same JSON; must equal `requirements/cuda.txt` at the tag |
| `soname`, `cuda_major` | `python3 -I wheel_peek.py <x86_64 wheel url>` (reads `DT_NEEDED` over HTTP range requests, about 1 MB) |
| `built_cuda`, `archs`, `ptx` | `.buildkite/release-pipeline.yaml` and `docker/Dockerfile` at the tag |
| `docs_cuda` | the "compiled with CUDA ..." sentence in `docs/getting_started/installation/gpu.cuda.inc.md` at the tag |
| `variants` | `+cuNNN` wheels among the assets of the GitHub release (run `wheel_peek.py` on each) |
| `index_variants` | sub-directories of `https://wheels.vllm.ai/X/` |
| `docker` | suffixes of `vllm/vllm-openai:vX*` on Docker Hub, without the per-arch and `-zstd` tags |

A new PyTorch pin also needs an entry in `matrix.json["torch"]` (CUDA of the PyPI build, and the `cuNNN` directories on
`https://download.pytorch.org/whl/torch/` that carry that version).

```
python3 -I .github/matrix/add_release.py en/vllm-torch-cuda-driver-matrix/matrix.json .github/matrix/facts_vX.json
python3 -I .github/matrix/build_page.py  en/vllm-torch-cuda-driver-matrix/matrix.json en/vllm-torch-cuda-driver-matrix <today>
python3 -m http.server 8765 &   # from the repository root
node .github/matrix/check_browser.js http://127.0.0.1:8765/en/vllm-torch-cuda-driver-matrix/
```

- `facts_v0.34.0.json` is the input that added v0.34.0; copy it for the next release.
- The page shows `pypi_date` everywhere (the day the wheels were uploaded, UTC). `date` (the git tag) stays in the data but is
  not shown: a tag can sit on a commit made weeks after the release (v0.10.2: tag 2025-10-07, PyPI 2025-09-13).
- `build_page.py` asserts every claim the prose makes about the data. The block around `cu13_only` stops the build when a
  release is not "CUDA 13.0 only, torch 2.14.0, no variant wheels": then the lede, the last bullets of "When did vLLM
  change ..." and the note under them have to be rewritten, not the assert loosened.
- The note about the install guide's `releases/latest` command, and which tag each GitHub release is attached to, is not
  generated. Re-read the guide and the release pages when rebuilding.
- `check_browser.js` holds answers worked out by hand from the table; update `LATEST`, `NREL` and the expected strings.
- `patch` scripts elsewhere read `matrix.json` for PyPI dates (`.github/structured-output/patch_v0.34.0.py`).
- After a rebuild: `sitemap.xml` lastmod, the card on `en/index.html`.
