# Lean Rush — performance audit, November 2026

Goal: keep the app reliable on Streamlit Community Cloud with 30–40 students
using it at the same time, without changing hosting or the game.

All numbers below were **measured** unless marked *estimate*. The test setup is
in `tools/perf/` and the regression tests are in `tests/`.

## How it was measured

* **Concurrency:** `tools/perf/loadtest.py` opens real WebSocket sessions
  against a local `streamlit run` server and speaks Streamlit's own protocol,
  which is exactly what a browser tab sends. Each virtual student plays the game:
  page load → 3 × (run the rush → answer the coach → commit a plan → switch the
  detail view) → generate report. That is 14 actions per student.
  The server is pinned to **one CPU core**, because Community Cloud runs every
  session in one Python process. "Burst" means everyone clicks at the same
  moment with no pause, which is the worst case. "Paced" means 2–8 s of think
  time between clicks, which is closer to a real class.
* **Per-action CPU:** `tools/perf/percall.py` times only the app script's own
  execution, as a median over 4 simulated students × 3 rounds.
* **Storage latency:** `tools/perf/netlat.py` replaces the Dropbox calls with
  fakes that wait 0.25 s per download and 0.40 s per upload. These latencies
  are *assumptions*. Real Dropbox latency from Community Cloud was not measured.

## Platform limits (Streamlit Community Cloud)

Streamlit's documentation gives limits "as of February 2024, approximately":
CPU 0.078–2 cores, memory 690 MB–2.7 GB, storage up to 50 GB. It adds that the
limits "may change at any time without notice". The exact allocation for this
app is **unknown**. Apps sleep after 12 hours without traffic. Educational and
non-profit apps can **apply for increased resources** at no cost.

## Findings, by priority

### Priority 1 — Critical

| # | Problem | Root cause | Fix | Measured result |
|---|---|---|---|---|
| 1 | **Memory exhaustion when reports are generated.** At 30 users, server memory peaked at **4.4 GB**. | `build_report_pdf()` measured text on a 6120 × 7920 px canvas at 720 dpi. That allocated **~194 MB per report** just to read font widths, and it was never drawn on. A few students generating reports at once pushed memory past Community Cloud's ceiling ("Oh no" / app killed). | Measure on a 1 × 1 renderer at the same DPI. The widths are identical (test-verified), and the PDF is **pixel-identical** on every page. | Peak RSS at 30 users: **4361 → 493 MB**; at 40 users: **5151 → 601 MB**. |
| 2 | **Simulation cache silently failing under load.** | `st.cache_data` pickles return values. Pickle finds the `RoundResult` class through `sys.modules["__main__"]`, which Streamlit overwrites on every rerun of every session. With several students active, it usually points at someone else's module, so pickling fails and the rush is recomputed. | Cache a plain dict (`dataclasses.asdict`) and rebuild the `RoundResult` on read. The rebuilt result is lossless (test-verified). | Instrumented baseline at 10 users: **454 of 1954 (23%)** cache calls failed. After the fix the failure is not possible (test-verified). |
| 3 | **Race on the engine binding.** | `sim = sys.modules[__name__]` reads that same process-wide slot. A session could bind `sim` to another student's half-executed module, causing a missing-name crash or the wrong instructor overrides. | `sim` now reads this run's own globals. | Race removed by construction. Not reproducible on demand, so not measurable. |
| 4 | **Cross-section cache mix-up.** | The process-wide simulation cache ignored the instructor's rush overrides (rush length, blend setup, handoff time). Two sections running different `?game=` settings at the same time could be served each other's rushes. | The overrides are now part of the cache key. | Test: 450 s vs 900 s rushes, same seed, same process → different results. |
| 5 | **A Dropbox download on every click.** | With a `?game=` link, `resolve_config()` downloaded and decrypted the instructor's config on **every rerun of every student**. That adds network latency to each click and burns through Dropbox's rate limit, whose back-off then makes clicks stall. | The config is shared process-wide for 2 minutes, so instructor edits still arrive. Failures are never cached. The config is the same for the whole game and is not student data. | Storage downloads per scripted session: **16 → 1**. Answer-click wall time at the assumed latency: **0.69 s → 0.03 s**. |

### Priority 2 — High

| # | Problem | Fix | Measured result |
|---|---|---|---|
| 6 | Every answer waited on a **synchronous Dropbox upload** before the page could update. | Uploads moved to a 3-thread background saver (`autosave_worker.py`): newest-wins coalescing, per-student ordering, 3 retries. A refresh is restored from the queued snapshot (read-your-writes). | Uploads per session: **13 → 8** (coalesced). Upload time is gone from the click path. See the note under Remaining risks. |
| 7 | Report generation is the heaviest action (~1 s of CPU). Students press Generate repeatedly. | Each report rebuild now uses memoised text widths. An identical report is not rebuilt when nothing it shows has changed. | First build **980 → 700 ms** of CPU (median). Repeat click **913 → 32 ms**. |
| 8 | Report pages were built with `pyplot` (`plt.figure`), whose global registry is not thread-safe. | Standalone `Figure` objects. `pyplot` is no longer imported at all. | Correctness/stability; output is pixel-identical. |

### Priority 3 — Medium

| # | Problem | Fix | Measured result |
|---|---|---|---|
| 9 | About 100 cache-key hashes per rerun on long tuples (hundreds of cycle times; a nested 40-field config). | Long keys are passed as one `repr()` string (same uniqueness), and the data rides along un-hashed. | Together with #10: simple click **33 → 24 ms** of CPU (−29%). |
| 10 | Usage-statistics telemetry was recorded **server-side** for every `st.*` call (~180 per rerun). | `.streamlit/config.toml`: `browser.gatherUsageStats = false`. | ~6–8% of an ordinary rerun. |
| 11 | Downloading the report triggered a full app rerun. | `on_click="ignore"` on both download buttons. | One rerun saved per download. |
| 12 | `streamlit>=1.30` was unpinned, so Cloud installs whatever is newest on every reboot. The app already relies on a deprecated API (`components.v1.html`). | Pinned: **1.67.0** on Python ≥ 3.11, **1.65.0** on Python 3.10 (Streamlit 1.66 dropped 3.10). | Regression tests pass on both. |

### Priority 4 — Low

* `__pycache__/` was committed despite `.gitignore`. It is now untracked.
* `juicetification-lean-rush.zip` (1.4 MB, an older copy of the app) is still in
  the repo. It slows cloning slightly. It was left in place, to be removed only
  if you no longer need it.

### Looked at and left alone

* **File uploads:** the app has none. **Downloads:** only the PDF report (#7, #11).
* **The simulation engine** is cheap (~1.5 ms per replication). Most of a rush's
  CPU goes to the coach's "which waste costs most" analysis (≈8 counterfactual
  simulations) and drawing the student's own charts. Both are unique to each
  student's shop, so caching can't share them, and reducing replications would
  change the game's numbers.
* **Session state** is about 130 KB per student. It is not a memory concern.
* **Threads, multiprocessing:** not added. All sessions share one interpreter,
  so extra Python threads would not add CPU capacity.

## Concurrency results

### Run 1 — code fixes #1–#8 (usage stats off on both sides, 1 core)

| users | mode | peak memory MB (before → after) | server CPU-s for the whole test | median response s | p95 response s | errors |
|---|---|---|---|---|---|---|
| 1 | burst | 454 → 247 | 3.54 → 2.53 | 0.14 → 0.06 | 0.38 → 0.31 | 0/0 |
| 5 | burst | 1058 → 322 | 15.6 → 14.7 | 0.55 → 0.52 | 3.88 → 4.15 | 0/0 |
| 10 | burst | 1481 → 378 | 37.5 → 31.3 | 1.12 → 1.24 | 8.17 → 7.38 | 0/0 |
| 20 | burst | 2466 → 453 | 73.2 → 65.1 | 1.54 → 1.57 | 17.7 → 15.9 | 0/0 |
| 30 | burst | 4361 → 493 | 124.0 → 99.7 | 2.79 → 1.93 | 31.1 → 24.9 | 0/0 |
| 40 | burst | 5151 → 601 | 166.9 → 149.3 | 3.91 → 3.60 | 39.5 → 40.1 | 0/0 |
| 30 | paced | 3783 → 433 | 108.5 → 96.9 | 0.65 → 0.65 | 12.6 → 9.7 | 0/0 |
| 40 | paced | 5132 → 505 | 162.8 → 130.5 | 1.28 → 0.81 | 28.5 → 17.8 | 0/0 |

Storage was off in this test (no Dropbox locally), so fixes #5 and #6 are not
reflected here. They are measured separately above.

### Run 2 — final version (all fixes, default server settings, 1 core)

FINAL_RESULTS_PLACEHOLDER

## Can it support 30–40 students?

**Memory: yes.** Peak memory at 40 users is now ~600 MB, under even the
documented 690 MB minimum. Before the fix, memory passed 2.7 GB at 20–30
users, which is what crashes the app.

**CPU: it is the remaining limit, and it is a platform limit.** All sessions
run in one Python process, which uses about one core no matter how many the
container offers. A student session in this test costs ~3 CPU-seconds spread
over 14 actions. With 30 students clicking every few seconds, the server is
busy 90–100% of the time. Clicks still work (0 errors at every level), but
some take several seconds when many coincide. That pattern matches what
students describe as "slow". Community Cloud's CPU may also be slower than
this test machine, and it is shared with other apps: *unknown*.

Cost-free options, from most to least effective:

1. **Apply for Community Cloud's increased resources** for educational apps
   (Streamlit's form, linked from their "Manage your app" docs).
2. **Spread the heavy moments.** "Everyone generate your report now" is the
   single most expensive instant in class. Staggering it by table or row, or
   having students generate after class, removes the worst spike.
3. **Run two deployments of the same repo** (e.g. one per half of the class).
   Each is its own process with its own CPU. This is the same free hosting,
   not a new service, and it is the only way to get more than one core of
   Python on Community Cloud. Students' progress is keyed by game code and
   student ID in Dropbox, so both copies can share the same storage secrets.

## Remaining risks

* **Background saving.** A student's latest answers are uploaded within
  seconds rather than before the page updates. If the server process restarts
  in that window (reboot, crash), the last few seconds of answers are lost.
  Previously a failed upload also lost them, silently. Data stored, format and
  location are unchanged.
* The game config can be up to 2 minutes stale after an instructor edits it
  mid-class.
* `st.components.v1.html` is deprecated by Streamlit. The pin keeps it
  working. A future upgrade should move those three snippets to `st.iframe`.
