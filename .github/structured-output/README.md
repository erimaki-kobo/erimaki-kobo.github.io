# en/vllm-structured-output-backend-cost: extending the page to a new vLLM release

The page's full build scripts are not in this repository. When a new release does not change the rules, extend the page in place:

```
python3 -I .github/structured-output/same_rules.py <vllm.git> <old tag> <new tag>     # what changed, function by function
python3 -I .github/structured-output/patch_v0.34.0.py en/vllm-structured-output-backend-cost/index.html <vllm.git> <today>
node .github/structured-output/check_browser.js http://127.0.0.1:8765/en/vllm-structured-output-backend-cost/
```

- `patch_v0.34.0.py` refuses to run unless the functions that choose and validate the backend are identical (as syntax trees)
  in both tags and `requirements/common.txt` pins the same xgrammar, llguidance, outlines_core, lm-format-enforcer and lark.
  Copy it for the next release and change `OLD`, `NEW` and the replacement strings.
- If one of those functions did change, the checker (`group()` and `autoPick()` in the page's script) and the keyword table
  need a new rule set: that is a rebuild from the original scripts, with the 3,000-schema comparison against vLLM's own code.
- v0.34.0 changed only what happens while tokens are generated (`accept_tokens` in the xgrammar and guidance backends now roll
  back on a rejected token; speculative tokens are trimmed in `StructuredOutputManager`). The page makes no claim about that.
- Dates in the version list are PyPI upload dates, read from `en/vllm-torch-cuda-driver-matrix/matrix.json`, so rebuild the
  matrix first.
