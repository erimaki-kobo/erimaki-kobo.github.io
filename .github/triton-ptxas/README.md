# en/triton-ptxas-arch-lookup: how the page is built

Rebuild when a new Triton, PyTorch or vLLM release appears, or a new CUDA compiler wheel is published.

```
git clone --bare --filter=blob:none https://github.com/triton-lang/triton triton.git
git clone --bare --filter=blob:none https://github.com/vllm-project/vllm vllm.git
python3 .github/triton-ptxas/scan_pypi.py run                     # downloads about 9 GB in total, one wheel at a time, deletes each; -> run/pypi.json
python3 .github/triton-ptxas/build_data.py run triton.git vllm.git   # -> run/data.json
python3 .github/triton-ptxas/build_page.py run/data.json en/triton-ptxas-arch-lookup/index.html <published> <modified>
NODE_PATH=<dir with playwright> node .github/triton-ptxas/check.js en/triton-ptxas-arch-lookup/index.html run
```

- `scan_pypi.py` executes nothing from the wheels. It reads the version banner and the `sm_*` strings out of each ptxas binary.
- `build_data.py` executes nothing from the Triton repository. It matches each release's `compiler.py` and `knobs.py` against the exact
  text forms it knows and stops on an unknown form. A new release that changes `get_ptxas`, `sm_arch_from_capability`,
  `ptx_get_version` or `env_nvidia_tool` needs a new branch there, written after reading the new code.
- `build_page.py` asserts every claim the prose makes about the data. If an assert fails, change the prose, not the assert.
- `check.js` derives every answer a second time from `pypi.json` with a rule table typed by hand, and compares it with what the page shows
  (all Triton releases x 9 GPUs x 2 widths). When `build_data.py` gets a new branch, update the table in `check.js` separately.
- Statements about public reports (issues, PRs, forum threads) and the GPU names per compute capability are not generated.
- Not blobless-safe: never run `git grep` on the bare clones made with `--filter=blob:none`; use `git show <tag>:<path>`.
- 2026-11-16: `data.json` and `pypi.json` in this folder are the inputs of the published page.
