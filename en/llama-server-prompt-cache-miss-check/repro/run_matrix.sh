#!/bin/bash
# Reproduce the table: a fresh llama-server per (configuration, case), two turns each,
# one JSON line per cell on stdout. Needs llama-server (S=...) and the toy models
# from make_toy_models.py in ./models.
S=${S:-llama-server}
CASES=${CASES:-"A_extend B_system_changed C_reply_rewritten D_middle_edit E_early_edit"}
run() { # name model extra-args...
  local name=$1 model=$2; shift 2
  for c in $CASES; do
    $S -m models/$model.gguf --port 8090 -c 4096 -np 1 -t 2 "$@" > logs/${name}__$c.log 2>&1 &
    pid=$!
    for i in $(seq 50); do curl -s localhost:8090/health | grep -q ok && break; sleep 0.2; done
    out=$(python3 cachecheck.py live cases/turn1.json cases/$c.json --server http://127.0.0.1:8090)
    code=$?
    kill $pid; wait $pid 2>/dev/null
    python3 - "$name" "$c" "$code" "$out" <<'PY'
import sys, re, json
name, c, code, out = sys.argv[1:]
t1 = re.search(r"turn 1: (\d+) prompt tokens", out)
m = re.search(r"turn 2: (\d+) prompt tokens, cache_n (\d+), prompt_n (\d+)", out)
sh = re.search(r"shared prefix of the two rendered prompts: (\d+)", out)
v = re.search(r"VERDICT: (.*)", out)
print(json.dumps({"config": name, "case": c, "turn1_tokens": int(t1.group(1)), "turn2_tokens": int(m.group(1)),
                  "shared": int(sh.group(1)), "cache_n": int(m.group(2)), "prompt_n": int(m.group(3)),
                  "exit": int(code), "verdict": v.group(1)[:60]}))
PY
  done
}
mkdir -p logs
run llama-full      toy-llama        -lv 4
run gemma2-swa      toy-gemma2-swa64 -lv 4
run gemma2-swa-full toy-gemma2-swa64 -lv 4 --swa-full
run mamba           toy-mamba        -lv 4
run mamba-no-ckpt   toy-mamba        -lv 4 --ctx-checkpoints 0
run gemma2-swa-lv3  toy-gemma2-swa64          # default verbosity: no checkpoint lines in the log
