"""Sliding-window rate limiter."""

import time
from collections import OrderedDict, deque
from collections.abc import Callable


class SlidingWindowRateLimiter:
    """Allows ``limit`` hits per ``window`` seconds per key.

    Memory is bounded by ``max_keys`` (least recently seen keys are evicted).
    Used from the event loop only; ``check`` never awaits, so it is atomic.
    """

    def __init__(
        self,
        limit: int,
        window: float = 60.0,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window
        self._max_keys = max_keys
        self._clock = clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()

    def check(self, key: str) -> float | None:
        """Records a hit.

        Returns:
            ``None`` if allowed, otherwise seconds until a slot frees up.
        """
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        self._hits.move_to_end(key)
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return self._window - (now - hits[0])
        hits.append(now)
        while len(self._hits) > self._max_keys:
            self._hits.popitem(last=False)
        return None
