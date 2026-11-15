#!/bin/bash
# usage: batch.sh <run dir containing wt_<tag>/ worktrees>   (writes <run dir>/out/*.jsonl)
HERE="$(cd "$(dirname "$0")" && pwd)"
RUN="$1"; mkdir -p "$RUN/out"; cd "$RUN" || exit 1
for d in wt_v*; do t=${d#wt_}; for c in 80 89 90 100 103 120 121; do echo "$t $c"; done; done | \
HERE="$HERE" xargs -P "${JOBS:-2}" -n 2 sh -c 't=$0; c=$1; v=$(echo $t | sed "s/v//"); hum=0; case $v in 0.1[5-9]*|0.20*|0.21*) hum=0;; *) hum=1;; esac; CUDA_VISIBLE_DEVICES= python3 "$HERE/run_select.py" wt_$t $c 1 $hum 2>out/$t.$c.err | grep "^{" > out/$t.$c.jsonl'
echo DONE > out/_done
