# Performance tooling

Everything used to measure the November 2026 optimization pass
(see `docs/PERFORMANCE_AUDIT.md`). Run from the repo root on Linux, with
`pip install -r requirements.txt pytest websockets`.

| script | what it measures |
|---|---|
| `loadtest.py` | **Concurrency.** Opens N real WebSocket sessions against a running `streamlit run` server and speaks Streamlit's own protocol (the same messages a browser tab sends), clicking through the game like a student: page load → [run the rush → answer the coach → commit a plan → switch the detail view] × rounds → generate report. Records per-action latency, server CPU and peak memory (RSS). |
| `run_level.sh` | Starts a fresh server pinned to one CPU core (Community Cloud runs every session in one Python process), warms it with one page load, runs `loadtest.py`. |
| `sweep.sh` | 1 / 5 / 10 / 20 / 30 / 40 users clicking simultaneously ("burst"), then 30 and 40 users with 2–8 s of think time between clicks ("paced"). |
| `percall.py` | Server CPU per action for a single student (median of many), via `hook.py`, which times only the script's own execution inside Streamlit's AppTest harness. |
| `netlat.py` | Per-click wall time with storage enabled, using fake Dropbox calls that sleep for a given latency (no network needed). |

```bash
tools/perf/sweep.sh "$PWD" new            # ~15 min on a 2-core machine
python tools/perf/percall.py "$PWD/app.py" off 4
python tools/perf/netlat.py "$PWD/app.py" 0.25 0.40
python -m pytest -q tests                 # functional + regression tests
```

Do not point `loadtest.py` at the production URL: it is a stress tool. Test
locally, then confirm on Community Cloud with a handful of real browser tabs.
