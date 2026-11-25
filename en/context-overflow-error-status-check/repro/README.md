# Reproducing /en/context-overflow-error-status-check/

- `make_cases.py` writes `cases.json`: each engine's response to an over-long request (status + body), copied from the engine source named in the `src` field.
- `replay.py cases.json > replay_results.json` serves each case from a local mock server and calls openai-python and LiteLLM (`openai/`, `hosted_vllm/`, `ollama_chat/`). `requests` is how many HTTP requests the client sent (retries). Run with `pip install openai litellm` (tested: openai 3.59.0, litellm 1.111.0).
- `llamacpp_*.json`: `../overflow_check.py --json` against llama-server built from source on CPU with `make_toy_gguf.py`'s model:
  - `llamacpp_default.json`: build 12733 (commit de30697), `-c 2048`
  - `llamacpp_np4.json`: same build, `-c 2048 -np 4` (512 tokens per slot)
  - `llamacpp_b6205_default.json`: b6205, `-c 2048` (context shift on by default: prompt truncated, HTTP 200)
  - `llamacpp_b6205_noshift.json`: b6205, `-c 2048 --no-context-shift`
- `make_toy_gguf.py`: `PYTHONPATH=<llama.cpp>/gguf-py python make_toy_gguf.py toy.gguf`
