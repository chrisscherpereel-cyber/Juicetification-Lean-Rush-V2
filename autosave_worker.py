"""autosave_worker.py — saves student progress off the click path.

PERFORMANCE: the Lean Rush used to save progress with a synchronous Dropbox
upload (encrypt + HTTPS round trip, plus rate-limit back-off sleeps) inside the
rerun of every answer, so every click waited on the network. Saves now go to a
small pool of worker threads shared by the whole server process.

Guarantees:
  * latest-wins  — a newer snapshot for the same student replaces one still
    waiting, so a burst of clicks costs one upload, not ten;
  * ordered      — one student's uploads never run concurrently, so an older
    snapshot can never overwrite a newer one;
  * read-your-writes — until a snapshot is confirmed uploaded, `latest()` hands
    back a copy of it, so a student who refreshes straight after answering is
    restored from it rather than from the older copy in storage;
  * retried      — a failed upload is retried (3 attempts in all) unless a
    newer snapshot has superseded it.

This is a plain imported module, so it lives once per server process (Streamlit
re-executes app.py on every rerun, but imported modules are cached).
"""
from __future__ import annotations

import json
import threading
import time
from typing import Callable, Dict, Hashable, Optional, Set, Tuple


class BackgroundSaver:
    WORKERS = 3
    ATTEMPTS = 3

    def __init__(self, save_fn: Callable, workers: int = WORKERS,
                 retry_delay: float = 1.0):
        self._save = save_fn
        self._retry_delay = retry_delay
        self._cv = threading.Condition()
        self._pending: Dict[Hashable, Tuple[dict, int]] = {}
        self._inflight: Set[Hashable] = set()
        self._latest: Dict[Hashable, dict] = {}
        for i in range(workers):
            threading.Thread(target=self._loop, daemon=True,
                             name=f"lean-rush-autosave-{i}").start()

    # ---- called from the app (script threads) ---------------------------
    def submit(self, key: Hashable, snap: dict) -> None:
        """Queue `snap` (a JSON-able dict that the caller will not mutate)."""
        with self._cv:
            self._pending[key] = (snap, 0)
            self._latest[key] = snap
            self._cv.notify()

    def latest(self, key: Hashable) -> Optional[dict]:
        """The newest snapshot not yet confirmed saved, as an independent copy
        (exactly what a JSON round trip through storage would return)."""
        with self._cv:
            snap = self._latest.get(key)
        return None if snap is None else json.loads(json.dumps(snap))

    def wait_idle(self, timeout: float = 30.0) -> bool:
        """Block until nothing is queued or uploading (tests / shutdown)."""
        end = time.monotonic() + timeout
        with self._cv:
            while self._pending or self._inflight:
                left = end - time.monotonic()
                if left <= 0:
                    return False
                self._cv.wait(left)
        return True

    # ---- worker threads -------------------------------------------------
    def _next(self):
        for key in self._pending:          # dicts keep insertion (FIFO) order
            if key not in self._inflight:
                return key
        return None

    def _loop(self):
        while True:
            with self._cv:
                key = self._next()
                while key is None:
                    self._cv.wait()
                    key = self._next()
                snap, attempt = self._pending.pop(key)
                self._inflight.add(key)
            ok = False
            try:
                self._save(key, snap)
                ok = True
            except Exception:
                time.sleep(self._retry_delay * (1 + attempt))
            with self._cv:
                self._inflight.discard(key)
                if ok:
                    if self._latest.get(key) is snap:
                        self._latest.pop(key, None)
                elif key not in self._pending and attempt + 1 < self.ATTEMPTS:
                    self._pending[key] = (snap, attempt + 1)
                # after the last failed attempt the snapshot stays in _latest:
                # it is still the student's real state, so a refresh served by
                # this process restores it rather than the older stored copy
                self._cv.notify_all()


_lock = threading.Lock()
_SAVER: Optional[BackgroundSaver] = None


def get_saver(save_fn: Callable) -> BackgroundSaver:
    """The process-wide saver (created on first use)."""
    global _SAVER
    if _SAVER is None:
        with _lock:
            if _SAVER is None:
                _SAVER = BackgroundSaver(save_fn)
    return _SAVER
