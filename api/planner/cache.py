"""Small in-memory TTL + LRU cache."""

import time
from collections import OrderedDict
from collections.abc import Callable


class TTLCache[K, V]:
    """Bounded cache with per-entry expiry.

    Not thread-safe by design: it is only used from the event loop, with no
    awaits inside its methods.
    """

    def __init__(
        self,
        max_entries: int,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_entries
        self._ttl = ttl_seconds
        self._clock = clock
        self._data: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K) -> V | None:
        """Returns a live value (refreshing LRU order) or ``None``."""
        entry = self._data.get(key)
        if entry is None:
            return None
        expires, value = entry
        if self._clock() >= expires:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: K, value: V) -> None:
        """Stores a value, evicting the least recently used if full."""
        if self._ttl <= 0:
            return
        self._data[key] = (self._clock() + self._ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)
