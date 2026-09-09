"""One run per target, four at once, shared by everyone watching it.

A visitor's connection is not the run. The run lives here on its own thread; each connection reads
its events from the beginning, so a reconnect, a second tab or a second visitor attaches to the run
already in flight instead of starting another. The budget is taken by the work, not by the
connection, so a browser that walks away does not hold a slot.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from .models import Brief

AT_ONCE = 4
WAIT = 300
BUSY = "Standup is busy with four other people. Try again in a minute."
BROKE = "Standup could not finish this run. Try again in a minute."

BUDGET = threading.Semaphore(AT_ONCE)
INFLIGHT: dict[str, "Run"] = {}
_GUARD = threading.Lock()


class Run:
    def __init__(self, target: str):
        self.target = target
        self.started = time.perf_counter()
        self.events: list[tuple[str, object]] = []
        self._cond = threading.Condition()

    def emit(self, kind: str, payload: object) -> None:
        with self._cond:
            self.events.append((kind, payload))
            self._cond.notify_all()

    def event(self, index: int, timeout: float = WAIT) -> tuple[str, object]:
        """The index-th event, waiting for it if it has not happened yet. Blocking: call off the loop."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while index >= len(self.events):
                left = deadline - time.monotonic()
                if left <= 0:
                    return "failed", BROKE
                self._cond.wait(left)
            return self.events[index]


def plain(exc: BaseException) -> str:
    """One sentence a person can act on. The pipeline's own honest line passes through."""
    message = str(exc).strip()
    return message if isinstance(exc, RuntimeError) and message.startswith("Standup") else BROKE


def watch(target: str, work: Callable[[Callable[[str], None]], Brief],
          on_brief: Callable[[str, Brief], None] | None = None) -> Run:
    """The run for this target, started if none is in flight. `on_brief`, when given, is called with
    the finished brief the moment it exists — regardless of whether anyone ever reads the run's
    events, so a completed brief is not lost when every watcher has walked away."""
    with _GUARD:
        run = INFLIGHT.get(target)
        if run is None:
            run = Run(target)
            INFLIGHT[target] = run
            threading.Thread(target=_work, args=(run, work, on_brief), daemon=True).start()
        return run


def _work(run: Run, work: Callable[[Callable[[str], None]], Brief],
          on_brief: Callable[[str, Brief], None] | None = None) -> None:
    try:
        if not BUDGET.acquire(blocking=False):
            run.emit("failed", BUSY)
            return
        try:
            brief = work(lambda line: run.emit("progress", line))
            if on_brief is not None:
                on_brief(run.target, brief)
            run.emit("brief", brief)
        except Exception as exc:
            run.emit("failed", plain(exc))
        finally:
            BUDGET.release()
    finally:
        with _GUARD:
            INFLIGHT.pop(run.target, None)
