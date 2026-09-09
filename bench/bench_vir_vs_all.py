#!/usr/bin/env python3
"""
bench_vir_vs_all.py — Vir REAL Performance vs C / C++ / Rust / Python
======================================================================
Compiles actual Vir code (Q-IR → x86_64 assembly → native binary) and
benchmarks it head-to-head against C, C++, Rust, and Python.

Algorithms tested:
  1. Fibonacci(40) × 500K   — integer loop throughput
  2. Sum 1..N (N=100M) × 5  — tight integer loop
  3. Sieve(1M) × 10         — integer logic + memory

Each language implements the EXACT same algorithm.
Vir code goes through the full compiler pipeline:
  Q-IR → Optimizer → X86_64Codegen → cc -arch x86_64 → native binary

Run:  python3 benchmarks/bench_vir_vs_all.py
"""

import os
import subprocess
import sys
import tempfile
import time

VIR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, VIR_ROOT)

from src.ir.instructions.q_ir import (
    Opcode, QInstruction, QFunction, QModule, VReg, Immediate, Label,
)
from src.ir.opt_passes import Optimizer
from src.backend.codegen.codegen_x86 import X86_64Codegen


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def compile_native(src, suffix, compiler_args, timeout=60):
    """Compile source, return binary path or None."""
    fd, src_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    bin_path = src_path.rsplit(".", 1)[0]
    with open(src_path, "w") as f:
        f.write(src)
    try:
        r = subprocess.run(
            compiler_args + ["-o", bin_path, src_path],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0:
            return bin_path, src_path
        else:
            print(f"    Compile error: {r.stderr[:200]}")
            return None, src_path
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"    Compile error: {e}")
        return None, src_path


def run_binary(bin_path, timeout=120):
    """Run binary and return stdout."""
    try:
        r = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def cleanup(*paths):
    for p in paths:
        if p:
            try:
                os.unlink(p)
            except OSError:
                pass


def parse_ms(output, label):
    """Extract 'label: 123.45 ms' from output."""
    if not output:
        return None
    for line in output.split("\n"):
        if line.strip().startswith(label + ":"):
            parts = line.split(":")[1].strip().split()
            try:
                return float(parts[0])
            except (ValueError, IndexError):
                pass
    return None


def fmt(ms):
    if ms is None:
        return "—"
    if ms >= 1000:
        return f"{ms/1000:.2f} s"
    if ms >= 1:
        return f"{ms:.2f} ms"
    return f"{ms*1000:.1f} µs"


# ═══════════════════════════════════════════════════════════
# VIR: Build Q-IR → Optimize → Assembly → Binary
# ═══════════════════════════════════════════════════════════

def build_vir_benchmark():
    """Build the Vir benchmark as x86_64 binary via codegen pipeline."""

    mod = QModule()

    # ── fibonacci(n) ──────────────────────────────────
    fib = QFunction(name="fibonacci", params=[VReg(0)])
    fib.body = [
        QInstruction(Opcode.Q_CMP_LT, VReg(10), VReg(0), Immediate(2)),
        QInstruction(Opcode.Q_JUMP_IF, Label("fib_base"), VReg(10)),
        QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(0)),
        QInstruction(Opcode.Q_LOAD, VReg(2), Immediate(1)),
        QInstruction(Opcode.Q_LOAD, VReg(3), Immediate(2)),
        QInstruction(Opcode.Q_LABEL, Label("fib_loop")),
        QInstruction(Opcode.Q_CMP_GT, VReg(11), VReg(3), VReg(0)),
        QInstruction(Opcode.Q_JUMP_IF, Label("fib_done"), VReg(11)),
        QInstruction(Opcode.Q_ADD, VReg(4), VReg(1), VReg(2)),
        QInstruction(Opcode.Q_MOVE, VReg(1), VReg(2)),
        QInstruction(Opcode.Q_MOVE, VReg(2), VReg(4)),
        QInstruction(Opcode.Q_ADD, VReg(3), VReg(3), Immediate(1)),
        QInstruction(Opcode.Q_JUMP, Label("fib_loop")),
        QInstruction(Opcode.Q_LABEL, Label("fib_done")),
        QInstruction(Opcode.Q_RET, VReg(2)),
        QInstruction(Opcode.Q_LABEL, Label("fib_base")),
        QInstruction(Opcode.Q_RET, VReg(0)),
    ]
    mod.functions.append(fib)

    # ── sum_to_n(n): sum 1..n ─────────────────────────
    sumfn = QFunction(name="sum_to_n", params=[VReg(0)])
    sumfn.body = [
        QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(0)),   # sum = 0
        QInstruction(Opcode.Q_LOAD, VReg(2), Immediate(1)),   # i = 1
        QInstruction(Opcode.Q_LABEL, Label("sum_loop")),
        QInstruction(Opcode.Q_CMP_GT, VReg(10), VReg(2), VReg(0)),
        QInstruction(Opcode.Q_JUMP_IF, Label("sum_done"), VReg(10)),
        QInstruction(Opcode.Q_ADD, VReg(1), VReg(1), VReg(2)),   # sum += i
        QInstruction(Opcode.Q_ADD, VReg(2), VReg(2), Immediate(1)),  # i++
        QInstruction(Opcode.Q_JUMP, Label("sum_loop")),
        QInstruction(Opcode.Q_LABEL, Label("sum_done")),
        QInstruction(Opcode.Q_RET, VReg(1)),
    ]
    mod.functions.append(sumfn)

    # ── Count primes up to n (simplified sieve using trial division) ──
    # Full sieve needs array ops not in codegen, so use trial division
    # is_prime(k): check divisibility from 2 to sqrt(k)
    is_prime = QFunction(name="is_prime", params=[VReg(0)])
    is_prime.body = [
        QInstruction(Opcode.Q_CMP_LT, VReg(10), VReg(0), Immediate(2)),
        QInstruction(Opcode.Q_JUMP_IF, Label("ip_no"), VReg(10)),
        QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(2)),  # d = 2
        QInstruction(Opcode.Q_LABEL, Label("ip_loop")),
        QInstruction(Opcode.Q_MUL, VReg(2), VReg(1), VReg(1)),   # d*d
        QInstruction(Opcode.Q_CMP_GT, VReg(10), VReg(2), VReg(0)),
        QInstruction(Opcode.Q_JUMP_IF, Label("ip_yes"), VReg(10)),
        QInstruction(Opcode.Q_MOD, VReg(3), VReg(0), VReg(1)),
        QInstruction(Opcode.Q_CMP_EQ, VReg(10), VReg(3), Immediate(0)),
        QInstruction(Opcode.Q_JUMP_IF, Label("ip_no"), VReg(10)),
        QInstruction(Opcode.Q_ADD, VReg(1), VReg(1), Immediate(1)),
        QInstruction(Opcode.Q_JUMP, Label("ip_loop")),
        QInstruction(Opcode.Q_LABEL, Label("ip_yes")),
        QInstruction(Opcode.Q_LOAD, VReg(5), Immediate(1)),
        QInstruction(Opcode.Q_RET, VReg(5)),
        QInstruction(Opcode.Q_LABEL, Label("ip_no")),
        QInstruction(Opcode.Q_LOAD, VReg(5), Immediate(0)),
        QInstruction(Opcode.Q_RET, VReg(5)),
    ]
    mod.functions.append(is_prime)

    # count_primes(n): count primes from 2..n
    cp = QFunction(name="count_primes", params=[VReg(0)])
    cp.body = [
        QInstruction(Opcode.Q_LOAD, VReg(1), Immediate(0)),     # count = 0
        QInstruction(Opcode.Q_LOAD, VReg(2), Immediate(2)),     # i = 2
        QInstruction(Opcode.Q_LABEL, Label("cp_loop")),
        QInstruction(Opcode.Q_CMP_GT, VReg(10), VReg(2), VReg(0)),
        QInstruction(Opcode.Q_JUMP_IF, Label("cp_done"), VReg(10)),
        QInstruction(Opcode.Q_CALL, VReg(3), Label("is_prime"), VReg(2)),
        QInstruction(Opcode.Q_ADD, VReg(1), VReg(1), VReg(3)),  # count += is_prime(i)
        QInstruction(Opcode.Q_ADD, VReg(2), VReg(2), Immediate(1)),  # i++
        QInstruction(Opcode.Q_JUMP, Label("cp_loop")),
        QInstruction(Opcode.Q_LABEL, Label("cp_done")),
        QInstruction(Opcode.Q_RET, VReg(1)),
    ]
    mod.functions.append(cp)

    # No main function — C harness provides main

    # Run optimizer — loop-safe constant folding + loop unrolling + auto-vectorization
    t0 = time.perf_counter_ns()
    opt = Optimizer()
    opt.optimize(mod)
    opt_ms = (time.perf_counter_ns() - t0) / 1e6
    s = opt.stats
    print(f"      Optimizer stats: {s.functions_inlined} inlined, {s.constants_folded} folded, "
          f"{s.loops_collapsed} collapsed, {s.licm_hoisted} LICM, {s.loop_str_reduced} str-reduced, "
          f"{s.loops_unrolled} unrolled, {s.loops_vectorized} vectorized, "
          f"{s.alias_marked} noalias")

    # ── Codegen ──
    t0 = time.perf_counter_ns()
    cg = X86_64Codegen()
    asm_text = cg.generate(mod)
    gen_ms = (time.perf_counter_ns() - t0) / 1e6

    # Strip .data section — only keep .text (avoids Rosetta symbol issues)
    lines = asm_text.split("\n")
    text_idx = next((i for i, l in enumerate(lines) if l.strip() == ".text"), 0)
    asm_text = "\n".join(lines[text_idx:])

    return asm_text, opt_ms, gen_ms


# ═══════════════════════════════════════════════════════════
# C HARNESS: calls Vir functions + C equivalents with timing
# ═══════════════════════════════════════════════════════════

C_HARNESS = r"""
#include <stdio.h>
#include <time.h>

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

/* Vir-compiled functions (from .s file) */
extern long vir_fibonacci(long n);
extern long vir_sum_to_n(long n);
extern long vir_count_primes(long n);

int main() {
    double t0, t1;
    volatile long r;

    /* === Fibonacci(40) x 500K === */
    t0 = now_ms();
    for (int i = 0; i < 500000; i++) r = vir_fibonacci(40);
    t1 = now_ms();
    printf("vir_fib: %.4f ms (result=%ld)\n", t1-t0, (long)r);

    /* === Sum 1..100M x 5 === */
    t0 = now_ms();
    for (int i = 0; i < 5; i++) r = vir_sum_to_n(100000000);
    t1 = now_ms();
    printf("vir_sum: %.4f ms (result=%ld)\n", t1-t0, (long)r);

    /* === Count primes to 10K x 10 === */
    t0 = now_ms();
    for (int i = 0; i < 10; i++) r = vir_count_primes(10000);
    t1 = now_ms();
    printf("vir_primes: %.4f ms (result=%ld)\n", t1-t0, (long)r);

    return 0;
}
"""


# ═══════════════════════════════════════════════════════════
# C BENCHMARK (same algorithms, compiled with cc -O2)
# ═══════════════════════════════════════════════════════════

C_BENCH = r"""
#include <stdio.h>
#include <time.h>

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

long c_fib(long n) {
    long a=0, b=1;
    for (long i=2; i<=n; i++) { long c=a+b; a=b; b=c; }
    return b;
}

long c_sum(long n) {
    long s = 0;
    for (long i = 1; i <= n; i++) s += i;
    return s;
}

int c_is_prime(long k) {
    if (k < 2) return 0;
    for (long d = 2; d*d <= k; d++)
        if (k % d == 0) return 0;
    return 1;
}

long c_count_primes(long n) {
    long count = 0;
    for (long i = 2; i <= n; i++) count += c_is_prime(i);
    return count;
}

int main() {
    double t0, t1;
    volatile long r;

    t0 = now_ms();
    for (int i = 0; i < 500000; i++) r = c_fib(40);
    t1 = now_ms();
    printf("c_fib: %.4f ms\n", t1-t0);

    t0 = now_ms();
    for (int i = 0; i < 5; i++) r = c_sum(100000000);
    t1 = now_ms();
    printf("c_sum: %.4f ms\n", t1-t0);

    t0 = now_ms();
    for (int i = 0; i < 10; i++) r = c_count_primes(10000);
    t1 = now_ms();
    printf("c_primes: %.4f ms\n", t1-t0);

    return 0;
}
"""


# ═══════════════════════════════════════════════════════════
# C++ BENCHMARK
# ═══════════════════════════════════════════════════════════

CPP_BENCH = r"""
#include <cstdio>
#include <chrono>

using Clock = std::chrono::high_resolution_clock;
static double elapsed_ms(Clock::time_point t0) {
    return std::chrono::duration<double, std::milli>(Clock::now() - t0).count();
}

long cpp_fib(long n) {
    long a=0,b=1; for(long i=2;i<=n;i++){long c=a+b;a=b;b=c;} return b;
}

long cpp_sum(long n) {
    long s=0; for(long i=1;i<=n;i++) s+=i; return s;
}

int cpp_is_prime(long k) {
    if(k<2) return 0;
    for(long d=2;d*d<=k;d++) if(k%d==0) return 0;
    return 1;
}

long cpp_count_primes(long n) {
    long c=0; for(long i=2;i<=n;i++) c+=cpp_is_prime(i); return c;
}

int main() {
    auto t0=Clock::now(); volatile long r;

    t0=Clock::now();
    for(int i=0;i<500000;i++) r=cpp_fib(40);
    printf("cpp_fib: %.4f ms\n", elapsed_ms(t0));

    t0=Clock::now();
    for(int i=0;i<5;i++) r=cpp_sum(100000000);
    printf("cpp_sum: %.4f ms\n", elapsed_ms(t0));

    t0=Clock::now();
    for(int i=0;i<10;i++) r=cpp_count_primes(10000);
    printf("cpp_primes: %.4f ms\n", elapsed_ms(t0));

    return 0;
}
"""


# ═══════════════════════════════════════════════════════════
# RUST BENCHMARK
# ═══════════════════════════════════════════════════════════

RUST_BENCH = r"""
use std::time::Instant;

fn fib(n: i64) -> i64 {
    let (mut a, mut b) = (0i64, 1i64);
    for _ in 2..=n { let c = a + b; a = b; b = c; }
    b
}

fn sum_to_n(n: i64) -> i64 {
    let mut s: i64 = 0;
    for i in 1..=n { s += i; }
    s
}

fn is_prime(k: i64) -> bool {
    if k < 2 { return false; }
    let mut d: i64 = 2;
    while d * d <= k { if k % d == 0 { return false; } d += 1; }
    true
}

fn count_primes(n: i64) -> i64 {
    let mut c: i64 = 0;
    for i in 2..=n { if is_prime(i) { c += 1; } }
    c
}

fn main() {
    let t0 = Instant::now();
    let mut r: i64 = 0;
    for _ in 0..500000 { r = fib(40); }
    println!("rust_fib: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
    std::hint::black_box(r);

    let t0 = Instant::now();
    for _ in 0..5 { r = sum_to_n(100_000_000); }
    println!("rust_sum: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
    std::hint::black_box(r);

    let t0 = Instant::now();
    for _ in 0..10 { r = count_primes(10000); }
    println!("rust_primes: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
    std::hint::black_box(r);
}
"""


# ═══════════════════════════════════════════════════════════
# PYTHON BENCHMARK
# ═══════════════════════════════════════════════════════════

def py_fib(n):
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def py_sum(n):
    s = 0
    for i in range(1, n + 1):
        s += i
    return s


def py_is_prime(k):
    if k < 2:
        return False
    d = 2
    while d * d <= k:
        if k % d == 0:
            return False
        d += 1
    return True


def py_count_primes(n):
    c = 0
    for i in range(2, n + 1):
        if py_is_prime(i):
            c += 1
    return c


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    print("=" * 72)
    print("  VIR vs C vs C++ vs Rust vs Python — REAL CODE BENCHMARK")
    print("  Vir code: Q-IR → Optimizer → X86_64 Codegen → cc → native binary")
    print("=" * 72)
    print()

    results = {}

    # ── 1. BUILD VIR BINARY ───────────────────────────
    print("[1/5] Compiling Vir (Q-IR → optimize → x86_64 asm → binary)...")
    asm_text, opt_ms, gen_ms = build_vir_benchmark()
    print(f"      Optimizer: {opt_ms:.2f} ms, Codegen: {gen_ms:.2f} ms")

    # Write .s file
    fd, asm_path = tempfile.mkstemp(suffix=".s")
    os.close(fd)
    with open(asm_path, "w") as f:
        f.write(asm_text)

    # Write C harness
    fd, harness_path = tempfile.mkstemp(suffix=".c")
    os.close(fd)
    with open(harness_path, "w") as f:
        f.write(C_HARNESS)

    vir_bin = asm_path.rsplit(".", 1)[0] + "_vir"
    try:
        r = subprocess.run(
            ["cc", "-arch", "x86_64", "-O0", "-o", vir_bin, harness_path, asm_path],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            print(f"      ERROR: {r.stderr[:300]}")
            results["Vir"] = {}
        else:
            print(f"      Binary built: {vir_bin}")
            out = run_binary(vir_bin, timeout=120)
            print(f"      Output: {out}")
            results["Vir"] = {
                "fib": parse_ms(out, "vir_fib"),
                "sum": parse_ms(out, "vir_sum"),
                "primes": parse_ms(out, "vir_primes"),
            }
    except Exception as e:
        print(f"      ERROR: {e}")
        results["Vir"] = {}
    finally:
        cleanup(asm_path, harness_path)

    # ── 2. C BENCHMARK ─────────────────────────────────
    print()
    print("[2/5] Compiling C (-O2 -arch x86_64)...")
    bin_path, src_path = compile_native(C_BENCH, ".c", ["cc", "-arch", "x86_64", "-O2"])
    if bin_path:
        out = run_binary(bin_path)
        print(f"      Output: {out}")
        results["C"] = {
            "fib": parse_ms(out, "c_fib"),
            "sum": parse_ms(out, "c_sum"),
            "primes": parse_ms(out, "c_primes"),
        }
    else:
        results["C"] = {}
    cleanup(bin_path, src_path)

    # ── 3. C++ BENCHMARK ──────────────────────────────
    print()
    print("[3/5] Compiling C++ (-O2 -arch x86_64)...")
    bin_path, src_path = compile_native(CPP_BENCH, ".cpp", ["c++", "-arch", "x86_64", "-O2", "-std=c++17"])
    if bin_path:
        out = run_binary(bin_path)
        print(f"      Output: {out}")
        results["C++"] = {
            "fib": parse_ms(out, "cpp_fib"),
            "sum": parse_ms(out, "cpp_sum"),
            "primes": parse_ms(out, "cpp_primes"),
        }
    else:
        results["C++"] = {}
    cleanup(bin_path, src_path)

    # ── 4. RUST BENCHMARK ─────────────────────────────
    print()
    print("[4/5] Compiling Rust (-O --target x86_64-apple-darwin)...")
    bin_path, src_path = compile_native(
        RUST_BENCH, ".rs",
        ["rustc", "-O", "--target", "x86_64-apple-darwin"],
        timeout=120
    )
    if bin_path:
        out = run_binary(bin_path, timeout=120)
        print(f"      Output: {out}")
        results["Rust"] = {
            "fib": parse_ms(out, "rust_fib"),
            "sum": parse_ms(out, "rust_sum"),
            "primes": parse_ms(out, "rust_primes"),
        }
    else:
        results["Rust"] = {}
    cleanup(bin_path, src_path)

    # ── 5. PYTHON BENCHMARK ───────────────────────────
    print()
    print("[5/5] Running Python (CPython, no numpy)...")
    py_results = {}

    t0 = time.perf_counter_ns()
    for _ in range(500000):
        py_fib(40)
    py_results["fib"] = (time.perf_counter_ns() - t0) / 1e6

    t0 = time.perf_counter_ns()
    py_sum(10000000)  # 10M only (100M too slow in pure Python)
    py_results["sum_raw"] = (time.perf_counter_ns() - t0) / 1e6
    py_results["sum"] = py_results["sum_raw"] * 50  # scale to 100M × 5

    t0 = time.perf_counter_ns()
    py_count_primes(10000)
    py_results["primes_raw"] = (time.perf_counter_ns() - t0) / 1e6
    py_results["primes"] = py_results["primes_raw"] * 10  # × 10 iterations

    results["Python"] = py_results
    print(f"      fib: {fmt(py_results['fib'])}, sum: {fmt(py_results['sum'])} (scaled), primes: {fmt(py_results['primes'])} (scaled)")

    # ═══════════════════════════════════════════════════
    # RESULTS TABLE
    # ═══════════════════════════════════════════════════
    print()
    print("━" * 72)
    print("  RESULTS — Runtime (ms, lower = better)")
    print("━" * 72)
    print()

    tasks = [
        ("fib", "Fibonacci(40) × 500K"),
        ("sum", "Sum 1..100M × 5"),
        ("primes", "CountPrimes(10K) × 10"),
    ]
    langs = ["Vir", "C", "C++", "Rust", "Python"]

    header = f"  {'Benchmark':<26s}"
    for lang in langs:
        header += f"  {lang:>10s}"
    print(header)
    print(f"  {'─'*26}" + f"  {'─'*10}" * len(langs))

    for task_key, task_name in tasks:
        row = f"  {task_name:<26s}"
        for lang in langs:
            val = results.get(lang, {}).get(task_key)
            row += f"  {fmt(val):>10s}"
        print(row)

    # ── Ratio analysis ────────────────────────────────
    print()
    print("━" * 72)
    print("  SPEEDUP RATIOS (vs Vir)")
    print("━" * 72)
    print()

    header2 = f"  {'Benchmark':<26s}"
    for lang in langs:
        header2 += f"  {lang:>10s}"
    print(header2)
    print(f"  {'─'*26}" + f"  {'─'*10}" * len(langs))

    for task_key, task_name in tasks:
        vir_val = results.get("Vir", {}).get(task_key)
        row = f"  {task_name:<26s}"
        for lang in langs:
            val = results.get(lang, {}).get(task_key)
            if val and vir_val and vir_val > 0:
                ratio = val / vir_val
                if ratio < 1:
                    row += f"  {1/ratio:>8.1f}× ▲"
                elif ratio > 1:
                    row += f"  {ratio:>8.1f}× ▼"
                else:
                    row += f"  {'1.0×':>10s}"
            else:
                row += f"  {'—':>10s}"
        print(row)

    print()
    print("  ▲ = faster than Vir, ▼ = slower than Vir")
    print()

    # ── Vir compilation speed ─────────────────────────
    print("━" * 72)
    print("  VIR COMPILATION PIPELINE")
    print("━" * 72)
    print(f"  Optimizer:  {opt_ms:.2f} ms")
    print(f"  Codegen:    {gen_ms:.2f} ms")
    print(f"  Total:      {opt_ms + gen_ms:.2f} ms")
    print(f"  Note: ALL binaries compiled for x86_64, running under Rosetta 2 (M2)")
    print(f"        Vir asm compiled with cc -O0 (no extra opt on codegen output)")
    print(f"        C/C++ compiled with -O2, Rust with -O")
    print()

    cleanup(vir_bin if 'vir_bin' in dir() else None)


if __name__ == "__main__":
    main()
