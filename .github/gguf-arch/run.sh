#!/usr/bin/env bash
# Rebuild en/gguf-arch-min-build-lookup/ from the git history of llama.cpp and Ollama, then test it.
# Usage: run.sh WORK_DIR      -> WORK_DIR/out/index.html and WORK_DIR/out/archs.json
# Optional env: LLAMA_REF (build as of that llama.cpp ref instead of the default branch),
#               PAGE_MODIFIED (YYYY-MM-DD for dateModified), CHROME (path to a Chrome binary).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$1"
mkdir -p "$WORK"
cp "$HERE"/*.py "$HERE"/*.js "$WORK"/
cd "$WORK"

[ -d llama.cpp ] || git clone -q --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp
[ -d ollama ] || git clone -q --filter=blob:none --no-checkout https://github.com/ollama/ollama
if [ -n "${LLAMA_REF:-}" ]; then
  git -C llama.cpp update-ref --no-deref HEAD "$(git -C llama.cpp rev-parse "${LLAMA_REF}^{commit}")"
fi

git -C llama.cpp log --follow -p --date=short --format="COMMIT%x09%H%x09%ad%x09%s" -- src/llama-arch.cpp > arch_log.txt
python3 -I extract_llama.py
python3 -I extract_ollama.py
python3 -I extract_ollama_go.py
python3 -I extract_ollama_vendored.py
python3 -I build_table.py
rm -rf out
python3 -I build_page.py table.json out

python3 -I test_data.py
node -e "require('playwright')" 2>/dev/null || PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-save --silent playwright
node check_browser.js out/index.html out/archs.json
