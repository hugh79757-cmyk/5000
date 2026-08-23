"""Sliding-window rate limiter (stdlib only).

Usage:
    limiter = RateLimiter(limit=8, window_seconds=3600)
    limiter.wait_if_needed()   # blocks via time.sleep() if window is full
    limiter.record()           # call after a successful API invocation

ponytail: single-process in-memory only; no cross-process persistence.
If the scheduler and dispatcher both harvest, add a file/DB-backed store.
"""

import time
from collections import deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._calls = deque()  # timestamps of recorded calls

    def _prune(self, now: float) -> None:
        while self._calls and now - self._calls[0] >= self.window_seconds:
            self._calls.popleft()

    def allowed(self) -> bool:
        """True if a new call would fit within the window."""
        self._prune(time.time())
        return len(self._calls) < self.limit

    def wait_if_needed(self) -> None:
        """Block until a slot frees up. Never exceeds the hard limit."""
        while True:
            self._prune(time.time())
            if len(self._calls) < self.limit:
                return
            sleep_for = self.window_seconds - (time.time() - self._calls[0])
            if sleep_for <= 0:
                continue
            time.sleep(min(sleep_for + 0.01, 60.0))  # cap chunk sleeps

    def record(self) -> None:
        """Record one call occurrence."""
        self._calls.append(time.time())
