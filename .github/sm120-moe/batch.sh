#!/bin/bash
# usage: batch.sh <run dir containing wt_<tag>/ worktrees>   (writes <run dir>/out/*.jsonl)
# Resumable: a (tag, capability) pair whose .jsonl already has content is skipped, so the script can be
# run again after an interruption (or under a time limit) until it prints "left 0".
HERE="$(cd "$(dirname "$0")" && pwd)"
RUN="$1"; mkdir -p "$RUN/out"; cd "$RUN" || exit 1
for d in wt_v*; do t=${d#wt_}; for c in 80 89 90 100 103 120 121; do [ -s "out/$t.$c.jsonl" ] || echo "$t $c"; done; done > out/_todo
echo "left $(wc -l < out/_todo)"
cat out/_todo | \
HERE="$HERE" xargs -P "${JOBS:-2}" -n 2 sh -c 't=$0; c=$1; v=$(echo $t | sed "s/v//"); hum=0; case $v in 0.1[5-9]*|0.20*|0.21*) hum=0;; *) hum=1;; esac; CUDA_VISIBLE_DEVICES= python3 "$HERE/run_select.py" wt_$t $c 1 $hum 2>out/$t.$c.err | grep "^{" > out/$t.$c.tmp && mv out/$t.$c.tmp out/$t.$c.jsonl'
for d in wt_v*; do t=${d#wt_}; for c in 80 89 90 100 103 120 121; do [ -s "out/$t.$c.jsonl" ] || echo "MISSING $t $c"; done; done
echo DONE > out/_done
