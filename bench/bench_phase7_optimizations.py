#!/usr/bin/env python3
"""
benchmarks/bench_phase7_optimizations.py — Phase 7 Optimization Benchmarks
============================================================================
Measures the performance impact of Phase 7 optimizations:
  1. Bounds Check Elimination (BCE) via Range Analysis
  2. Escape Analysis + Stack Promotion
  3. Deterministic Free (auto Q_FREE)
  4. SIMD auto-vectorization improvements in M→L lowering
  5. Combined optimizer pipeline (11 passes)

Methodology:
  - Warmup: 5 iterations (discarded)
  - Measurement: 50 iterations
  - Compares optimized vs. unoptimized IR pass times
"""

import os
import sys
import time
import statistics
import platform
from dataclasses import dataclass

VIR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, VIR_ROOT)

from src.ir.instructions.q_ir import (
    QModule, QFunction, QInstruction, Opcode,
    VReg, Immediate, Label,
)


# ═══════════════════════════════════════════════════════
# Benchmark infrastructure
# ═══════════════════════════════════════════════════════

@dataclass
class BenchResult:
    name: str
    iterations: int
    times_ns: list[float]

    @property
    def mean_us(self) -> float:
        return statistics.mean(self.times_ns) / 1_000

    @property
    def median_us(self) -> float:
        return statistics.median(self.times_ns) / 1_000

    @property
    def min_us(self) -> float:
        return min(self.times_ns) / 1_000

    @property
    def stdev_us(self) -> float:
        return (statistics.stdev(self.times_ns) / 1_000) if len(self.times_ns) > 1 else 0.0


def run_bench(name, fn, warmup=5, iterations=50):
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        fn()
        times.append(time.perf_counter_ns() - t0)
    return BenchResult(name=name, iterations=len(times), times_ns=times)


# ═══════════════════════════════════════════════════════
# IR Construction Helpers
# ═══════════════════════════════════════════════════════

def build_array_loop_module(n_iters=1000):
    """Build a module with array access in a counted loop — ideal for BCE."""
    instrs = []
    # for i in 0..n:
    #   x = array[i]    -> bounds check can be eliminated
    #   sum += x
    instrs.append(QInstruction(Opcode.Q_LOAD, VReg(0), Immediate(0), None, None))   # sum = 0
    instrs.append(QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(0), None, None))   # i = 0
    instrs.append(QInstruction(Opcode.Q_LOAD, VReg(2), Immediate(n_iters), None, None))  # limit
    instrs.append(QInstruction(Opcode.Q_LABEL, None, None, None, "loop_top"))
    # bounds check
    instrs.append(QInstruction(Opcode.Q_CMP_LT, VReg(3), VReg(1), VReg(2), None))
    instrs.append(QInstruction(Opcode.Q_JUMP_IF_NOT, None, VReg(3), Label("loop_end"), None))
    # array access
    instrs.append(QInstruction(Opcode.Q_BOUNDS_CHECK, VReg(4), VReg(1), VReg(2), None))
    instrs.append(QInstruction(Opcode.Q_LOAD, VReg(5), VReg(1), None, None))
    instrs.append(QInstruction(Opcode.Q_ADD, VReg(0), VReg(0), VReg(5), None))
    # i++
    instrs.append(QInstruction(Opcode.Q_ADD, VReg(1), VReg(1), Immediate(1), None))
    instrs.append(QInstruction(Opcode.Q_JUMP, None, Label("loop_top"), None, None))
    instrs.append(QInstruction(Opcode.Q_LABEL, None, None, None, "loop_end"))
    instrs.append(QInstruction(Opcode.Q_RET, None, VReg(0), None, None))

    func = QFunction(name="array_sum")
    func.body = instrs
    module = QModule()
    module.functions = [func]
    return module


def build_alloc_module(n_allocs=100):
    """Build a module with local allocations — ideal for escape analysis."""
    instrs = []
    for i in range(n_allocs):
        # alloc → use → free pattern
        instrs.append(QInstruction(Opcode.Q_ALLOC, VReg(i), Immediate(64), None, None))
        instrs.append(QInstruction(Opcode.Q_STORE, None, VReg(i), Immediate(i * 7), None))
        instrs.append(QInstruction(Opcode.Q_LOAD, VReg(n_allocs + i), VReg(i), None, None))
    # All allocations are local → should be promoted to stack
    instrs.append(QInstruction(Opcode.Q_RET, None, VReg(n_allocs), None, None))

    func = QFunction(name="local_allocs")
    func.body = instrs
    module = QModule()
    module.functions = [func]
    return module


def build_simd_loop_module(n=256):
    """Build a module with a vectorizable loop — ideal for SIMD autovectorizer."""
    instrs = []
    instrs.append(QInstruction(Opcode.Q_LOAD, VReg(0), Immediate(0), None, None))   # sum
    instrs.append(QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(0), None, None))   # i
    instrs.append(QInstruction(Opcode.Q_LOAD, VReg(2), Immediate(n), None, None))   # limit
    instrs.append(QInstruction(Opcode.Q_LABEL, None, None, None, "vloop"))
    instrs.append(QInstruction(Opcode.Q_CMP_LT, VReg(3), VReg(1), VReg(2), None))
    instrs.append(QInstruction(Opcode.Q_JUMP_IF_NOT, None, VReg(3), Label("vloop_end"), None))
    # body: multiply and accumulate
    instrs.append(QInstruction(Opcode.Q_MUL, VReg(4), VReg(1), VReg(1), None))
    instrs.append(QInstruction(Opcode.Q_ADD, VReg(0), VReg(0), VReg(4), None))
    instrs.append(QInstruction(Opcode.Q_ADD, VReg(1), VReg(1), Immediate(1), None))
    instrs.append(QInstruction(Opcode.Q_JUMP, None, Label("vloop"), None, None))
    instrs.append(QInstruction(Opcode.Q_LABEL, None, None, None, "vloop_end"))
    instrs.append(QInstruction(Opcode.Q_RET, None, VReg(0), None, None))

    func = QFunction(name="simd_sum_sq")
    func.body = instrs
    module = QModule()
    module.functions = [func]
    return module


def build_large_module(n_funcs=10, instrs_per_func=200):
    """Build a large module for full optimizer pipeline benchmarking."""
    module = QModule()
    module.functions = []
    for f in range(n_funcs):
        instrs = []
        for i in range(instrs_per_func):
            instrs.append(QInstruction(Opcode.Q_LOAD, VReg(i), Immediate(i * 3 + 1), None, None))
            instrs.append(QInstruction(Opcode.Q_ADD, VReg(instrs_per_func + i), VReg(i), Immediate(42), None))
            instrs.append(QInstruction(Opcode.Q_MOVE, VReg(2 * instrs_per_func + i), VReg(instrs_per_func + i), None, None))
        instrs.append(QInstruction(Opcode.Q_RET, None, VReg(instrs_per_func), None, None))
        func = QFunction(name=f"fn_{f}")
        func.body = instrs
        module.functions.append(func)
    return module


# ═══════════════════════════════════════════════════════
# Benchmarks
# ═══════════════════════════════════════════════════════

def bench_bce():
    """Benchmark Bounds Check Elimination pass."""
    from src.ir.optimizer.bounds_check_elim import BoundsCheckEliminator
    module = build_array_loop_module(1000)
    bce = BoundsCheckEliminator()

    def fn():
        for func in module.functions:
            bce.run(func)

    return run_bench("BCE Range Analysis", fn)


def bench_escape_analysis():
    """Benchmark Escape Analysis + Stack Promotion."""
    from src.ir.optimizer.escape_analysis import EscapeAnalyzer
    module = build_alloc_module(100)
    ea = EscapeAnalyzer()

    def fn():
        for func in module.functions:
            ea.run(func)

    return run_bench("Escape Analysis", fn)


def bench_deterministic_free():
    """Benchmark Deterministic Free insertion."""
    from src.ir.optimizer.deterministic_free import DeterministicFree
    module = build_alloc_module(100)
    df = DeterministicFree()

    def fn():
        for func in module.functions:
            df.run(func)

    return run_bench("Deterministic Free", fn)


def bench_full_optimizer():
    """Benchmark the full 11-pass optimizer pipeline."""
    from src.ir.optimizer.optimizer import IROptimizer
    module = build_large_module(10, 200)
    optimizer = IROptimizer()

    def fn():
        optimizer.optimize(module)

    return run_bench("Full Optimizer (11 passes)", fn)


def bench_codegen_with_simd():
    """Benchmark code generation with SIMD autovectorization."""
    from src.backend.codegen.codegen import CodeGenerator, TargetArch
    arch = TargetArch.ARM64 if platform.machine() == "arm64" else TargetArch.X86_64
    module = build_simd_loop_module(256)
    cg = CodeGenerator(arch=arch)

    def fn():
        cg.generate(module)

    return run_bench("Codegen + SIMD Vectorizer", fn)


def bench_sri_emission():
    """Benchmark SRI binary emission."""
    from src.backend.codegen.codegen import CodeGenerator, TargetArch
    from src.backend.formats import SRIBinary
    import tempfile

    arch = TargetArch.ARM64 if platform.machine() == "arm64" else TargetArch.X86_64
    module = build_large_module(5, 50)
    cg = CodeGenerator(arch=arch)

    # Pre-generate the SRI
    sri = cg.emit_sri(module, entry="fn_0")
    tmp = tempfile.NamedTemporaryFile(suffix=".sri", delete=False)
    tmp_path = tmp.name
    tmp.close()

    def fn():
        sri.write(tmp_path)

    result = run_bench("SRI Emission", fn)
    os.unlink(tmp_path)
    return result


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════

def main():
    print("═" * 70)
    print("  Vir Phase 7 — Optimization Benchmark Suite")
    print(f"  Platform: {platform.system()} {platform.machine()} | Python {platform.python_version()}")
    print("═" * 70)
    print()

    benchmarks = [
        ("1", bench_bce),
        ("2", bench_escape_analysis),
        ("3", bench_deterministic_free),
        ("4", bench_full_optimizer),
        ("5", bench_codegen_with_simd),
        ("6", bench_sri_emission),
    ]

    results: list[BenchResult] = []

    for idx, bench_fn in benchmarks:
        print(f"  [{idx}/6] Running {bench_fn.__doc__.strip()}...")
        try:
            r = bench_fn()
            results.append(r)
            print(f"         → {r.mean_us:>10.2f} µs (median {r.median_us:.2f} µs, "
                  f"min {r.min_us:.2f} µs, σ {r.stdev_us:.2f} µs)")
        except Exception as e:
            print(f"         → ERROR: {e}")

    # Summary table
    print()
    print("─" * 70)
    print(f"{'Benchmark':<35} {'Mean':>10} {'Median':>10} {'Min':>10} {'σ':>10}")
    print("─" * 70)
    for r in results:
        print(f"{r.name:<35} {r.mean_us:>9.2f}µs {r.median_us:>9.2f}µs "
              f"{r.min_us:>9.2f}µs {r.stdev_us:>9.2f}µs")
    print("─" * 70)

    # Phase 7 targets assessment
    print()
    print("Phase 7 Target Assessment:")
    for r in results:
        if "BCE" in r.name:
            target = 50.0  # µs target for BCE analysis per function
            status = "✓ PASS" if r.mean_us < target else "✗ NEEDS WORK"
            print(f"  BCE Range Analysis:      {r.mean_us:.2f} µs (target <{target} µs) — {status}")
        elif "Escape" in r.name:
            target = 500.0  # 100 allocs × ~2-3µs per alloc
            status = "✓ PASS" if r.mean_us < target else "✗ NEEDS WORK"
            print(f"  Escape Analysis:         {r.mean_us:.2f} µs (target <{target} µs) — {status}")
        elif "Deterministic" in r.name:
            target = 500.0  # 100 allocs × ~2-3µs per alloc
            status = "✓ PASS" if r.mean_us < target else "✗ NEEDS WORK"
            print(f"  Deterministic Free:      {r.mean_us:.2f} µs (target <{target} µs) — {status}")
        elif "Full Optimizer" in r.name:
            target = 5000.0  # 5ms for 10 functions × 200 instrs
            status = "✓ PASS" if r.mean_us < target else "✗ NEEDS WORK"
            print(f"  Full 11-pass Pipeline:   {r.mean_us:.2f} µs (target <{target} µs) — {status}")
        elif "SIMD" in r.name:
            target = 200.0
            status = "✓ PASS" if r.mean_us < target else "✗ NEEDS WORK"
            print(f"  Codegen + SIMD:          {r.mean_us:.2f} µs (target <{target} µs) — {status}")
        elif "SRI" in r.name:
            target = 500.0
            status = "✓ PASS" if r.mean_us < target else "✗ NEEDS WORK"
            print(f"  SRI Binary Emission:     {r.mean_us:.2f} µs (target <{target} µs) — {status}")

    print()
    print("═" * 70)


if __name__ == "__main__":
    main()
