"""In-memory sliding-window rate limiter. Keys are salted hashes, never raw IPs, and live only in RAM."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

_SALT = secrets.token_hex(8)  # per-process: hashed keys cannot be linked across restarts


class RateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0) -> None:
        self.limit, self.window = limit, window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        k = hashlib.sha256((_SALT + key).encode()).hexdigest()[:16]
        with self._lock:
            q = self._hits[k]
            while q and t - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(t)
            if len(self._hits) > 5000:  # bound memory: drop idle keys
                for old in [x for x, d in self._hits.items() if not d or t - d[-1] > self.window]:
                    self._hits.pop(old, None)
            return True
