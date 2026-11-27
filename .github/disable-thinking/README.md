# disable-thinking-request-field-check

Page: https://erimaki-kobo.github.io/en/disable-thinking-request-field-check/ (published 2026-11-27)

## What is measured, what is read

- llama-server (b6393, b10108, b12809): measured. `en/disable-thinking-request-field-check/repro/run.sh <llama.cpp checkout> <label>`
  builds llama-server on CPU, writes the toy Qwen3 GGUF (make_toy_qwen3.py: real Qwen2 vocab + Qwen3's 4 added tokens + real
  Qwen3-0.6B template from llama.cpp models/), posts each body to /apply-template (render_matrix.py -> results.jsonl) and runs
  thinkcheck.py. toy-qwen3.gguf sha256 202d4dc6446dc3d30092aba40e593e159e868d071194ce48606f6452bf67270d (gguf-py at b12809).
  b10108 returns HTTP 500 "does not match the expected peg-native format" for sampling runs on the toy (toy output), so only
  the render rows exist for it.
- Ollama v0.40.18, vLLM v0.34.0, SGLang v0.5.23: read from source, not run.
- "since" versions: binary search over release tags, reading the request-parsing file at each tag
  (.github/disable-thinking/bisect_tag.py: `bisect_tag.py <bare blobless clone> <tag regex> <regex> <paths...>`):
  - llama.cpp tools/server/server-common.cpp (older: tools/server/utils.hpp, examples/server/utils.hpp)
    b5780 per-request chat_template_kwargs, b6394 string enable_thinking -> 400, b8287 thinking_budget_tokens,
    b9982 reasoning_budget_tokens, b10121 reasoning_effort "none" (#26045)
  - vLLM vllm/entrypoints/openai/protocol.py -> chat_completion/protocol.py; serve/engine/protocol.py for the extra-field log
    v0.5.1 chat_template_kwargs, v0.6.5 extra-field warning, v0.10.1 include_reasoning, v0.11.0 unused kwargs dropped
    (renderers/hf.py or entrypoints/chat_utils.py resolve_chat_template_kwargs), v0.16.0 reasoning_content removed from
    responses (#33402), v0.18.0 "none" allowed (#36238) + extra-field log at debug, v0.19.0 thinking_token_budget,
    v0.22.0 none -> enable_thinking=false (#43401). Dates from .github/common/pypi_dates.json.
  - SGLang python/sglang/srt/entrypoints/openai/protocol.py: v0.4.4 separate_reasoning, v0.4.7 chat_template_kwargs,
    v0.5.1 reasoning_effort (low/medium/high), v0.5.10 "none" (#20556), v0.5.23 top-level thinking
  - Ollama openai/openai.go (full bare clone, .github/disable-thinking/firsttag.sh): v0.9.0 native think, v0.11.0 reasoning in /v1 responses,
    v0.11.5 reasoning_effort (string think -> 400 for non-harmony models until v0.12.3), v0.12.4 "none" -> think false

## When to rerun

A new vLLM / SGLang minor, Ollama release or llama.cpp change to oaicompat_chat_params_parse: re-read the four files above
and update the two tables. repro/mock_engine.py tests thinkcheck.py's verdicts (ollama_v1, vllm_0_21, vllm_0_17 modes).
