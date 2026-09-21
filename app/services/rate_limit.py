"""Simple in-process spacing of outbound API calls."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Minimum interval between acquire() calls. Shared across worker threads."""

    def __init__(self, *, per_minute: int) -> None:
        self._interval = 0.0 if per_minute <= 0 else 60.0 / per_minute
        self._lock = threading.Lock()
        self._next_at = 0.0

    def acquire(self) -> None:
        if self._interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            self._next_at = max(now, self._next_at) + self._interval
        if wait > 0:
            time.sleep(wait)
