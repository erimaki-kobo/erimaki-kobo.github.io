# en/llama-cpp-removed-args-lookup: how the page is built

Nothing from llama.cpp is compiled or run; `common/arg.cpp` is read as text at every commit that changed it.

```
git clone --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp
python3 -I .github/llama-args/args_hist.py llama.cpp > args_hist.json          # ~1 min; fetches the ~400 versions of arg.cpp in one request
python3 -I .github/llama-args/old_flags.py llama.cpp args_hist.json > old_flags.json   # the hand-written parsers before b3716, every ~250 builds
python3 -I .github/llama-args/build_data.py args_hist.json old_flags.json > data.json
python3 -I .github/llama-args/test_data.py llama.cpp data.json                 # independent: text search at the build tags (~130 tags)
python3 -I .github/llama-args/build_page.py data.json en/gguf-arch-min-build-lookup/archs.json en/llama-cpp-removed-args-lookup <published> <today>
python3 -m http.server 8765 &   # repository root
node .github/llama-args/check_browser.js http://127.0.0.1:8765
```

- `args_hist.py`: each `add_opt(common_arg(...))` block (parentheses matched outside strings and comments) gives names, negated names,
  `set_examples` / `set_excludes`, `set_env`, whether it is a stub (`arg_removed(...)` or help text "the argument has been removed")
  and the option's own deprecation warning (a string starting with `DEPRECATED`). Commits are mapped to the first `bNNNN` tag containing them.
- `build_data.py`: which of llama-server (SERVER), llama-cli (MAIN before b7348, CLI from it) and llama-completion (COMPLETION) accept
  each name, as build ranges. An option belongs to a tool when it names that example or COMMON (no `set_examples` = COMMON) and does
  not exclude it; this is the rule in `arg.cpp` itself. It asserts the b7348 switch and that the `LLAMA_ARG_NO_` fallback exists
  wherever two-list (positive, negative) options do.
- `build_page.py` asserts every number and build the prose names. A new build that removes something changes the counts and stops the
  build: update the asserted tuple, read the removal commit, and add a line to `USE` if the replacement is a plain rename.
- The Ollama paragraph rests on `llm/llama_server.go` at v0.32.5 (`--no-mmap`) and v0.32.6 (`--load-mode`), read by hand, and on the
  bundled builds in the GGUF page's `archs.json` (asserted).
- `check_browser.js` expectations were written from the removal commits, not from the tool.
- Daily: `.github/workflows/gguf-arch-refresh.yml` runs `run.sh` (all of the above, against a copy of the page in a scratch
  directory) after the GGUF page and `finish.py` (publish when the tables changed or the data is 7 days old). When an assert
  in `build_page.py` stops the build, the published page stays, the GGUF page is still published, and the run ends red.
  `check_browser.js` takes the newest build from `LATEST_BUILD`, so a new build alone does not fail it.
