# en/model-arch-min-version: bringing the page up to new releases

`en/model-arch-min-version/data.json` is the data the lookup reads; `index.html` shows the same data as three tables.
These scripts update both **incrementally**: they read only the tags that are newer than the published data, after
proving that they can re-derive what the published data says about its own newest tags.
(The scripts of the first full build, which walk every tag, are not here.)

```
V=<vllm bare clone>  T=<transformers clone, --filter=blob:none is enough>  L=<llama.cpp clone, --depth 1 --filter=blob:none>
P=en/model-arch-min-version
cp $P/data.json old.json
python3 -I .github/model-arch/check_tables.py $P/index.html old.json          # tables on the page == tables from the data
B=$(python3 -c "import json;print(json.load(open('en/gguf-arch-min-build-lookup/archs.json'))['llama_cpp_head'])")
git -C $L fetch --depth 1 --filter=blob:none origin tag $B
mkdir conv && git -C $L archive $B conversion convert_hf_to_gguf.py gguf-py/gguf/constants.py | tar -x -C conv
python3 -I .github/model-arch/gguf_map.py conv > hf2gguf.json                   # compare its keys with old.json["h2g"]: the new ones are
python3 -I .github/model-arch/converter_first.py $L work <old gguf_build> $B <new classes...> > conv_first.json
python3 -I .github/model-arch/update_data.py old.json $V $T conv conv_first.json en/gguf-arch-min-build-lookup/archs.json .github/common/pypi_dates.json > new.json
python3 -I .github/model-arch/build_page.py $P/index.html new.json new.html <today>
cp new.json $P/data.json && cp new.html $P/index.html
python3 -I .github/model-arch/check_tables.py $P/index.html $P/data.json
python3 -m http.server 8765 &   # repository root
node .github/model-arch/check_browser.js http://127.0.0.1:8765
```

- Before this: add the new releases to `.github/common/pypi_dates.json` (`https://pypi.org/pypi/<vllm|transformers>/json`,
  earliest upload of each release). Dates on the page are PyPI upload dates; a tag that is not on PyPI keeps its tag date.
- `update_data.py` stops when the published data cannot be reproduced from the published newest tags (vLLM statuses from
  `registry.py`, live Transformers model_types). That means an upstream file changed shape: fix `extract.py` first.
- `build_page.py` uses the published page as its template and replaces by pattern, each pattern counted. It asserts the
  examples the prose names (Qwen3, Qwen3.5, Gemma 4, Kimi K2.5, DeepSeek-V2, OLMo 2, the first Qwen, BART) and the special
  case of Mistral Large 4: vLLM v0.34.0 registers `MistralLarge4ForCausalLM`, the name its Mistral-format config loader
  assigns, not the Transformers class `MistralLarge4ForConditionalGeneration`. When an assert fails the prose has to change.
- `check_browser.js` holds answers read from the registries by hand for v0.34.0 / v5.23.0 / b12447; write new ones per release.
- `conv_first_b12352_b12447.json` is the converter_first.py output that went into the 2026-11-17 update.
- A class that two Transformers model types share (v5.23.0: `LlamaForCausalLM` is also listed under `internlm3`) keeps the
  model_type it had; only classes that are new get a mapping.
- h2g dates added from 2026-11-17 are UTC dates of the tag's commit; older ones were computed in the first build.
