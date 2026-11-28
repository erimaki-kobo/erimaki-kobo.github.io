#!/bin/bash
# Run embedcheck.py against llama-server for every toy checkpoint (CPU, a few seconds each).
# usage: run_matrix.sh <llama-server binary> <toys dir> <gguf dir> <out dir>
set -u
SRV=$1; TOYS=$2; G=$3; OUT=$4
mkdir -p "$OUT"
PORT=18090
run() {  # name mode gguf model extra-server-args... -- extra-check-args...
  local name=$1 mode=$2 gguf=$3 model=$4; shift 4
  local sargs=() cargs=()
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do sargs+=("$1"); shift; done
  [ $# -gt 0 ] && shift; cargs=("$@")
  "$SRV" -m "$G/$gguf" --port $PORT -t 2 -c 2048 "${sargs[@]}" > "$OUT/$name.server.log" 2>&1 &
  local pid=$!
  for i in $(seq 1 60); do curl -sf http://127.0.0.1:$PORT/health > /dev/null && break; sleep 0.5; done
  python embedcheck.py "$mode" --model "$TOYS/$model" --url http://127.0.0.1:$PORT --gguf "$G/$gguf" "${cargs[@]}" > "$OUT/$name.txt" 2> "$OUT/$name.err"
  echo "$name exit=$? $(grep -m1 '^verdict' "$OUT/$name.txt")"
  kill $pid; wait $pid 2>/dev/null
}
# embeddings
run cls-norm            embed  bert-cls-norm.gguf     bert-cls-norm     --embedding
run cls-norm.pool-mean  embed  bert-cls-norm.gguf     bert-cls-norm     --embedding --pooling mean
run mean-norm           embed  bert-mean-norm.gguf    bert-mean-norm    --embedding
run mean-prompt         embed  bert-mean-prompt.gguf  bert-mean-prompt  --embedding
run no-st-files         embed  bert-no-st-files.gguf  bert-no-st-files-ref --embedding
run cls-norm.raw        embed  bert-cls-norm.gguf     bert-cls-norm     --embedding --embd-normalize -1
run cls-norm.ub128      embed  bert-cls-norm.gguf     bert-cls-norm     --embedding -ub 128 -b 128
# rerankers
run ce.b12816           rerank bert-cross-encoder-b12816.gguf bert-cross-encoder --reranking
run ce.current          rerank bert-cross-encoder.gguf        bert-cross-encoder --reranking
run qwen3.reranker      rerank qwen3-reranker-toy.gguf  qwen3-reranker-toy --reranking -- --kind qwen3
run qwen3.as-llm        rerank toy-model.gguf           qwen3-reranker-toy --reranking --pooling rank -- --kind qwen3
