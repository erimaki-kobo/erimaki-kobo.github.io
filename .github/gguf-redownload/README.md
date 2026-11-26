# gguf-redownload-check

Source of https://erimaki-kobo.github.io/en/gguf-redownload-check/ : a browser tool that lists every upload of a GGUF
file on the Hugging Face Hub, finds the user's copy (sha256, file header, or Ollama tag) and says whether later uploads
changed the tensors or only metadata, plus a survey of re-uploads in popular repositories.

| file | what |
| --- | --- |
| ggufhist.js | history (`paths-info` + `lastCommit`), GGUF header parser (HTTP range or File), header diff, tensor-byte sampling by tensor name, Ollama manifest digest |
| ui.js | the page's form and verdicts |
| survey.js | the survey, run in a browser console on a page that can reach huggingface.co (after evaluating ggufhist.js); `summary()` gives survey.json |
| survey.json | the survey as published (2026-11-26) |
| build_page.py | `python3 build_page.py survey.json OUT` writes OUT/index.html (inlines style.css, ggufhist.js, ui.js); asserts the worked example |
| make_test_files.py, test_roundtrip.sh, test_parser.mjs | parser tests on small generated GGUF files and the gguf-new-metadata / gguf-set-metadata round trip (`pip install gguf numpy`) |
| lay.js | layout check (no overflow at 390px), needs playwright |

Rebuild: `python3 make_test_files.py && bash test_roundtrip.sh && node test_parser.mjs && python3 build_page.py survey.json out && node lay.js`.
To refresh the survey, run survey.js in a browser (about 15 minutes with 5 workers), save `summary()` as survey.json,
set `PAGE_MODIFIED`, rebuild.
The container used to build cannot reach huggingface.co; the network parts were tested in a browser on the live page.
