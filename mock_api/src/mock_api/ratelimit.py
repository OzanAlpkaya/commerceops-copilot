"""Sliding-window rate limit per API client, kept in memory.

State lives in this process, so the service runs a single uvicorn worker.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # seconds until a slot frees up; 0 when allowed


class SlidingWindowLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> Decision:
        """Count one request for `key` unless it is over the limit."""
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, math.ceil(hits[0] + self.window - now))
                return Decision(False, self.limit, 0, retry_after)
            hits.append(now)
            return Decision(True, self.limit, self.limit - len(hits), 0)
