# llama-cpp-pre-tokenizer-lookup

Source of https://erimaki-kobo.github.io/en/llama-cpp-pre-tokenizer-lookup/ : every `chkhsh` in llama.cpp's
`get_vocab_base_pre()` and every `tokenizer.ggml.pre` name the loader accepts, with the first release tag,
plus the first Ollama and llama-cpp-python release that bundles each name.

Rebuild: `bash .github/pretok/run.sh /tmp/pretok-work`, then copy `out/index.html` and `out/pretok.json`
to `en/llama-cpp-pre-tokenizer-lookup/` (set `PAGE_MODIFIED=YYYY-MM-DD` when the data changes). About 2 minutes.

| step | file | what |
| --- | --- | --- |
| 1 | extract_pretok.py | walks the first-parent history of the converter and loader files since 2024-04 and records when each hash / name was added (and removed) |
| 2 | validate.py | compares the lists implied by step 1 with the source of sampled release tags; must print `mismatching tags: 0` |
| 3 | groups.py | names the current loader handles identically (same branch body), and the build where each converter file started holding the list |
| 4 | (inline in run.sh) | hashes listed more than once at HEAD (the last `if` wins) |
| 5 | extract_ollama.py | llama.cpp pin of every Ollama release (same script as gguf-arch) |
| 6 | extract_bundles.py | first Ollama / llama-cpp-python release whose bundled llama.cpp contains the commit adding each name |
| 7 | build_page.py | page and pretok.json; asserts the worked examples in the text still hold |
| 8 | check_browser.js | runs the lookup on known inputs, checks row counts, duplicate ids and 390px overflow |

When the list moves to another file again, add the path to `CONV`/`VOCAB` in extract_pretok.py, `P` in run.sh
and the file lists in validate.py; validate.py fails until it is found.
