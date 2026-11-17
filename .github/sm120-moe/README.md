# en/vllm-sm120-moe-backend-lookup: how the page is built

The page embeds its data. To rebuild (for example when a new vLLM release is tagged):

```
git clone --bare https://github.com/vllm-project/vllm vllm.git
mkdir run && cd vllm.git
for t in $(git tag | grep -E '^v0\.(1[5-9]|[2-9][0-9])\.[0-9]+$' | sort -V); do git worktree add -f --detach ../run/wt_$t $t; done
cd ..
pip install torch humming-kernels gguf && pip install -r run/wt_<latest>/requirements/common.txt   # CPU is enough; do NOT pip install vllm or flashinfer
bash   .github/sm120-moe/batch.sh run                      # 7 capabilities x every tag, about 15 s each
# v0.16.0 only: the MXFP4 scenario needs vllm.vllm_flash_attn stubbed
for c in 80 89 90 100 103 120 121; do STUB_FA=1 SCEN_ONLY=mxfp4_gptoss CUDA_VISIBLE_DEVICES= python3 .github/sm120-moe/run_select.py run/wt_v0.16.0 $c 1 0 | grep '^{' > run/out/fix_v0.16.0.$c.jsonl; done
python3 .github/sm120-moe/build_data.py run vllm.git       # -> run/data.json
python3 .github/sm120-moe/forced.py run <latest tag>       # -> run/forced.json (messages quoted on the page)
python3 .github/sm120-moe/build_page.py run/data.json en/vllm-sm120-moe-backend-lookup/index.html <published> <modified>
node    .github/sm120-moe/check_browser.js en/vllm-sm120-moe-backend-lookup/index.html run
```

- `run_select.py` imports one release's Python source with compiled modules stubbed (`stubenv.py`), replaces `current_platform`
  with a CUDA platform of a chosen compute capability, and calls that release's own `select_*_moe_backend`.
- Three C++ predicates are re-implemented in `run_select.py`. Before a rebuild, compare them with the new tag's
  `vllm/_custom_ops.py`, `csrc/quantization/w8a8/cutlass/scaled_mm_entry.cu` and `csrc/quantization/fp4/mxfp4_experts_quant.cu`.
- `build_page.py` asserts every claim the prose makes about the data (auto picks, "the one break is v0.15.0 to v0.15.1",
  SM120 == SM121, Marlin always passes). If an assert fails, the prose has to change, not the assert.
- `forced_v0.33.0.json` is the `forced.json` of the v0.33.0 build. v0.34.0 reworded the FP8 rejection
  ("FP8 MoE backend X ..." became "Fp8 MoE backend 'X' ..."); `build_page.py` prints both forms and asserts them.
- `batch.sh` is resumable: run it again until it prints "left 0" (about 25 minutes in total on 2 cores for 29 tags).
- Dates are tag dates (`creatordate`), the same as the other vLLM pages.
- Statements about public reports (issues, PRs, forum threads) are not generated; re-read them when rebuilding.
  "Not in any release up to X" for PR #43730 and #43814 was checked with `git log --grep` on the bare clone.
- 2026-11-15: data for v0.15.0 to v0.33.0 was produced twice, on different machines, with identical output
  (sha256 of data.json with `%cs` dates begins 08e3d606e3195cdc).
