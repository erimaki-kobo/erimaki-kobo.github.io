#!/bin/bash
# usage: firsttag.sh <gitdir> <path> <regex> [tagfilter]
cd "$1"; filt=${4:-'^v[0-9]+\.[0-9]+\.[0-9]+$'}
for t in $(git tag | grep -E "$filt" | sort -V); do
  if git show "$t:$2" 2>/dev/null | grep -qE "$3"; then echo "$t"; exit 0; fi
done; echo none
