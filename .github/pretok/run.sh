#!/usr/bin/env bash
# Rebuild en/llama-cpp-pre-tokenizer-lookup/ from the git history of llama.cpp, Ollama and llama-cpp-python, then test it.
# Usage: run.sh WORK_DIR   -> WORK_DIR/out/index.html and WORK_DIR/out/pretok.json
# Optional env: PAGE_MODIFIED (YYYY-MM-DD for dateModified). Needs git, python3, node with playwright.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$1"
mkdir -p "$WORK"
cp "$HERE"/*.py "$HERE"/*.js "$HERE"/style.css "$WORK"/
cd "$WORK"
export TZ=UTC
[ -d llama.cpp ] || git clone -q --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp
[ -d ollama ] || git clone -q --filter=blob:none --no-checkout https://github.com/ollama/ollama
[ -d llama-cpp-python ] || git clone -q --filter=blob:none --no-checkout https://github.com/abetlen/llama-cpp-python
P="convert_hf_to_gguf.py convert-hf-to-gguf.py conversion/base.py src/llama-vocab.cpp src/llama-model.cpp src/llama.cpp llama.cpp"
git -C llama.cpp log --first-parent --reverse --raw --no-abbrev --no-renames --format='C %H %cd %s' --date=short-local --since=2024-04-01 -- $P > raw_fp.txt
# fetch every needed blob in one request (a blobless clone would otherwise fetch them one by one)
awk -F'\t' '/^:/{split($1,a," "); if (a[4] !~ /^0+$/) print a[4]}' raw_fp.txt | sort -u > oids.txt
git -C llama.cpp -c fetch.negotiationAlgorithm=noop fetch -q origin --no-tags --no-write-fetch-head --stdin < oids.txt
python3 -I extract_pretok.py llama.cpp raw_fp.txt pretok_raw.json
python3 -I validate.py llama.cpp pretok_raw.json 150 2>&1 | grep -v ambiguous | tail -3
python3 -I groups.py llama.cpp groups.json paths.json
python3 -I - <<'PY'
import json, re, subprocess
s = subprocess.run(["git", "-C", "llama.cpp", "show", "HEAD:conversion/base.py"], capture_output=True, text=True, check=True).stdout
order = {}
for cond, com, name in re.findall(r'if (chkhsh == "[0-9a-f]{64}"(?:\s+or\s+chkhsh == "[0-9a-f]{64}")*):\s*\n((?:[ \t]*#[^\n]*\n)*)[ \t]*res = "([^"]+)"', s):
    ref = re.search(r"ref:\s*(\S+)", com)
    for h in re.findall(r"[0-9a-f]{64}", cond):
        order.setdefault(h, []).append([name, ref.group(1) if ref else None])
json.dump({h: v for h, v in order.items() if len(v) > 1}, open("dups.json", "w"), indent=1)
PY
python3 -I extract_ollama.py
python3 -I extract_bundles.py pretok_raw.json ollama_tags.json bundles.json
rm -rf out
python3 -I build_page.py pretok_raw.json bundles.json groups.json dups.json paths.json validate.json out
node -e "require('playwright')" 2>/dev/null || PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-save --silent playwright
node check_browser.js out/index.html
