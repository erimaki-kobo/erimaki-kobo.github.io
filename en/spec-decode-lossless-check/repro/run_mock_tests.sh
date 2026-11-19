#!/bin/bash
# Runs ../specdiff.py against mock_server.py in every mode and checks the exit code and verdict.
set -u
cd "$(dirname "$0")"
pids=()
start(){ python3 mock_server.py $1 $2 ${3:-llama} & pids+=($!); }
start 18000 base
start 18009 flaky
start 18001 lossless
start 18002 neartie
start 18003 bug
start 18004 brokenlp
start 18005 nodraft
start 18006 shift
start 18007 lossless vllm
start 18008 neartie sglang
start 18010 lossless none
sleep 1
fail=0
check(){ # port base_port expected_code expected_verdict extra...
  out=$(python3 ../specdiff.py --base http://127.0.0.1:$2/v1 --spec http://127.0.0.1:$1/v1 --samples 400 "${@:5}" 2>&1); code=$?
  v=$(echo "$out" | grep '^VERDICT' | cut -d' ' -f2)
  if [ "$code" = "$3" ] && [ "$v" = "$4" ]; then echo "ok   $1 ${*:5} -> $code $v"; else echo "FAIL $1 ${*:5} -> $code $v (want $3 $4)"; echo "$out" | tail -25; fail=1; fi
}
check 18001 18000 0 NO_DIFFERENCE_FOUND
check 18002 18000 3 NEAR_TIE_DIVERGENCE
check 18003 18000 1 SUSPECTED_BUG
check 18004 18000 0 NO_DIFFERENCE_FOUND
check 18005 18000 4 INCONCLUSIVE_NO_DRAFTS_ACCEPTED
check 18006 18000 1 SUSPECTED_BUG
check 18006 18000 0 NO_DIFFERENCE_FOUND --skip-sample
check 18007 18000 0 NO_DIFFERENCE_FOUND
check 18008 18000 3 NEAR_TIE_DIVERGENCE
check 18001 18009 4 INCONCLUSIVE_BASELINE_NONDETERMINISTIC
check 18002 18000 3 NEAR_TIE_DIVERGENCE --completions
check 18010 18000 0 NO_DIFFERENCE_FOUND
kill ${pids[@]} 2>/dev/null
exit $fail
