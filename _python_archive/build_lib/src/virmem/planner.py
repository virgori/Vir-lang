"""
Memory Planner — Lifetime-based buffer reuse for training steps.
=================================================================
Assigns buffers to tensor operations based on liveness intervals.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LiveInterval:
    """Liveness interval for a tensor buffer."""
    tensor_id: int
    size_bytes: int
    start: int      # step index where first used
    end: int        # step index where last used (inclusive)


@dataclass
class BufferAssignment:
    """Maps tensor to a physical buffer slot."""
    tensor_id: int
    buffer_id: int
    offset: int = 0


class MemoryPlanner:
    """Plan buffer reuse across a training step.

    Uses a greedy interval-based algorithm:
    - Sort intervals by start time
    - Reuse expired buffers that fit
    - Track peak memory
    """

    def __init__(self) -> None:
        self._intervals: list[LiveInterval] = []
        self._assignments: list[BufferAssignment] = []
        self._peak_bytes: int = 0

    def add_interval(self, tensor_id: int, size_bytes: int,
                     start: int, end: int) -> None:
        self._intervals.append(LiveInterval(tensor_id, size_bytes, start, end))

    def plan(self) -> list[BufferAssignment]:
        """Run the planner. Returns buffer assignments."""
        # Sort by start time
        intervals = sorted(self._intervals, key=lambda iv: iv.start)

        # Track active buffers: (buffer_id, size, end_time)
        free_buffers: list[tuple[int, int, int]] = []
        next_buf_id = 0
        current_bytes = 0
        self._assignments.clear()

        for iv in intervals:
            # Find a free buffer that fits
            best_idx = -1
            best_waste = float("inf")
            for i, (bid, bsize, bend) in enumerate(free_buffers):
                if bend < iv.start and bsize >= iv.size_bytes:
                    waste = bsize - iv.size_bytes
                    if waste < best_waste:
                        best_idx = i
                        best_waste = waste

            if best_idx >= 0:
                bid, bsize, _ = free_buffers[best_idx]
                free_buffers[best_idx] = (bid, bsize, iv.end)
                self._assignments.append(
                    BufferAssignment(tensor_id=iv.tensor_id, buffer_id=bid))
            else:
                bid = next_buf_id
                next_buf_id += 1
                free_buffers.append((bid, iv.size_bytes, iv.end))
                current_bytes += iv.size_bytes
                self._peak_bytes = max(self._peak_bytes, current_bytes)
                self._assignments.append(
                    BufferAssignment(tensor_id=iv.tensor_id, buffer_id=bid))

        return self._assignments

    @property
    def peak_bytes(self) -> int:
        return self._peak_bytes

    @property
    def num_buffers(self) -> int:
        return len({a.buffer_id for a in self._assignments})
