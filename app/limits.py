"""Small thread-safe, per-process budgets for this single-admin local prototype."""

import math
from collections import deque
from threading import Lock
from time import monotonic


class LocalBudget:
    def __init__(self, limit: int, window: int, concurrent: int | None = None, clock=monotonic):
        self.limit, self.window, self.concurrent = limit, window, concurrent
        self.clock = clock
        self.events = deque()
        self.active = 0
        self.lock = Lock()

    def enter(self) -> tuple[str | None, int]:
        with self.lock:
            now = self.clock()
            while self.events and self.events[0] <= now - self.window:
                self.events.popleft()
            if len(self.events) >= self.limit:
                return "local_limit", max(1, math.ceil(self.events[0] + self.window - now))
            if self.concurrent is not None and self.active >= self.concurrent:
                return "local_busy", 1
            self.events.append(now)
            self.active += 1
            return None, 0

    def leave(self):
        with self.lock:
            self.active -= 1

    def reset(self):
        with self.lock:
            self.events.clear()
