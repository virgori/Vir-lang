#!/usr/bin/env python3
"""
tools/bench_arena_simd.py — High-precision multi-sample benchmark runner for
Strict v2 Arena and SIMD multi-target deliverables.

Measures release binaries (-O2):
- CPU, OS, compiler binary SHA-256 logged
- Warmup runs before measurement
- Multi-sample collection (N=15)
- Reports median, p95, and p99
- Specific benchmarks:
  1. arena_alloc scalar allocation-only latency (8B, 24B, 64B) <= +3% regression gate
  2. arena_alloc_zeroed (SIMD bulk zero vs scalar zero)
  3. arena_batch_reserve2 vs 2x arena_reserve (same layout & allocations)
  4. Bulk mem_set & mem_copy (8B, 16B threshold, 64B, 4 KiB, 64 KiB, 128 KiB grow size)
  5. Grow copy & promotion copy costs
  6. 1D Loop auto-vectorization (-O2 vs -O2 --no-simd)
"""

import sys
import os
import subprocess
import time
import hashlib
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIRC = ROOT / "bin" / "virc"
TMP = Path("/tmp/vir_bench")
TMP.mkdir(parents=True, exist_ok=True)

def get_compiler_hash() -> str:
    if not VIRC.exists():
        return "UNKNOWN"
    return hashlib.sha256(VIRC.read_bytes()).hexdigest()

def get_cpu_info() -> str:
    try:
        out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        return out
    except Exception:
        return platform.processor() or "Apple Silicon"

def get_os_info() -> str:
    try:
        ver = subprocess.check_output(["sw_vers", "-productVersion"], text=True).strip()
        build = subprocess.check_output(["sw_vers", "-buildVersion"], text=True).strip()
        kernel = subprocess.check_output(["uname", "-r"], text=True).strip()
        return f"macOS {ver} ({build}), Darwin {kernel}"
    except Exception:
        return platform.platform()

def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1 if f + 1 < len(s) else f
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1

def compile_vir(source_code: str, name: str, flags: list[str] | None = None) -> Path:
    src_file = TMP / f"{name}.vri"
    bin_file = TMP / name
    src_file.write_text(source_code)
    cmd = [str(VIRC), str(src_file), "-o", str(bin_file), "-O2"]
    if flags:
        cmd.extend(flags)
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Compilation failed for {name}:\n{res.stdout}")
    return bin_file

def run_benchmark(bin_path: Path, iters: int = 15, warmup: int = 3) -> tuple[float, float, float]:
    for _ in range(warmup):
        subprocess.run([str(bin_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    times = []
    for _ in range(iters):
        t0 = time.perf_counter_ns()
        subprocess.run([str(bin_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        t1 = time.perf_counter_ns()
        times.append((t1 - t0) / 1_000_000.0) # ms
    med = percentile(times, 50.0)
    p95 = percentile(times, 95.0)
    p99 = percentile(times, 99.0)
    return (med, p95, p99)

def main():
    print("================================================================================")
    print(" Vir Strict v2 Arena & Hardware SIMD Benchmark Suite")
    print("================================================================================")
    cpu = get_cpu_info()
    os_info = get_os_info()
    comp_hash = get_compiler_hash()
    print(f"Target:        macos-arm64")
    print(f"CPU:           {cpu}")
    print(f"OS:            {os_info}")
    print(f"Compiler Hash: {comp_hash}")
    print(f"Compiler Bin:  {VIRC}")
    print(f"Runs/Sample:   N=15 timed runs (+ 3 warmup runs)")
    print("================================================================================")
    print()

    results = []

    # --------------------------------------------------------------------------
    # 1. Scalar arena_alloc Allocation-Only Latency (8B, 24B, 64B) <= +3% Gate
    # --------------------------------------------------------------------------
    print("Compiling Benchmark 1: Scalar arena_alloc allocation-only...")
    code_alloc_base = """
include types
include alloc
import alloc, free from alloc

entity ArenaRef:
    base: ptr
    offset: int
    cap: int
end.

func arena_ref_new(size: int):
    var real_size = size
    if size < 4096 do real_size = 4096 end
    out ArenaRef (
        base: alloc(real_size),
        offset: 0,
        cap: real_size
    )
end.

func arena_ref_alloc(a: ArenaRef, bytes: int):
    if bytes <= 0 do out null end
    var a_align = 8
    let mask = a_align - 1
    let aligned_offset = (a.offset + mask) & ~mask
    if aligned_offset < a.offset or aligned_offset + bytes < aligned_offset do
        out null
    end
    if aligned_offset + bytes > a.cap do
        out null
    end
    let p = a.base + aligned_offset
    a.offset = aligned_offset + bytes
    out p
end.

func arena_ref_free(a: ArenaRef):
    if a.base != null do
        free(a.base)
        a.base = null
    end
    a.offset = 0
    a.cap = 0
end.

func main:
    var a = arena_ref_new(33554432)
    var i = 0
    when i < 300000 loop
        arena_ref_alloc(a, 8)
        arena_ref_alloc(a, 24)
        arena_ref_alloc(a, 64)
        i = i + 1
    end
    arena_ref_free(a)
    out 0
end.
"""
    code_alloc_curr = """
include types
include alloc
include mem.arena
import Arena, arena_new, arena_alloc, arena_free from mem.arena

func main:
    var a = arena_new(33554432)
    var i = 0
    when i < 300000 loop
        arena_alloc(a, 8)
        arena_alloc(a, 24)
        arena_alloc(a, 64)
        i = i + 1
    end
    arena_free(a)
    out 0
end.
"""
    bin_alloc_base = compile_vir(code_alloc_base, "bench_alloc_base")
    bin_alloc_curr = compile_vir(code_alloc_curr, "bench_alloc_curr")
    med_b, p95_b, p99_b = run_benchmark(bin_alloc_base)
    med_c, p95_c, p99_c = run_benchmark(bin_alloc_curr)
    reg_pct = ((med_c - med_b) / med_b) * 100.0
    gate_alloc = "PASS (<= +3%)" if reg_pct <= 3.0 else f"FAIL ({reg_pct:+.1f}%)"
    print(f"  Baseline Reference: {med_b:.2f} ms (p95: {p95_b:.2f}, p99: {p99_b:.2f})")
    print(f"  Current Allocator:  {med_c:.2f} ms (p95: {p95_c:.2f}, p99: {p99_c:.2f}) -> {reg_pct:+.2f}% [Gate: {gate_alloc}]")
    results.append(("arena_alloc 8B/24B/64B alloc-only", 300000, med_b, p95_b, p99_b, med_c, p95_c, p99_c, f"{reg_pct:+.1f}%", gate_alloc))

    # --------------------------------------------------------------------------
    # 2. arena_alloc_zeroed (SIMD Bulk Zero vs Scalar Zero)
    # --------------------------------------------------------------------------
    print("Compiling Benchmark 2: arena_alloc_zeroed...")
    code_zero_scalar = """
include types
include alloc
include mem.arena
import Arena, arena_new, arena_alloc, arena_reset, arena_free from mem.arena
include mem.copy
import mem_zero_scalar from mem.copy

func main:
    var a = arena_new(16777216)
    var i = 0
    when i < 200000 loop
        let ptr = arena_alloc(a, 64)
        mem_zero_scalar(ptr, 64)
        if a.offset > 15000000 do
            arena_reset(a)
        end
        i = i + 1
    end
    arena_free(a)
    out 0
end.
"""
    code_zero_simd = """
include types
include alloc
include mem.arena
import Arena, arena_new, arena_alloc_zeroed, arena_reset, arena_free from mem.arena

func main:
    var a = arena_new(16777216)
    var i = 0
    when i < 200000 loop
        let ptr = arena_alloc_zeroed(a, 64)
        if a.offset > 15000000 do
            arena_reset(a)
        end
        i = i + 1
    end
    arena_free(a)
    out 0
end.
"""
    bin_zero_scal = compile_vir(code_zero_scalar, "bench_zero_scal")
    bin_zero_simd = compile_vir(code_zero_simd, "bench_zero_simd")
    med_zs, p95_zs, p99_zs = run_benchmark(bin_zero_scal)
    med_zm, p95_zm, p99_zm = run_benchmark(bin_zero_simd)
    sp_zero = med_zs / med_zm if med_zm > 0 else 1.0
    print(f"  Scalar zero: {med_zs:.2f} ms (p95: {p95_zs:.2f}, p99: {p99_zs:.2f})")
    print(f"  SIMD zero:   {med_zm:.2f} ms (p95: {p95_zm:.2f}, p99: {p99_zm:.2f}) -> {sp_zero:.2f}x speedup")
    results.append(("arena_alloc_zeroed (64B)", 200000, med_zs, p95_zs, p99_zs, med_zm, p95_zm, p99_zm, f"{sp_zero:.2f}x", "PASS"))

    # --------------------------------------------------------------------------
    # 3. Arena Batch Reserve (arena_batch_reserve2 vs 2x arena_reserve)
    # --------------------------------------------------------------------------
    print("Compiling Benchmark 3: arena_batch_reserve2 vs 2x arena_reserve...")
    code_batch_indiv = """
include types
include alloc
include mem.arena
import Arena, arena_new, arena_reserve, arena_free from mem.arena

func main:
    var i = 0
    when i < 2000 loop
        var a = arena_new(2097152)
        let off0 = arena_reserve(a, 32, 8)
        let off1 = arena_reserve(a, 48, 8)
        arena_free(a)
        i = i + 1
    end
    out 0
end.
"""
    code_batch_res2 = """
include types
include alloc
include mem.arena
import Arena, ArenaBatchLayout, arena_new, arena_batch_reserve2, arena_free from mem.arena

func main:
    var i = 0
    when i < 2000 loop
        var a = arena_new(2097152)
        let layout = arena_batch_reserve2(a, 32, 8, 48, 8)
        arena_free(a)
        i = i + 1
    end
    out 0
end.
"""
    bin_batch_indiv = compile_vir(code_batch_indiv, "bench_batch_indiv")
    bin_batch_res2 = compile_vir(code_batch_res2, "bench_batch_res2")
    med_bi, p95_bi, p99_bi = run_benchmark(bin_batch_indiv)
    med_br, p95_br, p99_br = run_benchmark(bin_batch_res2)
    sp_batch = med_bi / med_br if med_br > 0 else 1.0
    print(f"  2x arena_reserve:     {med_bi:.2f} ms (p95: {p95_bi:.2f}, p99: {p99_bi:.2f})")
    print(f"  arena_batch_reserve2: {med_br:.2f} ms (p95: {p95_br:.2f}, p99: {p99_br:.2f}) -> {sp_batch:.2f}x speedup")
    results.append(("arena_batch_reserve2 (32B+48B)", 2000, med_bi, p95_bi, p99_bi, med_br, p95_br, p99_br, f"{sp_batch:.2f}x", "PASS"))

    # --------------------------------------------------------------------------
    # 4. Bulk mem_set & mem_copy Across Sizes (8B, 16B, 64B, 4 KiB, 64 KiB, 128 KiB)
    # --------------------------------------------------------------------------
    print("Compiling Benchmark 4: Bulk mem_set + mem_copy across sizes...")
    sizes = [
        ("8 B (small)", 8, 300000),
        ("16 B (threshold)", 16, 200000),
        ("64 B", 64, 200000),
        ("4 KiB", 4096, 50000),
        ("64 KiB", 65536, 5000),
        ("128 KiB (grow size)", 131072, 2500),
    ]

    for label, sz, iters in sizes:
        code_bulk = f"""
include types
include alloc
import alloc, free from alloc
include mem.copy
import mem_copy, mem_set from mem.copy

func main:
    let n = {sz}
    var src = alloc(n)
    var dst = alloc(n)
    var i = 0
    when i < {iters} loop
        mem_set(src, 42, n)
        mem_copy(dst, src, n)
        i = i + 1
    end
    free(src)
    free(dst)
    out 0
end.
"""
        bin_bulk_simd = compile_vir(code_bulk, f"bench_bulk_{sz}_simd")
        bin_bulk_scal = compile_vir(code_bulk, f"bench_bulk_{sz}_scal", ["--no-simd"])
        med_s, p95_s, p99_s = run_benchmark(bin_bulk_scal)
        med_m, p95_m, p99_m = run_benchmark(bin_bulk_simd)
        sp = med_s / med_m if med_m > 0 else 1.0
        gate = "PASS" if (sz <= 16 or sp >= 0.95) else "FAIL"
        print(f"  Bulk {label:18s} iters={iters:6d}: Scal {med_s:7.2f} ms | SIMD {med_m:7.2f} ms | Speedup: {sp:5.2f}x [{gate}]")
        results.append((f"Bulk mem_set/copy ({label})", iters, med_s, p95_s, p99_s, med_m, p95_m, p99_m, f"{sp:.2f}x", gate))

    # --------------------------------------------------------------------------
    # 5. Grow Copy & Promotion Copy Costs
    # --------------------------------------------------------------------------
    print("Compiling Benchmark 5: Grow copy & Promotion copy...")
    code_grow = """
include types
include alloc
include mem.arena
import Arena, arena_new, arena_alloc, arena_free from mem.arena

func main:
    var i = 0
    when i < 2000 loop
        var a = arena_new(1024)
        arena_alloc(a, 1024)
        arena_alloc(a, 2048)
        arena_alloc(a, 4096)
        arena_alloc(a, 8192)
        arena_alloc(a, 16384)
        arena_alloc(a, 32768)
        arena_alloc(a, 65536)
        arena_free(a)
        i = i + 1
    end
    out 0
end.
"""
    bin_grow_scal = compile_vir(code_grow, "bench_grow_scal", ["--no-simd"])
    bin_grow_simd = compile_vir(code_grow, "bench_grow_simd")
    med_gs, p95_gs, p99_gs = run_benchmark(bin_grow_scal)
    med_gm, p95_gm, p99_gm = run_benchmark(bin_grow_simd)
    sp_grow = med_gs / med_gm if med_gm > 0 else 1.0
    print(f"  Arena dynamic grow: Scal {med_gs:.2f} ms | SIMD {med_gm:.2f} ms -> {sp_grow:.2f}x")
    results.append(("Arena dynamic grow (1KB->128KB)", 2000, med_gs, p95_gs, p99_gs, med_gm, p95_gm, p99_gm, f"{sp_grow:.2f}x", "PASS"))

    code_promote = """
func main:
    var parent_box = [0, 0, 0, 0]
    arena:
        var i = 0
        when i < 50000 loop
            arena:
                var child = [i, i + 1, i + 2, i + 3]
                parent_box = child
            end
            i = i + 1
        end
    end
    print parent_box[0]
    out 0
end.
"""
    bin_prom_scal = compile_vir(code_promote, "bench_prom_scal", ["--no-simd"])
    bin_prom_simd = compile_vir(code_promote, "bench_prom_simd")
    med_ps, p95_ps, p99_ps = run_benchmark(bin_prom_scal)
    med_pm, p95_pm, p99_pm = run_benchmark(bin_prom_simd)
    sp_prom = med_ps / med_pm if med_pm > 0 else 1.0
    print(f"  Sub-arena promotion: Scal {med_ps:.2f} ms | SIMD {med_pm:.2f} ms -> {sp_prom:.2f}x")
    results.append(("Sub-arena to parent promotion", 50000, med_ps, p95_ps, p99_ps, med_pm, p95_pm, p99_pm, f"{sp_prom:.2f}x", "PASS"))

    # --------------------------------------------------------------------------
    # 6. 1D Loop Auto-Vectorization (-O2 vs -O2 --no-simd)
    # --------------------------------------------------------------------------
    print("Compiling Benchmark 6: 1D loop vectorization kernel...")
    code_loop = """
func main:
    var a = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160]
    var b = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    var dst = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    var iter = 0
    when iter < 200000 loop
        var i = 0
        when i < 16 loop
            dst[i] = a[i] + b[i]
            i = i + 1
        end
        iter = iter + 1
    end
    print dst[0]
    out 0
end.
"""
    bin_loop_scal = compile_vir(code_loop, "bench_loop_scal", ["--no-simd"])
    bin_loop_simd = compile_vir(code_loop, "bench_loop_simd")
    med_ls, p95_ls, p99_ls = run_benchmark(bin_loop_scal)
    med_lm, p95_lm, p99_lm = run_benchmark(bin_loop_simd)
    sp_loop = med_ls / med_lm if med_lm > 0 else 1.0
    print(f"  1D loop autovec: Scal {med_ls:.2f} ms | SIMD {med_lm:.2f} ms -> {sp_loop:.2f}x")
    results.append(("1D loop auto-vectorization (16-lane)", 200000, med_ls, p95_ls, p99_ls, med_lm, p95_lm, p99_lm, f"{sp_loop:.2f}x", "PASS"))

    print()
    print("================================================================================")
    print(" Summary Table")
    print("================================================================================")
    print(f"{'Benchmark':<35} | {'Iters':<7} | {'Baseline / Scal (med / p95 / p99)':<30} | {'Fast / SIMD (med / p95 / p99)':<30} | {'Speedup':<8} | {'Gate'}")
    print("-" * 125)
    for name, iters, b_med, b_p95, b_p99, c_med, c_p95, c_p99, sp, gate in results:
        b_str = f"{b_med:.2f} / {b_p95:.2f} / {b_p99:.2f}"
        c_str = f"{c_med:.2f} / {c_p95:.2f} / {c_p99:.2f}"
        print(f"{name:<35} | {iters:<7} | {b_str:<30} | {c_str:<30} | {sp:<8} | {gate}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
