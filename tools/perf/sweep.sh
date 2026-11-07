#!/bin/bash
# Full sweep: 1/5/10/20/30/40 users all clicking at once ("burst"), then
# 30/40 users with 2-8 s of think time between clicks ("paced").
# usage: tools/perf/sweep.sh APPDIR TAG      (writes TAG_burst_N.json etc.)
HERE=$(cd "$(dirname "$0")" && pwd)
for n in 1 5 10 20 30 40; do echo "== $2 N=$n burst"; "$HERE/run_level.sh" "$1" $n 3 burst ${2}_burst_$n.json; done
for n in 30 40; do echo "== $2 N=$n paced"; "$HERE/run_level.sh" "$1" $n 3 paced ${2}_paced_$n.json; done
