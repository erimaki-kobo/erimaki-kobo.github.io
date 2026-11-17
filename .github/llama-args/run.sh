#!/usr/bin/env bash
# Rebuild en/llama-cpp-removed-args-lookup/ from llama.cpp's git history and test it.
# Usage: run.sh CLONE_DIR WORK_DIR SITE_ROOT
#   CLONE_DIR  a directory that holds (or will hold) a blobless clone named llama.cpp; the GGUF page's work dir is fine
#   -> WORK_DIR/site/en/llama-cpp-removed-args-lookup/{index.html,data.json}
# Stops (non-zero) when an assert in build_page.py no longer holds: a build removed or changed something the
# prose names. Then the published page stays as it is until a person rewrites the prose.
# Optional env: PAGE_MODIFIED (YYYY-MM-DD), CHROME.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CLONE="$1"; WORK="$2"; SITE="$(cd "$3" && pwd)"
mkdir -p "$CLONE" "$WORK"
[ -d "$CLONE/llama.cpp" ] || git clone -q --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp "$CLONE/llama.cpp"
REPO="$CLONE/llama.cpp"
export TZ=UTC
OUT="$WORK/site/en/llama-cpp-removed-args-lookup"
rm -rf "$WORK/site"; mkdir -p "$OUT"
python3 -I "$HERE/args_hist.py" "$REPO" > "$WORK/args_hist.json"
python3 -I "$HERE/old_flags.py" "$REPO" "$WORK/args_hist.json" > "$WORK/old_flags.json"
python3 -I "$HERE/build_data.py" "$WORK/args_hist.json" "$WORK/old_flags.json" > "$WORK/data.json"
python3 -I "$HERE/test_data.py" "$REPO" "$WORK/data.json"
PUBLISHED="$(python3 -I -c 'import re,sys;print(re.search(r"\"datePublished\": \"(\d{4}-\d\d-\d\d)\"",open(sys.argv[1],encoding="ascii").read()).group(1))' "$SITE/en/llama-cpp-removed-args-lookup/index.html")"
python3 -I "$HERE/build_page.py" "$WORK/data.json" "$SITE/en/gguf-arch-min-build-lookup/archs.json" "$OUT" "$PUBLISHED" "${PAGE_MODIFIED:-$(date -u +%F)}"
[ -f "$OUT/data.json" ] || cp "$WORK/data.json" "$OUT/data.json"
# The page reads the GGUF page's release table (Ollama release -> bundled build) at run time.
mkdir -p "$WORK/site/en/gguf-arch-min-build-lookup"
cp "$SITE/en/gguf-arch-min-build-lookup/archs.json" "$WORK/site/en/gguf-arch-min-build-lookup/"

# node resolves "playwright" from the directory of the script, so the script runs from a copy next to node_modules
cp "$HERE/check_browser.js" "$WORK/"
cd "$WORK"
node -e "require('playwright')" 2>/dev/null || PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-save --silent playwright
PORT=8765
python3 -m http.server "$PORT" --directory "$WORK/site" > "$WORK/http.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
sleep 1
LATEST_BUILD="$(python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["latest"][0])' "$WORK/data.json")" \
  node "$WORK/check_browser.js" "http://127.0.0.1:$PORT"
