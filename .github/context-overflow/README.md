# context-overflow-error-status-check

Page: en/context-overflow-error-status-check/ (index.html, overflow_check.py, repro/).

- Rebuild the page: `python3 build_page.py <site checkout> body.html ../../en/context-overflow-error-status-check/index.html` (head, JSON-LD and FAQ schema are generated from body.html; the style is copied from en/spec-decode-lossless-check/).
- Version boundaries: `tagscan.py <bare clone> <tag regex> <regex> <path>...` prints the first release tag whose file matches (prefix `!` to test absence). Engines were cloned with `git clone --filter=blob:none --no-checkout`.
- Client behavior: en/context-overflow-error-status-check/repro/README.md.
- Rework when: a new vLLM/SGLang minor changes renderers/params.py or tokenizer_manager.py length checks; llama.cpp changes server-context.cpp; Ollama changes llm/llama_server.go; LiteLLM changes is_error_str_context_window_exceeded (update LITELLM_SUBSTRINGS in overflow_check.py).
