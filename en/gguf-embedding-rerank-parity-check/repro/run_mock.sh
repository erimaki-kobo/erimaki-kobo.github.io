#!/bin/bash
# Test embedcheck.py's Ollama / TEI / vLLM client paths against mock_engine.py.
set -u; TOYS=$1; OUT=$2; mkdir -p "$OUT"; P=18100
m() { # name engine model mode api [--rerank] -- check args
  local name=$1 eng=$2 model=$3 mode=$4 api=$5; shift 5; local rr=""
  [ "${1:-}" = "--rerank" ] && { rr=--rerank; shift; }
  [ "${1:-}" = "--" ] && shift
  python mock_engine.py $P $eng "$TOYS/$model" $rr > "$OUT/$name.mock.log" 2>&1 & local pid=$!
  for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:$P/ && break; sleep 0.5; done
  python embedcheck.py $mode --model "$TOYS/$model" --url http://127.0.0.1:$P --api $api "$@" > "$OUT/$name.txt" 2> "$OUT/$name.err"
  echo "$name exit=$? $(grep -m1 '^verdict' "$OUT/$name.txt")"; kill $pid; wait $pid 2>/dev/null; P=$((P+1))
}
m ollama.mean-norm     ollama bert-mean-norm   embed  ollama
m ollama-legacy.cls    ollama bert-cls-norm    embed  ollama-legacy
m ollama.mean-prompt   ollama bert-mean-prompt embed  ollama
m tei.mean-norm        tei    bert-mean-norm   embed  tei
m tei.mean-prompt      tei    bert-mean-prompt embed  tei
m vllm.cls-norm        vllm   bert-cls-norm    embed  vllm
m vllm.mean-norm       vllm   bert-mean-norm   embed  vllm
m tei.ce               tei    bert-cross-encoder rerank tei  --rerank
m vllm.ce              vllm   bert-cross-encoder rerank vllm --rerank
