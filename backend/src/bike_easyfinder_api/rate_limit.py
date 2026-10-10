from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int = 0


class SlidingWindowRateLimiter:
    """Per-process MVP limiter. Put the same limits at the staging edge before beta."""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, bucket: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = monotonic()
        oldest_allowed = now - window_seconds
        with self._lock:
            events = self._events[(key, bucket)]
            while events and events[0] <= oldest_allowed:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                return RateLimitResult(False, retry_after)
            events.append(now)
            return RateLimitResult(True)

