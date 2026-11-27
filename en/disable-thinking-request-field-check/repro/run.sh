#!/bin/bash
# Rebuild the llama-server measurements on this page (CPU, a few minutes per build).
# usage: repro/run.sh <llama.cpp checkout at the build to test> <label>
set -e
LC=$1; LABEL=$2; HERE=$(cd "$(dirname "$0")" && pwd)
cmake -S "$LC" -B "$LC/build" -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$LC/build" --target llama-server -j"$(nproc)" >/dev/null
[ -f toy-qwen3.gguf ] || PYTHONPATH="$LC/gguf-py" python3 "$HERE/make_toy_qwen3.py" "$LC" toy-qwen3.gguf
"$LC/build/bin/llama-server" -m toy-qwen3.gguf --port 8091 -c 2048 -np 1 --jinja > "server_$LABEL.log" 2>&1 &
PID=$!; trap 'kill $PID' EXIT
for i in $(seq 60); do curl -s localhost:8091/health | grep -q ok && break; sleep 1; done
python3 "$HERE/render_matrix.py" 8091 "$LABEL" | tee -a results.jsonl
python3 "$HERE/../thinkcheck.py" --base-url http://localhost:8091/v1 --model toy --skip-thinking --json "run_llama_$LABEL.json"
