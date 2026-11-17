# vllm-kv-concurrency-planner: how to check and extend

The published page (`en/vllm-kv-concurrency-planner/index.html`, with `kvplan.py` next to it) is its own
template since 2026-11-17: edit both directly, then run the checks below. `patch_v0.34.0.py` is the record
of how the v0.33.0 page became the v0.34.0 one (it refuses to run twice). The kv-planner entries in
`.github/live-fixes/2026-11-14_audit.py` and `2026-11-17_dates.py` are already in the page.

## When a new vLLM release comes out

```
git clone --bare https://github.com/vllm-project/vllm vllm.git          # about 1 minute
python3 same_plan.py vllm.git v0.34.0 vNEW                              # which planning functions changed
mkdir src && git -C vllm.git archive vNEW vllm/v1/kv_cache_interface.py vllm/v1/core/kv_cache_planning.py \
  vllm/v1/core/kv_cache_utils.py vllm/v1/core/kv_cache_config_builder.py vllm/v1/kv_cache_layout.py \
  vllm/v1/kv_cache_spec_registry.py vllm/v1/core/single_type_kv_cache_manager.py vllm/utils/math_utils.py \
  vllm/v1/worker/extensible_kv_cache.py | tar -x -C src
P=../../en/vllm-kv-concurrency-planner
python3 verify_port.py $P src 20000 20261117 && python3 verify_port.py $P src 20000 7   # mismatch must be 0
python3 verify_measured.py $P src/vllm/v1/worker/extensible_kv_cache.py                 # mismatch must be 0
python3 gen_parity_cases.py $P 6000 5 > cases.json && node test_parity.js $P/index.html cases.json
npm i jsdom && node test_ui.js $P/index.html
```

`real_vllm.py` loads vLLM's own planning files with a stub torch; if an import is new, add a stub there.
Also read by hand, because no script covers them: `vllm/config/cache.py` (DEFAULT_BLOCK_SIZE,
resolved_gpu_memory_utilization), `get_batch_defaults` in `vllm/engine/arg_utils.py`, `max_concurrent_batches`
in `vllm/config/vllm.py`, and the log formats in `LOG_PATTERNS`.

Results on 2026-11-17: verify_port 40,000 cases each for v0.33.0 and v0.34.0, 0 mismatches; verify_measured
20,000, 0; parity 6,032 inputs, 0; test_ui 18 checks.

Not checked: a real v0.34.0 startup log (none public yet), any GPU run.
