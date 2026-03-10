"""
Arena Allocator — Bump-pointer allocator for training step temporaries.
=======================================================================
All allocations within a step are freed together at step boundary.
"""

from __future__ import annotations

import array
from dataclasses import dataclass, field


@dataclass
class ArenaBlock:
    """A single contiguous memory block."""
    data: array.array  # 'f' = float32
    used: int = 0

    @property
    def capacity(self) -> int:
        return len(self.data)

    @property
    def remaining(self) -> int:
        return self.capacity - self.used


class ArenaAllocator:
    """Bump-pointer arena for temporary tensor storage.

    Usage:
        arena = ArenaAllocator(block_size=1_000_000)
        buf = arena.alloc(1024)   # returns array slice
        arena.reset()             # free everything at step boundary
    """

    def __init__(self, block_size: int = 1_000_000) -> None:
        self._block_size = block_size
        self._blocks: list[ArenaBlock] = []
        self._current: int = -1
        self._peak_bytes: int = 0
        self._total_allocated: int = 0

    def alloc(self, n_floats: int) -> array.array:
        """Allocate n_floats from the arena. Returns a new array view."""
        if self._current < 0 or self._blocks[self._current].remaining < n_floats:
            size = max(self._block_size, n_floats)
            blk = ArenaBlock(data=array.array("f", bytes(size * 4)))
            self._blocks.append(blk)
            self._current = len(self._blocks) - 1

        blk = self._blocks[self._current]
        start = blk.used
        blk.used += n_floats
        self._total_allocated += n_floats * 4
        self._peak_bytes = max(self._peak_bytes, self._total_allocated)
        return blk.data[start:start + n_floats]

    def reset(self) -> None:
        """Reset all blocks for reuse (no deallocation)."""
        for blk in self._blocks:
            blk.used = 0
        self._current = 0 if self._blocks else -1
        self._total_allocated = 0

    @property
    def peak_bytes(self) -> int:
        return self._peak_bytes

    @property
    def num_blocks(self) -> int:
        return len(self._blocks)
