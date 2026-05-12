#!/usr/bin/env python3
"""
bench_phase3.py — Phase 3 Benchmark: Vir Compiler Pipeline vs C/Rust/C++/Python
=================================================================================
Measures:
  1. Vir Compilation Pipeline: tokenize → parse → IR build → optimize → codegen
  2. Generated code quality estimates (instruction counts, optimization impact)
  3. Cross-language comparison: equivalent programs in C, C++, Rust, Python

Run:  python3 benchmarks/bench_phase3.py
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VIR_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(VIR_ROOT))

RESULTS = {}
ITERS = 50


def bench(label, iters, fn, *args, category="pipeline"):
    fn(*args)  # warmup
    times = []
    for _ in range(iters):
        t0 = time.perf_counter_ns()
        fn(*args)
        t1 = time.perf_counter_ns()
        times.append((t1 - t0) / 1000.0)
    times.sort()
    median = times[len(times)//2]
    mean = sum(times)/len(times)
    mn, mx = times[0], times[-1]
    RESULTS.setdefault(category, {})[label] = {
        "mean_us": mean, "median_us": median, "min_us": mn, "max_us": mx,
    }
    return median


def format_us(v):
    if v >= 1_000_000:
        return f"{v/1e6:.2f} s"
    if v >= 1_000:
        return f"{v/1e3:.2f} ms"
    return f"{v:.1f} µs"


# ═══════════════════════════════════════════════════════
# 1. VIR PIPELINE BENCHMARKS (Vietnamese source)
# ═══════════════════════════════════════════════════════

VIR_SRC_SIMPLE = "Ta có hàm chính:\n    cho biến x 10;\n    cho biến y 20;\n    tính tổng x y;\n    nói kết_quả;\nxong"

VIR_SRC_COMPLEX = "Ta có hàm fibonacci N:\n    nếu mà N bé hơn 2:\n        trả_lại N;\n    xong\n    cho biến a 0;\n    cho biến b 1;\n    cho biến i 2;\n    lặp mà i bé hơn N:\n        tính tổng a b;\n        gán a b;\n        gán b kết_quả;\n        tính tổng i 1;\n    xong\n    trả_lại b;\nxong\nTa có hàm chính:\n    gọi fibonacci 30;\n    nói kết_quả;\nxong"


def _get_adapter():
    from src.frontend.tokenizer.ngram_tokenizer import NGramTokenizer, LegacySublibBridge
    adapter = LegacySublibBridge()
    return NGramTokenizer(adapter)


def bench_tokenize(src):
    tok = _get_adapter()
    tok.tokenize(src)


def bench_parse(src):
    from src.frontend.parser.parser import Parser
    tok = _get_adapter()
    tokens = tok.tokenize(src)
    p = Parser(tokens)
    p.parse()


def bench_ir_build(ast):
    """Benchmark IRBuilder with pre-parsed AST."""
    from src.ir.instructions.ir_builder import IRBuilder
    builder = IRBuilder()
    builder.build(ast)


def bench_optimize(mod_factory):
    """Benchmark optimizer with a factory that creates fresh modules."""
    from src.ir.opt_passes import Optimizer
    mod = mod_factory()
    opt = Optimizer()
    opt.optimize(mod)


def bench_codegen_x86(mod_factory):
    """Benchmark x86 codegen with a factory."""
    from src.backend.codegen.codegen_x86 import X86_64Codegen
    mod = mod_factory()
    cg = X86_64Codegen()
    cg.generate(mod)


def bench_arm64_codegen(mod_factory):
    """Benchmark ARM64 codegen if available."""
    from src.backend.codegen.codegen import CodeGenerator, TargetArch
    mod = mod_factory()
    cg = CodeGenerator(target=TargetArch.ARM64)
    cg.generate(mod)


def make_ir_module():
    """Create a synthetic IR module for benchmarking."""
    from src.ir.instructions.q_ir import (
        Opcode, QInstruction, QFunction, QModule, VReg, Immediate, Label,
    )
    mod = QModule()
    # fibonacci function in IR
    fib = QFunction(name="fibonacci", params=[VReg(0)])
    fib.body = [
        QInstruction(opcode=Opcode.Q_CMP_LT, dest=VReg(10), src1=VReg(0), src2=Immediate(2)),
        QInstruction(opcode=Opcode.Q_JUMP_IF, dest=Label("base"), src1=VReg(10)),
        QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(1), src1=Immediate(0)),
        QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(2), src1=Immediate(1)),
        QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(3), src1=Immediate(2)),
        QInstruction(opcode=Opcode.Q_LABEL, dest=Label("loop")),
        QInstruction(opcode=Opcode.Q_CMP_GT, dest=VReg(10), src1=VReg(3), src2=VReg(0)),
        QInstruction(opcode=Opcode.Q_JUMP_IF, dest=Label("done"), src1=VReg(10)),
        QInstruction(opcode=Opcode.Q_ADD, dest=VReg(4), src1=VReg(1), src2=VReg(2)),
        QInstruction(opcode=Opcode.Q_MOVE, dest=VReg(1), src1=VReg(2)),
        QInstruction(opcode=Opcode.Q_MOVE, dest=VReg(2), src1=VReg(4)),
        QInstruction(opcode=Opcode.Q_ADD, dest=VReg(3), src1=VReg(3), src2=Immediate(1)),
        QInstruction(opcode=Opcode.Q_JUMP, dest=Label("loop")),
        QInstruction(opcode=Opcode.Q_LABEL, dest=Label("done")),
        QInstruction(opcode=Opcode.Q_RET, dest=VReg(2)),
        QInstruction(opcode=Opcode.Q_LABEL, dest=Label("base")),
        QInstruction(opcode=Opcode.Q_RET, dest=VReg(0)),
    ]
    mod.functions.append(fib)

    main = QFunction(name="main", params=[])
    main.body = [
        QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(30)),
        QInstruction(opcode=Opcode.Q_CALL, dest=VReg(1), src1=Label("fibonacci")),
        QInstruction(opcode=Opcode.Q_PRINT, dest=VReg(1)),
        QInstruction(opcode=Opcode.Q_RET),
    ]
    mod.functions.append(main)
    return mod


def make_large_ir_module():
    """Create a large IR module with many functions."""
    from src.ir.instructions.q_ir import (
        Opcode, QInstruction, QFunction, QModule, VReg, Immediate, Label,
    )
    mod = QModule()
    for i in range(50):
        f = QFunction(name=f"func_{i}", params=[VReg(0), VReg(1)])
        f.body = [
            QInstruction(opcode=Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
            QInstruction(opcode=Opcode.Q_ADD, dest=VReg(3), src1=VReg(2), src2=Immediate(i)),
            QInstruction(opcode=Opcode.Q_MUL, dest=VReg(4), src1=VReg(3), src2=Immediate(2)),
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(5), src1=Immediate(999)),  # dead code
            QInstruction(opcode=Opcode.Q_RET, dest=VReg(4)),
        ]
        mod.functions.append(f)
    main = QFunction(name="main", params=[])
    main.body = [
        QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(1)),
        QInstruction(opcode=Opcode.Q_CALL, dest=VReg(1), src1=Label("func_0")),
        QInstruction(opcode=Opcode.Q_PRINT, dest=VReg(1)),
        QInstruction(opcode=Opcode.Q_RET),
    ]
    mod.functions.append(main)
    return mod


# ═══════════════════════════════════════════════════════
# 2. C / C++ / RUST / PYTHON COMPUTE BENCHMARKS
# ═══════════════════════════════════════════════════════

C_FIB = r"""
#include <stdio.h>
#include <time.h>
long fib(int n) {
    long a=0, b=1;
    for(int i=2;i<=n;i++) { long c=a+b; a=b; b=c; }
    return b;
}
int main() {
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    volatile long r;
    for(int i=0;i<100000;i++) r=fib(30);
    clock_gettime(CLOCK_MONOTONIC,&t1);
    double ns=((t1.tv_sec-t0.tv_sec)*1e9+(t1.tv_nsec-t0.tv_nsec))/100000.0;
    printf("C_fib30: %.1f ns\n", ns);
    return 0;
}
"""

CPP_FIB = r"""
#include <cstdio>
#include <chrono>
long fib(int n) {
    long a=0, b=1;
    for(int i=2;i<=n;i++) { long c=a+b; a=b; b=c; }
    return b;
}
int main() {
    using Clock = std::chrono::high_resolution_clock;
    auto t0 = Clock::now();
    volatile long r;
    for(int i=0;i<100000;i++) r=fib(30);
    auto t1 = Clock::now();
    double ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t1-t0).count()/100000.0;
    printf("CPP_fib30: %.1f ns\n", ns);
    return 0;
}
"""

RUST_FIB = r"""
use std::time::Instant;
fn fib(n: i64) -> i64 {
    let (mut a, mut b) = (0i64, 1i64);
    for _ in 2..=n { let c = a+b; a = b; b = c; }
    b
}
fn main() {
    let t0 = Instant::now();
    let mut r = 0i64;
    for _ in 0..100000 { r = fib(30); }
    let elapsed = t0.elapsed().as_nanos() as f64 / 100000.0;
    println!("Rust_fib30: {:.1} ns (result={})", elapsed, r);
}
"""


def run_c_bench():
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
        f.write(C_FIB)
        src = f.name
    out = src.replace(".c", "")
    try:
        subprocess.run(["cc", "-O2", "-o", out, src], check=True,
                      capture_output=True, timeout=30)
        result = subprocess.run([out], capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        for p in [src, out]:
            try: os.unlink(p)
            except: pass


def run_cpp_bench():
    with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
        f.write(CPP_FIB)
        src = f.name
    out = src.replace(".cpp", "")
    try:
        subprocess.run(["c++", "-O2", "-std=c++17", "-o", out, src], check=True,
                      capture_output=True, timeout=30)
        result = subprocess.run([out], capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        for p in [src, out]:
            try: os.unlink(p)
            except: pass


def run_rust_bench():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write(RUST_FIB)
        src = f.name
    out = src.replace(".rs", "")
    try:
        subprocess.run(["rustc", "-O", "-o", out, src], check=True,
                      capture_output=True, timeout=60)
        result = subprocess.run([out], capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        for p in [src, out]:
            try: os.unlink(p)
            except: pass


def run_python_fib_bench():
    t0 = time.perf_counter_ns()
    for _ in range(100000):
        a, b = 0, 1
        for i in range(2, 31):
            a, b = b, a + b
    elapsed_ns = (time.perf_counter_ns() - t0) / 100000.0
    return f"Python_fib30: {elapsed_ns:.1f} ns"


# ═══════════════════════════════════════════════════════
# 3. COMPILER INTELLIGENCE METRICS
# ═══════════════════════════════════════════════════════

def measure_optimizer_impact():
    from src.ir.opt_passes import Optimizer

    mod = make_large_ir_module()
    before = sum(len(f.body) for f in mod.functions)

    opt = Optimizer()
    opt.optimize(mod)

    after = sum(len(f.body) for f in mod.functions)

    return {
        "ir_before": before,
        "ir_after": after,
        "reduction_pct": round((1 - after/max(before,1)) * 100, 1),
        "stats": {
            "constants_folded": opt.stats.constants_folded,
            "dead_code_removed": opt.stats.dead_code_removed,
            "strength_reduced": opt.stats.strength_reduced,
            "functions_inlined": opt.stats.functions_inlined,
            "cse_eliminated": opt.stats.cse_eliminated,
        }
    }


def measure_codegen_stats():
    from src.backend.codegen.codegen_x86 import X86_64Codegen

    mod = make_ir_module()
    cg = X86_64Codegen()
    asm = cg.generate(mod)

    return {
        "asm_lines": len(asm.split("\n")),
        "functions_emitted": cg.stats.functions_emitted,
        "instructions_emitted": cg.stats.instructions_emitted,
        "stack_slots": cg.stats.stack_slots_used,
    }


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    print("=" * 72)
    print("  Vir Phase 3 — Comprehensive Benchmark")
    print("=" * 72)
    print()

    # ── 1. Pipeline benchmarks ────────────────────────
    print("━━━ 1. Vir Compiler Pipeline ━━━")
    print(f"  {'Benchmark':<45s} {'Median':>12s}")
    print(f"  {'─'*45} {'─'*12}")

    # Tokenizer benchmarks
    for label, src in [("simple", VIR_SRC_SIMPLE),
                       ("complex", VIR_SRC_COMPLEX)]:
        t = bench(f"tokenize [{label}]", ITERS, bench_tokenize, src)
        print(f"  {'tokenize ['+label+']':<45s} {format_us(t):>12s}")

    # Parser benchmarks
    print()
    for label, src in [("simple", VIR_SRC_SIMPLE),
                       ("complex", VIR_SRC_COMPLEX)]:
        t = bench(f"parse [{label}]", ITERS, bench_parse, src)
        print(f"  {'parse ['+label+']':<45s} {format_us(t):>12s}")

    # Optimizer benchmarks (use synthetic IR)
    print()
    t = bench("optimize [fibonacci IR]", ITERS, bench_optimize, make_ir_module)
    print(f"  {'optimize [fibonacci IR]':<45s} {format_us(t):>12s}")
    t = bench("optimize [50-func module]", ITERS, bench_optimize, make_large_ir_module)
    print(f"  {'optimize [50-func module]':<45s} {format_us(t):>12s}")

    # x86 codegen benchmarks
    print()
    t = bench("codegen_x86 [fibonacci IR]", ITERS, bench_codegen_x86, make_ir_module)
    print(f"  {'codegen_x86 [fibonacci IR]':<45s} {format_us(t):>12s}")
    t = bench("codegen_x86 [50-func module]", ITERS, bench_codegen_x86, make_large_ir_module)
    print(f"  {'codegen_x86 [50-func module]':<45s} {format_us(t):>12s}")

    # ARM64 codegen
    print()
    try:
        t = bench("codegen_arm64 [fibonacci IR]", ITERS, bench_arm64_codegen, make_ir_module)
        print(f"  {'codegen_arm64 [fibonacci IR]':<45s} {format_us(t):>12s}")
    except Exception as e:
        print(f"  codegen_arm64: skipped ({type(e).__name__})")

    # Full pipeline (opt + codegen)
    print()
    def full_pipeline_fib():
        from src.ir.opt_passes import Optimizer
        from src.backend.codegen.codegen_x86 import X86_64Codegen
        mod = make_ir_module()
        Optimizer().optimize(mod)
        X86_64Codegen().generate(mod)
    def full_pipeline_large():
        from src.ir.opt_passes import Optimizer
        from src.backend.codegen.codegen_x86 import X86_64Codegen
        mod = make_large_ir_module()
        Optimizer().optimize(mod)
        X86_64Codegen().generate(mod)
    t = bench("full pipeline [fibonacci]", ITERS, full_pipeline_fib)
    print(f"  {'full pipeline [fibonacci]':<45s} {format_us(t):>12s}")
    t = bench("full pipeline [50-func module]", ITERS, full_pipeline_large)
    print(f"  {'full pipeline [50-func module]':<45s} {format_us(t):>12s}")

    # ── 2. Cross-language compute ─────────────────────
    print()
    print("━━━ 2. Cross-Language: fib(30) × 100K iterations ━━━")

    py_result = run_python_fib_bench()
    print(f"  {py_result}")

    c_result = run_c_bench()
    if c_result:
        print(f"  {c_result}")
    else:
        print("  C: (compiler not available)")

    cpp_result = run_cpp_bench()
    if cpp_result:
        print(f"  {cpp_result}")
    else:
        print("  C++: (compiler not available)")

    rust_result = run_rust_bench()
    if rust_result:
        print(f"  {rust_result}")
    else:
        print("  Rust: (compiler not available)")

    # ── 3. Compiler intelligence ──────────────────────
    print()
    print("━━━ 3. Compiler Intelligence Metrics ━━━")

    opt_impact = measure_optimizer_impact()
    print(f"  IR instructions before optimization: {opt_impact['ir_before']}")
    print(f"  IR instructions after optimization:  {opt_impact['ir_after']}")
    print(f"  Reduction: {opt_impact['reduction_pct']}%")
    print(f"  Constants folded:   {opt_impact['stats']['constants_folded']}")
    print(f"  Dead code removed:  {opt_impact['stats']['dead_code_removed']}")
    print(f"  Strength reduced:   {opt_impact['stats']['strength_reduced']}")
    print(f"  Functions inlined:  {opt_impact['stats']['functions_inlined']}")
    print(f"  CSE eliminated:     {opt_impact['stats']['cse_eliminated']}")

    cg_stats = measure_codegen_stats()
    print()
    print(f"  x86_64 codegen stats (fibonacci program):")
    print(f"    Assembly lines:      {cg_stats['asm_lines']}")
    print(f"    Functions emitted:   {cg_stats['functions_emitted']}")
    print(f"    Instructions:        {cg_stats['instructions_emitted']}")
    print(f"    Stack slots:         {cg_stats['stack_slots']}")

    # ── 4. Summary table ─────────────────────────────
    print()
    print("━━━ 4. Summary ━━━")
    print()
    pipeline_fib = RESULTS.get("pipeline", {}).get("full pipeline [fibonacci]", {})
    pipeline_lg = RESULTS.get("pipeline", {}).get("full pipeline [50-func module]", {})
    if pipeline_fib:
        print(f"  Fibonacci (optimize + x86_64 codegen): {format_us(pipeline_fib['median_us'])} median")
    if pipeline_lg:
        print(f"  50-function module (optimize + x86_64):  {format_us(pipeline_lg['median_us'])} median")
    print()

    # Save results
    out_path = VIR_ROOT / "benchmarks" / "bench_phase3_results.json"
    with open(out_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"  Results saved to {out_path}")

    print()
    print("=" * 72)
    print("  Benchmark complete.")
    print("=" * 72)


if __name__ == "__main__":
    main()
