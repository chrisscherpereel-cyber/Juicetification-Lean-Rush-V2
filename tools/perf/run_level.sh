#!/bin/bash
# One load-test level against a local server.
# usage: tools/perf/run_level.sh APPDIR N_USERS ROUNDS burst|paced OUT.json
# The server is pinned to ONE core (taskset -c 0) to mimic Community Cloud,
# where all sessions share one Python process; the load generator runs on core 1.
APPDIR=$1; N=$2; R=$3; MODE=$4; OUT=$5; PORT=$((8600 + RANDOM % 300))
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$APPDIR"
taskset -c 0 python3 -m streamlit run app.py --server.headless true --server.port $PORT \
   > /tmp/st_$PORT.log 2>&1 &
SPID=$!
for i in $(seq 1 60); do curl -s localhost:$PORT/_stcore/health >/dev/null && break; sleep 0.5; done
# warm-up: one page load, as when the instructor opens the app before class
taskset -c 1 python3 "$HERE/loadtest.py" $PORT 1 0 burst /tmp/warm.json $SPID > /dev/null
taskset -c 1 python3 "$HERE/loadtest.py" $PORT $N $R $MODE "$OUT" $SPID
kill $SPID; wait $SPID 2>/dev/null
