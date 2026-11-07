"""Regression tests for the concurrency / performance fixes.

Run from the repo root:   python -m pytest -q tests

They drive the real app through Streamlit's AppTest harness (no browser) and
exercise the engine directly. Storage (Dropbox) is never contacted: where a
test needs it, student_store's functions are replaced by in-memory fakes.
"""
import base64
import dataclasses
import json
import os
import pickle
import sys
import threading
import time
import types

import pytest
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app.py")
sys.path.insert(0, ROOT)

import autosave_worker  # noqa: E402
import student_store  # noqa: E402


# ---------------------------------------------------------------- helpers ---
def engine():
    """The simulation engine (the top of app.py) as an ordinary module."""
    src = open(APP, encoding="utf-8").read().split("class _EngineView:")[0]
    mod = types.ModuleType("lean_engine")
    sys.modules["lean_engine"] = mod
    exec(compile(src, APP, "exec"), mod.__dict__)
    return mod


def new_app(**query):
    at = AppTest.from_file(APP, default_timeout=180)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def button(at, prefix=None, key=None):
    for b in at.button:
        if (key and b.key == key) or (prefix and (b.label or "").startswith(prefix)):
            return b
    raise KeyError(prefix or key)


def play_round(at):
    button(at, "▶️").click().run()
    assert not at.exception, at.exception
    for pre in ("coachmc_", "plancommit_"):
        r = [x for x in at.radio if (x.key or "").startswith(pre)]
        if r:
            r[0].set_value(r[0].options[0]).run()
            assert not at.exception, at.exception


@pytest.fixture
def fake_storage(monkeypatch):
    """student_store with storage 'enabled' but backed by a dict, with call
    counters and a little latency so ordering problems would show up."""
    db, calls = {}, {"load_game_config": 0, "save": 0, "load": 0}
    lock = threading.Lock()

    def load_game_config(code):
        calls["load_game_config"] += 1
        return {"params": {}, "seed": 4242}

    def save(game, sid, state, **kw):
        time.sleep(0.02)
        with lock:
            calls["save"] += 1
            db[(game, sid)] = json.loads(json.dumps(state))
        return True

    def load(game, sid):
        calls["load"] += 1
        return json.loads(json.dumps(db.get((game, sid), {})))

    monkeypatch.setattr(student_store, "ENABLED", True)
    monkeypatch.setattr(student_store, "load_game_config", load_game_config)
    monkeypatch.setattr(student_store, "save", save)
    monkeypatch.setattr(student_store, "load", load)
    monkeypatch.setattr(student_store, "record_completion", lambda *a, **k: True)
    # a fresh process-wide saver bound to this fake
    monkeypatch.setattr(autosave_worker, "_SAVER", None)
    return db, calls


# ------------------------------------------------------------ the engine ---
def test_cached_result_round_trips_exactly():
    """The sim cache stores asdict(result); rebuilding must be lossless."""
    eng = engine()
    res = eng.run_simulation(eng.Config(), base_seed=1001)
    rebuilt = eng.RoundResult(**pickle.loads(pickle.dumps(dataclasses.asdict(res))))
    assert rebuilt == res
    assert rebuilt.va_pct == res.va_pct


def test_cached_value_pickles_whatever_main_is():
    """With 30 sessions, sys.modules['__main__'] is usually another student's
    module. The old RoundResult return value failed to pickle in that state
    (measured: 23% of cache calls at 10 users); the dict form must not."""
    eng = engine()
    res = eng.run_simulation(eng.Config(), base_seed=7)
    saved = sys.modules.get("__main__")
    try:
        sys.modules["__main__"] = types.ModuleType("__main__")   # a stranger
        pickle.dumps(dataclasses.asdict(res))                     # must not raise
    finally:
        sys.modules["__main__"] = saved


def test_one_pixel_measuring_renderer_gives_identical_widths():
    """The report measured text on a 6120x7920 px canvas (~194 MB); a 1x1
    renderer at the same DPI must wrap text identically."""
    from matplotlib.backends.backend_agg import RendererAgg
    from matplotlib.font_manager import FontProperties
    big, tiny = RendererAgg(int(8.5 * 720), int(11 * 720), 720), RendererAgg(1, 1, 720)
    for size, weight in ((9.2, "normal"), (12.5, "bold"), (7.5, "normal")):
        p = FontProperties(family="DejaVu Sans", size=size, weight=weight)
        for s in ("Juicetification: The Lean Rush", "Lean Score 73 · profit $41",
                  "W" * 40, "a quick brown fox jumps"):
            assert (big.get_text_width_height_descent(s, p, ismath=False)
                    == tiny.get_text_width_height_descent(s, p, ismath=False))


def test_no_pyplot_and_no_sys_modules_engine_binding():
    src = open(APP, encoding="utf-8").read()
    assert "sim = _sys.modules[__name__]" not in src
    assert "sim = _EngineView(globals())" in src
    assert "import matplotlib.pyplot" not in src
    assert "plt." not in src.replace("plt.figure(): pyplot", "")


# ------------------------------------------------------------- the app ---
def test_full_flow_and_report_is_not_rebuilt_when_unchanged():
    at = new_app()
    for _ in range(2):
        play_round(at)
    button(at, key="gen_report_side").click().run()
    assert not at.exception, at.exception
    pdf = at.session_state["report_pdf"]
    assert pdf.startswith(b"%PDF") and len(pdf) > 10_000
    sig = at.session_state["report_sig"]

    button(at, key="gen_report_side").click().run()     # nothing changed
    assert at.session_state["report_pdf"] is pdf           # reused, not rebuilt
    assert at.session_state["report_sig"] == sig

    play_round(at)                                         # something changed
    button(at, key="gen_report_side").click().run()
    assert at.session_state["report_sig"] != sig
    assert at.session_state["report_pdf"] is not pdf


def test_sessions_share_cache_but_never_each_others_results():
    """Two students, different shops, same process (shared caches): each one's
    result must equal an uncached simulation of THEIR OWN configuration."""
    eng = engine()
    a, b = new_app(seed="111"), new_app(seed="222")
    play_round(a); play_round(b); play_round(a)
    for at in (a, b):
        cfg = at.session_state["last_cfg"]
        seed = at.session_state["last_seed"]
        fresh = eng.run_simulation(eng.Config(**dataclasses.asdict(cfg)), base_seed=seed)
        assert dataclasses.asdict(at.session_state["last_result"]) == dataclasses.asdict(fresh)
    assert a.session_state["scenario"] != b.session_state["scenario"]


def test_instructor_rush_overrides_are_part_of_the_cache_key():
    """Two sections with different ?cfg= rush lengths in one process must not
    be served each other's cached rushes."""
    cfg = base64.urlsafe_b64encode(json.dumps({"horizon_s": 450}).encode()).decode()
    short, normal = new_app(seed="5", cfg=cfg), new_app(seed="5")
    play_round(normal); play_round(short)
    assert normal.session_state["scenario"] == short.session_state["scenario"]
    assert (normal.session_state["last_result"].arrivals
            > short.session_state["last_result"].arrivals * 1.5)


def test_game_config_fetched_once_and_progress_saved_in_background(fake_storage):
    db, calls = fake_storage
    at = new_app(game="CLASS1", sid="student01")
    for _ in range(3):
        at.run()
    play_round(at)
    assert calls["load_game_config"] == 1        # was: once per rerun
    saver = autosave_worker.get_saver(None)
    assert saver.wait_idle(10)
    stored = db[("CLASS1", "student01")]
    assert stored["round"] == at.session_state["round"]

    # read-your-writes: a refresh right after an answer is restored from the
    # queued snapshot even before storage has it
    play_round(at)
    expect_round = at.session_state["round"]
    again = new_app(game="CLASS1", sid="student01")
    assert again.session_state["round"] == expect_round


# ------------------------------------------------------ the saver alone ---
def test_saver_coalesces_orders_and_retries():
    seen, lock = [], threading.Lock()
    fail_once = {"k2": True}

    def save(key, snap):
        time.sleep(0.05)
        if fail_once.pop(key, False):
            raise IOError("transient")
        with lock:
            seen.append((key, snap["n"]))

    s = autosave_worker.BackgroundSaver(save, workers=3, retry_delay=0.01)
    for n in range(20):                       # a burst of clicks
        s.submit("k1", {"n": n})
    s.submit("k2", {"n": 1})
    assert s.latest("k1") == {"n": 19}
    assert s.wait_idle(10)
    k1 = [n for k, n in seen if k == "k1"]
    assert k1 == sorted(k1) and k1[-1] == 19   # in order, newest last
    assert len(k1) < 20                       # coalesced
    assert ("k2", 1) in seen                  # retried after a failure
    assert s.latest("k1") is None             # confirmed -> nothing pending


def test_saver_latest_is_an_independent_copy():
    s = autosave_worker.BackgroundSaver(lambda k, v: time.sleep(0.2), workers=1)
    snap = {"answers": {"q": "a"}}
    s.submit("k", snap)
    got = s.latest("k")
    got["answers"]["q"] = "changed"
    assert snap["answers"]["q"] == "a"
