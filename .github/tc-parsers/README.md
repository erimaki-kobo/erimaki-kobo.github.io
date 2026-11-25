# en/tool-call-parser-conformance-check: how the page is built

vLLM's own tool parsers, from the source of 20 releases (tags.txt: the newest patch of each minor, v0.15.1 to v0.34.0),
run without a GPU on fixed model outputs.

- stubload.py: puts one release's `vllm/` tree on sys.path and stubs what only the engine needs (torch, the compiled
  extension, model/engine/multimodal code, gguf, xgrammar, ...); pydantic models allow arbitrary types (older releases
  put msgspec structs in plain models); torch.iinfo gives real int64 bounds. The parser code runs as released.
- scenarios.py: the model outputs (per family, after vLLM's tests/tool_parsers/), the tools, the calls that should come out.
- run_parsers.py: per release: each parser built as the chat server builds it (`parser(tokenizer, request.tools)`),
  extract_tool_calls and extract_tool_calls_streaming (piece by piece) on every output; the cross run (every parser on
  every family's one-call output); the qwen3 reasoning parser chained with hermes / qwen3_coder. Stand-in tokenizer:
  special tokens are single tokens, other text is cut into words, spaces and single characters.
- classify.py: verdicts (ok, markup_in_content, no_call, content_lost, partial_call, ...). summarize.py prints ranges.
- selftest.py: a local server replays each release's parser results as vLLM's chat server would shape them (including
  the finish_reason rule before/after v0.33.0); toolcheck.py's labels must match classify.py's (1,960 of 1,960).
- test_toolcheck.py: the labels the replay cannot reach. toolcheck.py itself is en/tool-call-parser-conformance-check/toolcheck.py.

```
git -C vllm archive $TAG vllm ':(exclude)vllm/model_executor' ':(exclude)vllm/v1' ... | tar -x -C tr/$TAG
uv venv --python 3.12 venv; uv pip install regex pydantic openai fastapi partial-json-parser msgspec "transformers<5.23" \
  jsonschema pyyaml cachetools psutil numpy ijson cloudpickle pybase64 cbor2 orjson sentencepiece tiktoken huggingface_hub \
  requests tqdm blake3 py-cpuinfo pyzmq aiohttp prometheus_client typing_extensions setproctitle python-json-logger einops email-validator
venv/bin/python -I run_parsers.py tr/$TAG > res/$TAG.json          # about 3 s per release
python3 -I selftest.py res selftest.json
python3 -I build_page.py res selftest.json <repo>/en/tool-call-parser-conformance-check/toolcheck.py <repo>/en/tool-call-parser-conformance-check <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
The finish_reason rule (tool_calls for any parsed call before v0.33.0; a length stop stays "length" from v0.33.0, PR #59324)
was read from each release's chat server source, not run. results.tar.xz holds res/ and selftest.json.
