"""
Temp Pool — Reusable buffer pool based on size buckets.
=======================================================
Avoids repeated allocation for same-size temporaries.
"""

from __future__ import annotations

import array
from collections import defaultdict


class TempPool:
    """Pool of reusable float32 buffers keyed by size.

    Usage:
        pool = TempPool()
        buf = pool.acquire(1024)
        # ... use buf ...
        pool.release(buf)
    """

    def __init__(self) -> None:
        self._free: dict[int, list[array.array]] = defaultdict(list)
        self._peak_count: int = 0
        self._total_created: int = 0

    def acquire(self, n_floats: int) -> array.array:
        """Get a buffer of at least n_floats. May return a recycled one."""
        bucket = self._free.get(n_floats)
        if bucket:
            return bucket.pop()
        self._total_created += 1
        self._peak_count = max(self._peak_count, self._total_created)
        return array.array("f", bytes(n_floats * 4))

    def release(self, buf: array.array) -> None:
        """Return a buffer to the pool for reuse."""
        self._free[len(buf)].append(buf)

    def clear(self) -> None:
        """Release all pooled buffers."""
        self._free.clear()

    @property
    def pool_size(self) -> int:
        return sum(len(v) for v in self._free.values())
