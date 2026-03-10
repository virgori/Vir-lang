"""
Microbenchmark — Quick startup-time benchmarks for kernel selection.
"""

from __future__ import annotations

import time
import array
import math

from src.virplat.cpu_probe import CPUInfo


def _bench_scalar_fma(n: int = 1_000_000) -> float:
    """Benchmark scalar FMA throughput. Returns MFLOPS."""
    a = 1.0001
    b = 0.9999
    c = 0.0
    t0 = time.perf_counter_ns()
    for _ in range(n):
        c = a * b + c
    dt = time.perf_counter_ns() - t0
    _ = c  # prevent dead-code elimination
    mflops = (n * 2) / (dt / 1e3)  # 2 flops per FMA, dt in ns -> us
    return mflops


def _bench_memory_bandwidth(size_kb: int = 256) -> float:
    """Benchmark memory bandwidth (MB/s) with sequential scan."""
    n = size_kb * 256  # number of 32-bit ints
    buf = array.array("f", [0.0]) * n
    t0 = time.perf_counter_ns()
    total = 0.0
    for i in range(n):
        total += buf[i]
    dt = time.perf_counter_ns() - t0
    _ = total
    bytes_read = n * 4
    mbps = bytes_read / (dt / 1e9) / (1024 * 1024)
    return mbps


class MicroBench:
    """Quick startup benchmarks for kernel selection tuning."""

    def __init__(self) -> None:
        self.scalar_mflops: float = 0.0
        self.mem_bandwidth_mbps: float = 0.0

    def run(self) -> None:
        self.scalar_mflops = _bench_scalar_fma()
        self.mem_bandwidth_mbps = _bench_memory_bandwidth()

    def summary(self) -> str:
        return (
            f"MicroBench: scalar FMA {self.scalar_mflops:.1f} MFLOPS, "
            f"mem BW {self.mem_bandwidth_mbps:.1f} MB/s"
        )
