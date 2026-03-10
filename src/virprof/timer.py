"""
Timer — High-precision timing utilities for profiling.
========================================================
Context-manager and decorator forms for measuring elapsed time.
Uses time.perf_counter_ns for nanosecond-precision on macOS.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator


@dataclass
class TimerRecord:
    """Single recorded timing measurement."""
    name: str
    elapsed_ns: int
    start_ns: int
    end_ns: int

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_ns / 1_000_000

    @property
    def elapsed_us(self) -> float:
        return self.elapsed_ns / 1_000

    @property
    def elapsed_s(self) -> float:
        return self.elapsed_ns / 1_000_000_000

    def __repr__(self) -> str:
        if self.elapsed_ns >= 1_000_000:
            return f"Timer({self.name}: {self.elapsed_ms:.2f}ms)"
        return f"Timer({self.name}: {self.elapsed_us:.1f}µs)"


class Timer:
    """Accumulating timer that records multiple measurements.

    Usage:
        timer = Timer("matmul")
        with timer:
            do_matmul()
        with timer:
            do_matmul()
        print(timer.summary())
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.records: list[TimerRecord] = []
        self._start_ns: int = 0

    def __enter__(self) -> "Timer":
        self._start_ns = time.perf_counter_ns()
        return self

    def __exit__(self, *_exc: object) -> None:
        end_ns = time.perf_counter_ns()
        self.records.append(TimerRecord(
            name=self.name,
            elapsed_ns=end_ns - self._start_ns,
            start_ns=self._start_ns,
            end_ns=end_ns,
        ))

    @property
    def total_ns(self) -> int:
        return sum(r.elapsed_ns for r in self.records)

    @property
    def total_ms(self) -> float:
        return self.total_ns / 1_000_000

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def mean_ns(self) -> float:
        return self.total_ns / self.count if self.count > 0 else 0.0

    @property
    def mean_ms(self) -> float:
        return self.mean_ns / 1_000_000

    @property
    def min_ns(self) -> int:
        return min((r.elapsed_ns for r in self.records), default=0)

    @property
    def max_ns(self) -> int:
        return max((r.elapsed_ns for r in self.records), default=0)

    def last(self) -> TimerRecord | None:
        return self.records[-1] if self.records else None

    def reset(self) -> None:
        self.records.clear()

    def summary(self) -> str:
        if not self.records:
            return f"Timer({self.name}: no measurements)"
        return (
            f"Timer({self.name}: "
            f"total={self.total_ms:.2f}ms, "
            f"count={self.count}, "
            f"mean={self.mean_ms:.3f}ms, "
            f"min={self.min_ns / 1_000_000:.3f}ms, "
            f"max={self.max_ns / 1_000_000:.3f}ms)"
        )


@contextmanager
def profile_block(name: str) -> Generator[Timer, None, None]:
    """One-shot profiling context manager that prints elapsed time.

    Usage:
        with profile_block("init") as t:
            do_init()
        # prints: [profile] init: 12.34ms
    """
    timer = Timer(name)
    timer.__enter__()
    try:
        yield timer
    finally:
        timer.__exit__(None, None, None)
        rec = timer.last()
        if rec:
            print(f"[profile] {rec}")
