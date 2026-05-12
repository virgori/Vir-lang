#!/usr/bin/env python3
"""
Vir AI Stack — Cross-Language Performance Benchmark
=====================================================
Benchmarks Vir stdlib algorithms against equivalent implementations
in C, Python (numpy), Rust, and Go across these tasks:

  1. GEMM (Matrix Multiply)          — matrix.vri vs others
  2. Softmax                          — nn.vri (Two-Pass Online) vs others
  3. Kahan-Welford Variance           — stats.vri vs others
  4. Flash Attention                  — attention.vri vs others
  5. Elementwise Fusion (mul+add+relu)— auto_fusion.py vs others
  6. Vector Dot Product (Kahan)       — vector.vri vs others

For Vir: we simulate the exact same algorithm in Python to measure
the algorithm's computational cost (op count, memory traffic).
The actual Vir → ARM64 codegen adds NEON vectorization on top,
so real Vir perf is ≥ these numbers.

For C/Rust/Go: we compile and run actual native code.
For Python: numpy (BLAS-backed) and pure Python.
"""

import os
import sys
import time
import json
import math
import ctypes
import subprocess
import tempfile
import statistics
from pathlib import Path
from typing import Any

WARMUP = 2
REPEATS = 10

RESULTS: list[dict[str, Any]] = []

# ═══════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════

def bench(fn, *, warmup=WARMUP, repeats=REPEATS):
    """Benchmark a function, return (median_ms, min_ms, max_ms)."""
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        times.append((t1 - t0) / 1e6)  # ms
    return statistics.median(times), min(times), max(times)

def record(task, lang, size, median_ms, min_ms, max_ms, notes=""):
    RESULTS.append({
        "task": task, "lang": lang, "size": size,
        "median_ms": round(median_ms, 4),
        "min_ms": round(min_ms, 4),
        "max_ms": round(max_ms, 4),
        "notes": notes,
    })
    print(f"  {lang:12s} {size:>12s}  {median_ms:10.3f} ms  ({notes})")

def compile_and_run_c(code: str, timeout: int = 30) -> float:
    """Compile C code, run it, return the elapsed ms printed to stdout."""
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
        f.write(code)
        c_path = f.name
    out_path = c_path.replace(".c", "")
    try:
        subprocess.run(
            ["cc", "-O3", "-march=native", "-o", out_path, c_path, "-lm"],
            check=True, capture_output=True, timeout=timeout,
        )
        result = subprocess.run(
            [out_path], capture_output=True, text=True, timeout=timeout,
        )
        return float(result.stdout.strip())
    finally:
        for p in (c_path, out_path):
            try: os.unlink(p)
            except: pass

def compile_and_run_rust(code: str, timeout: int = 60) -> float:
    """Compile Rust code (single file), run it, return elapsed ms."""
    tmpdir = tempfile.mkdtemp()
    src_path = os.path.join(tmpdir, "main.rs")
    out_path = os.path.join(tmpdir, "main")
    with open(src_path, "w") as f:
        f.write(code)
    try:
        subprocess.run(
            ["rustc", "-O", "-o", out_path, src_path],
            check=True, capture_output=True, timeout=timeout,
        )
        result = subprocess.run(
            [out_path], capture_output=True, text=True, timeout=timeout,
        )
        return float(result.stdout.strip())
    except FileNotFoundError:
        return -1.0  # rustc not installed
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

def compile_and_run_go(code: str, timeout: int = 60) -> float:
    """Compile Go code, run it, return elapsed ms."""
    tmpdir = tempfile.mkdtemp()
    src_path = os.path.join(tmpdir, "main.go")
    with open(src_path, "w") as f:
        f.write(code)
    try:
        result = subprocess.run(
            ["go", "run", src_path],
            capture_output=True, text=True, timeout=timeout,
        )
        return float(result.stdout.strip())
    except FileNotFoundError:
        return -1.0  # go not installed
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════
# Task 1: GEMM (Matrix Multiply)
# ═══════════════════════════════════════════════════════

def bench_gemm():
    print("\n═══ Task 1: GEMM (Matrix Multiply) ═══")
    N = 512

    # --- Python (numpy BLAS) ---
    try:
        import numpy as np
        A = np.random.randn(N, N)
        B = np.random.randn(N, N)
        med, mn, mx = bench(lambda: A @ B)
        record("GEMM", "Python/numpy", f"{N}x{N}", med, mn, mx, "BLAS-backed")
    except ImportError:
        pass

    # --- Python (pure) ---
    def pure_matmul(A, B, N):
        C = [[0.0]*N for _ in range(N)]
        for i in range(N):
            for k in range(N):
                aik = A[i][k]
                for j in range(N):
                    C[i][j] += aik * B[k][j]
        return C

    # Only for small N (pure python is slow)
    sN = 128
    Ap = [[float(i*sN+j) * 0.001 for j in range(sN)] for i in range(sN)]
    Bp = [[float(i*sN+j) * 0.001 for j in range(sN)] for i in range(sN)]
    med, mn, mx = bench(lambda: pure_matmul(Ap, Bp, sN), warmup=1, repeats=3)
    record("GEMM", "Python/pure", f"{sN}x{sN}", med, mn, mx, "3 nested loops")

    # --- Vir (tiled GEMM algorithm, simulated) ---
    def vir_tiled_gemm(A, B, N, TILE=64, MICRO=4):
        C = [[0.0]*N for _ in range(N)]
        for i0 in range(0, N, TILE):
            for j0 in range(0, N, TILE):
                for k0 in range(0, N, TILE):
                    ie = min(i0+TILE, N)
                    je = min(j0+TILE, N)
                    ke = min(k0+TILE, N)
                    for i in range(i0, ie, MICRO):
                        for j in range(j0, je, MICRO):
                            for ii in range(i, min(i+MICRO, ie)):
                                for jj in range(j, min(j+MICRO, je)):
                                    acc = C[ii][jj]
                                    for k in range(k0, ke):
                                        acc += A[ii][k] * B[k][jj]
                                    C[ii][jj] = acc
        return C

    med, mn, mx = bench(lambda: vir_tiled_gemm(Ap, Bp, sN), warmup=1, repeats=3)
    record("GEMM", "Vir/tiled", f"{sN}x{sN}", med, mn, mx, "64×64→4×4 tiles, FMA pattern")

    # --- C ---
    c_code = f"""
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#define N {N}
static double A[N][N], B[N][N], C[N][N];
int main() {{
    srand(42);
    for(int i=0;i<N;i++) for(int j=0;j<N;j++) {{
        A[i][j]=(double)rand()/RAND_MAX;
        B[i][j]=(double)rand()/RAND_MAX;
    }}
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    for(int rep=0;rep<5;rep++) {{
        for(int i=0;i<N;i++) for(int j=0;j<N;j++) C[i][j]=0;
        for(int i=0;i<N;i++) for(int k=0;k<N;k++) {{
            double aik=A[i][k];
            for(int j=0;j<N;j++) C[i][j]+=aik*B[k][j];
        }}
    }}
    clock_gettime(CLOCK_MONOTONIC,&t1);
    double ms=((t1.tv_sec-t0.tv_sec)*1e9+(t1.tv_nsec-t0.tv_nsec))/1e6/5.0;
    printf("%.4f\\n",ms);
    return 0;
}}
"""
    try:
        ms = compile_and_run_c(c_code)
        record("GEMM", "C/-O3", f"{N}x{N}", ms, ms, ms, "ikj loop, -O3 -march=native")
    except Exception as e:
        print(f"  C: skipped ({e})")

    # --- Rust ---
    rust_code = f"""
use std::time::Instant;
const N: usize = {N};
fn main() {{
    let mut a = vec![0.0f64; N*N];
    let mut b = vec![0.0f64; N*N];
    let mut c = vec![0.0f64; N*N];
    let mut seed: u64 = 42;
    for i in 0..N*N {{
        seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
        a[i] = (seed as f64) / (u64::MAX as f64);
        seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
        b[i] = (seed as f64) / (u64::MAX as f64);
    }}
    let mut total = 0u128;
    for _ in 0..5 {{
        for x in c.iter_mut() {{ *x = 0.0; }}
        let t0 = Instant::now();
        for i in 0..N {{
            for k in 0..N {{
                let aik = a[i*N+k];
                for j in 0..N {{
                    c[i*N+j] += aik * b[k*N+j];
                }}
            }}
        }}
        total += t0.elapsed().as_nanos();
    }}
    println!("{{:.4}}", total as f64 / 5.0 / 1e6);
}}
"""
    try:
        ms = compile_and_run_rust(rust_code)
        if ms > 0.0:
            record("GEMM", "Rust/-O", f"{N}x{N}", ms, ms, ms, "ikj loop, -O")
    except Exception as e:
        print(f"  Rust: skipped ({e})")

    # --- Go ---
    go_code = f"""
package main
import ("fmt";"time")
const N = {N}
func main() {{
    a := make([]float64, N*N)
    b := make([]float64, N*N)
    c := make([]float64, N*N)
    seed := uint64(42)
    for i := range a {{
        seed = seed*6364136223846793005 + 1
        a[i] = float64(seed) / float64(^uint64(0))
        seed = seed*6364136223846793005 + 1
        b[i] = float64(seed) / float64(^uint64(0))
    }}
    var total int64
    for rep := 0; rep < 5; rep++ {{
        for i := range c {{ c[i] = 0 }}
        t0 := time.Now()
        for i := 0; i < N; i++ {{
            for k := 0; k < N; k++ {{
                aik := a[i*N+k]
                for j := 0; j < N; j++ {{
                    c[i*N+j] += aik * b[k*N+j]
                }}
            }}
        }}
        total += time.Since(t0).Nanoseconds()
    }}
    fmt.Printf("%.4f\\n", float64(total)/5.0/1e6)
}}
"""
    try:
        ms = compile_and_run_go(go_code)
        if ms > 0.0:
            record("GEMM", "Go", f"{N}x{N}", ms, ms, ms, "ikj loop")
    except Exception as e:
        print(f"  Go: skipped ({e})")


# ═══════════════════════════════════════════════════════
# Task 2: Softmax
# ═══════════════════════════════════════════════════════

def bench_softmax():
    print("\n═══ Task 2: Softmax ═══")
    N = 100_000

    try:
        import numpy as np
        x = np.random.randn(N)
        def np_softmax(x):
            e = np.exp(x - x.max())
            return e / e.sum()
        med, mn, mx = bench(lambda: np_softmax(x))
        record("Softmax", "Python/numpy", str(N), med, mn, mx, "3-pass: max, exp, div")
    except ImportError:
        pass

    # Vir: Two-Pass Online Softmax (CUSTOM)
    def vir_softmax(x, n):
        running_max = x[0]
        sum_exp = 1.0
        for i in range(1, n):
            v = x[i]
            if v > running_max:
                sum_exp = sum_exp * math.exp(running_max - v)
                running_max = v
                sum_exp += 1.0
            else:
                sum_exp += math.exp(v - running_max)
        out = [0.0] * n
        inv = 1.0 / sum_exp
        for i in range(n):
            out[i] = math.exp(x[i] - running_max) * inv
        return out

    x_list = [float(i * 0.001 - 50.0) for i in range(N)]
    med, mn, mx = bench(lambda: vir_softmax(x_list, N), warmup=1, repeats=5)
    record("Softmax", "Vir/online", str(N), med, mn, mx, "2-pass online (CUSTOM)")

    # Python pure 3-pass
    def py_softmax(x, n):
        mx_val = max(x)
        exps = [math.exp(v - mx_val) for v in x]
        s = sum(exps)
        return [e / s for e in exps]
    med, mn, mx = bench(lambda: py_softmax(x_list, N), warmup=1, repeats=5)
    record("Softmax", "Python/pure", str(N), med, mn, mx, "3-pass standard")

    # C
    c_code = f"""
#include <stdio.h>
#include <math.h>
#include <time.h>
#define N {N}
static double x[N], out[N];
int main() {{
    for(int i=0;i<N;i++) x[i]=(double)i*0.001-50.0;
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    for(int rep=0;rep<20;rep++) {{
        double rm=x[0], se=1.0;
        for(int i=1;i<N;i++) {{
            if(x[i]>rm) {{ se=se*exp(rm-x[i]); rm=x[i]; se+=1.0; }}
            else {{ se+=exp(x[i]-rm); }}
        }}
        double inv=1.0/se;
        for(int i=0;i<N;i++) out[i]=exp(x[i]-rm)*inv;
    }}
    clock_gettime(CLOCK_MONOTONIC,&t1);
    double ms=((t1.tv_sec-t0.tv_sec)*1e9+(t1.tv_nsec-t0.tv_nsec))/1e6/20.0;
    printf("%.4f\\n",ms);
    return 0;
}}
"""
    try:
        ms = compile_and_run_c(c_code)
        record("Softmax", "C/-O3", str(N), ms, ms, ms, "2-pass online, -O3")
    except Exception as e:
        print(f"  C: skipped ({e})")


# ═══════════════════════════════════════════════════════
# Task 3: Welford Variance (Kahan-compensated)
# ═══════════════════════════════════════════════════════

def bench_welford():
    print("\n═══ Task 3: Welford Variance ═══")
    N = 1_000_000

    try:
        import numpy as np
        x = np.random.randn(N)
        med, mn, mx = bench(lambda: np.var(x))
        record("Variance", "Python/numpy", str(N), med, mn, mx, "np.var (two-pass)")
    except ImportError:
        pass

    x_list = [float(i) * 0.001 for i in range(N)]

    # Vir: Kahan-Welford
    def vir_welford(x, n):
        mean = 0.0; m2 = 0.0; comp = 0.0
        for i in range(n):
            delta = x[i] - mean
            mean += delta / (i + 1)
            delta2 = x[i] - mean
            term = delta * delta2
            y = term - comp
            s = m2 + y
            comp = (s - m2) - y
            m2 = s
        return m2 / n

    med, mn, mx = bench(lambda: vir_welford(x_list, N), warmup=1, repeats=5)
    record("Variance", "Vir/KW", str(N), med, mn, mx, "Kahan-Welford (CUSTOM)")

    # Python pure two-pass
    def py_var(x, n):
        m = sum(x) / n
        return sum((v - m)**2 for v in x) / n
    med, mn, mx = bench(lambda: py_var(x_list, N), warmup=1, repeats=3)
    record("Variance", "Python/pure", str(N), med, mn, mx, "two-pass sum+var")

    c_code = f"""
#include <stdio.h>
#include <time.h>
#define N {N}
static double x[N];
int main() {{
    for(int i=0;i<N;i++) x[i]=(double)i*0.001;
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    double var_val = 0;
    for(int rep=0;rep<20;rep++) {{
        double mean=0, m2=0, comp=0;
        for(int i=0;i<N;i++) {{
            double delta=x[i]-mean;
            mean+=delta/(i+1);
            double delta2=x[i]-mean;
            double term=delta*delta2;
            double y=term-comp;
            double s=m2+y;
            comp=(s-m2)-y;
            m2=s;
        }}
        var_val=m2/(double)N;
    }}
    clock_gettime(CLOCK_MONOTONIC,&t1);
    double ms=((t1.tv_sec-t0.tv_sec)*1e9+(t1.tv_nsec-t0.tv_nsec))/1e6/20.0;
    printf("%.4f\\n",ms);
    return 0;
}}
"""
    try:
        ms = compile_and_run_c(c_code)
        record("Variance", "C/-O3", str(N), ms, ms, ms, "Kahan-Welford, -O3")
    except Exception as e:
        print(f"  C: skipped ({e})")


# ═══════════════════════════════════════════════════════
# Task 4: Flash Attention
# ═══════════════════════════════════════════════════════

def bench_flash_attention():
    print("\n═══ Task 4: Flash Attention ═══")
    N, d = 256, 64

    try:
        import numpy as np
        Q = np.random.randn(N, d)
        K = np.random.randn(N, d)
        V = np.random.randn(N, d)
        scale = 1.0 / math.sqrt(d)

        # Standard attention (materializes N×N)
        def std_attention(Q, K, V, scale):
            scores = Q @ K.T * scale
            scores -= scores.max(axis=1, keepdims=True)
            e = np.exp(scores)
            attn = e / e.sum(axis=1, keepdims=True)
            return attn @ V

        med, mn, mx = bench(lambda: std_attention(Q, K, V, scale))
        record("Attention", "Python/numpy", f"{N}×{d}", med, mn, mx, "standard O(N²) memory")
    except ImportError:
        pass

    # Vir: Flash Attention (tiled online softmax)
    def vir_flash(Q, K, V, N, d, scale, TILE=32):
        row_max = [-1e30] * N
        row_sum = [0.0] * N
        Out = [[0.0]*d for _ in range(N)]

        for kv0 in range(0, N, TILE):
            kve = min(kv0 + TILE, N)
            for q0 in range(0, N, TILE):
                qe = min(q0 + TILE, N)
                # Score tile
                for qi in range(q0, qe):
                    for ki in range(kv0, kve):
                        s = sum(Q[qi][j]*K[ki][j] for j in range(d)) * scale
                        # Online softmax update
                        old_max = row_max[qi]
                        new_max = max(old_max, s)
                        alpha = math.exp(old_max - new_max)
                        row_sum[qi] = row_sum[qi] * alpha + math.exp(s - new_max)
                        for j in range(d):
                            Out[qi][j] = Out[qi][j] * alpha + math.exp(s - new_max) * V[ki][j]
                        row_max[qi] = new_max

        for i in range(N):
            inv = 1.0 / max(row_sum[i], 1e-30)
            for j in range(d):
                Out[i][j] *= inv
        return Out

    Q_l = [[float(i*d+j)*0.01 for j in range(d)] for i in range(N)]
    K_l = [[float((i+1)*d+j)*0.01 for j in range(d)] for i in range(N)]
    V_l = [[float((i+2)*d+j)*0.01 for j in range(d)] for i in range(N)]
    med, mn, mx = bench(lambda: vir_flash(Q_l, K_l, V_l, N, d, 1.0/math.sqrt(d)), warmup=1, repeats=3)
    record("Attention", "Vir/flash", f"{N}×{d}", med, mn, mx, "O(N) mem, tiled online softmax (CUSTOM)")

    # C flash attention
    c_code = f"""
#include <stdio.h>
#include <math.h>
#include <string.h>
#include <time.h>
#define N {N}
#define D {d}
#define TILE 32
static double Q[N][D], K[N][D], V[N][D], O[N][D];
static double row_max[N], row_sum[N];
int main() {{
    for(int i=0;i<N;i++) for(int j=0;j<D;j++) {{
        Q[i][j]=(double)(i*D+j)*0.01;
        K[i][j]=(double)((i+1)*D+j)*0.01;
        V[i][j]=(double)((i+2)*D+j)*0.01;
    }}
    double scale = 1.0/sqrt((double)D);
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    for(int rep=0;rep<5;rep++) {{
        for(int i=0;i<N;i++) {{ row_max[i]=-1e30; row_sum[i]=0; }}
        memset(O,0,sizeof(O));
        for(int kv0=0;kv0<N;kv0+=TILE) {{
            int kve=kv0+TILE; if(kve>N) kve=N;
            for(int q0=0;q0<N;q0+=TILE) {{
                int qe=q0+TILE; if(qe>N) qe=N;
                for(int qi=q0;qi<qe;qi++) {{
                    for(int ki=kv0;ki<kve;ki++) {{
                        double s=0;
                        for(int j=0;j<D;j++) s+=Q[qi][j]*K[ki][j];
                        s*=scale;
                        double om=row_max[qi], nm=om>s?om:s;
                        double alpha=exp(om-nm);
                        double p=exp(s-nm);
                        row_sum[qi]=row_sum[qi]*alpha+p;
                        for(int j=0;j<D;j++) O[qi][j]=O[qi][j]*alpha+p*V[ki][j];
                        row_max[qi]=nm;
                    }}
                }}
            }}
        }}
        for(int i=0;i<N;i++) {{ double inv=1.0/row_sum[i]; for(int j=0;j<D;j++) O[i][j]*=inv; }}
    }}
    clock_gettime(CLOCK_MONOTONIC,&t1);
    double ms=((t1.tv_sec-t0.tv_sec)*1e9+(t1.tv_nsec-t0.tv_nsec))/1e6/5.0;
    printf("%.4f\\n",ms);
    return 0;
}}
"""
    try:
        ms = compile_and_run_c(c_code)
        record("Attention", "C/-O3", f"{N}×{d}", ms, ms, ms, "flash tiled, -O3")
    except Exception as e:
        print(f"  C: skipped ({e})")


# ═══════════════════════════════════════════════════════
# Task 5: Elementwise Chain Fusion
# ═══════════════════════════════════════════════════════

def bench_fusion():
    print("\n═══ Task 5: Elementwise Chain Fusion (MUL+ADD+RELU) ═══")
    N = 1_000_000

    try:
        import numpy as np
        a = np.random.randn(N)
        b = np.random.randn(N)
        c = np.random.randn(N)
        # Unfused (3 separate ops, 3 intermediate buffers)
        def unfused(a, b, c):
            tmp1 = a * b          # alloc + write
            tmp2 = tmp1 + c       # alloc + write
            return np.maximum(tmp2, 0)  # alloc + write
        med, mn, mx = bench(lambda: unfused(a, b, c))
        record("EWFusion", "Python/numpy", str(N), med, mn, mx, "3 ops, 3 allocations")

        # Fused (single expression — numpy still allocates intermediates internally)
        def np_fused(a, b, c):
            return np.maximum(a * b + c, 0)
        med, mn, mx = bench(lambda: np_fused(a, b, c))
        record("EWFusion", "numpy/expr", str(N), med, mn, mx, "single expr, still 3 allocs internally")
    except ImportError:
        pass

    # Vir: fused kernel (single loop, zero intermediates)
    a_l = [float(i)*0.001 for i in range(N)]
    b_l = [float(i)*0.002 for i in range(N)]
    c_l = [float(i)*0.003 for i in range(N)]

    def vir_fused(a, b, c, n):
        out = [0.0] * n
        for i in range(n):
            v = a[i] * b[i] + c[i]
            out[i] = v if v > 0.0 else 0.0
        return out
    med, mn, mx = bench(lambda: vir_fused(a_l, b_l, c_l, N), warmup=1, repeats=3)
    record("EWFusion", "Vir/fused", str(N), med, mn, mx, "1 loop, 0 intermediate buffers (CUSTOM)")

    # Unfused Python
    def py_unfused(a, b, c, n):
        tmp1 = [a[i]*b[i] for i in range(n)]
        tmp2 = [tmp1[i]+c[i] for i in range(n)]
        return [max(tmp2[i], 0) for i in range(n)]
    med, mn, mx = bench(lambda: py_unfused(a_l, b_l, c_l, N), warmup=1, repeats=3)
    record("EWFusion", "Python/pure", str(N), med, mn, mx, "3 loops, 3 allocations")

    # C: fused vs unfused
    for label, body in [
        ("C/fused", f"""
    for(int i=0;i<N;i++) {{
        double v = a[i]*b[i]+c[i];
        out[i] = v > 0.0 ? v : 0.0;
    }}"""),
        ("C/unfused", f"""
    double *t1=malloc(N*8), *t2=malloc(N*8);
    for(int i=0;i<N;i++) t1[i]=a[i]*b[i];
    for(int i=0;i<N;i++) t2[i]=t1[i]+c[i];
    for(int i=0;i<N;i++) out[i]=t2[i]>0?t2[i]:0;
    free(t1); free(t2);"""),
    ]:
        c_code = f"""
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#define N {N}
static double a[N],b[N],c[N],out[N];
int main() {{
    for(int i=0;i<N;i++) {{ a[i]=i*0.001; b[i]=i*0.002; c[i]=i*0.003; }}
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    for(int rep=0;rep<20;rep++) {{{body}
    }}
    clock_gettime(CLOCK_MONOTONIC,&t1);
    double ms=((t1.tv_sec-t0.tv_sec)*1e9+(t1.tv_nsec-t0.tv_nsec))/1e6/20.0;
    printf("%.4f\\n",ms);
    return 0;
}}
"""
        try:
            ms = compile_and_run_c(c_code)
            record("EWFusion", label, str(N), ms, ms, ms, "")
        except Exception as e:
            print(f"  {label}: skipped ({e})")


# ═══════════════════════════════════════════════════════
# Task 6: Vector Dot Product (Kahan-compensated)
# ═══════════════════════════════════════════════════════

def bench_dot():
    print("\n═══ Task 6: Dot Product (Kahan-compensated) ═══")
    N = 10_000_000

    try:
        import numpy as np
        a = np.random.randn(N)
        b = np.random.randn(N)
        med, mn, mx = bench(lambda: np.dot(a, b))
        record("DotProduct", "Python/numpy", str(N), med, mn, mx, "BLAS sdot")
    except ImportError:
        pass

    a_l = [float(i)*1e-6 for i in range(N)]
    b_l = [float(i)*1e-6 for i in range(N)]

    # Vir: Kahan dot
    def vir_kahan_dot(a, b, n):
        s = 0.0; comp = 0.0
        for i in range(n):
            y = a[i]*b[i] - comp
            t = s + y
            comp = (t - s) - y
            s = t
        return s
    med, mn, mx = bench(lambda: vir_kahan_dot(a_l, b_l, N), warmup=1, repeats=3)
    record("DotProduct", "Vir/kahan", str(N), med, mn, mx, "Kahan compensated (CUSTOM)")

    # Python naive
    def py_dot(a, b, n):
        return sum(a[i]*b[i] for i in range(n))
    med, mn, mx = bench(lambda: py_dot(a_l, b_l, N), warmup=1, repeats=3)
    record("DotProduct", "Python/pure", str(N), med, mn, mx, "naive sum")

    c_code = f"""
#include <stdio.h>
#include <time.h>
#define N {N}
static double a[N], b[N];
int main() {{
    for(int i=0;i<N;i++) {{ a[i]=(double)i*1e-6; b[i]=(double)i*1e-6; }}
    struct timespec t0,t1;
    clock_gettime(CLOCK_MONOTONIC,&t0);
    double result=0;
    for(int rep=0;rep<10;rep++) {{
        double s=0,comp=0;
        for(int i=0;i<N;i++) {{
            double y=a[i]*b[i]-comp;
            double t=s+y;
            comp=(t-s)-y;
            s=t;
        }}
        result=s;
    }}
    clock_gettime(CLOCK_MONOTONIC,&t1);
    double ms=((t1.tv_sec-t0.tv_sec)*1e9+(t1.tv_nsec-t0.tv_nsec))/1e6/10.0;
    printf("%.4f\\n",ms);
    return 0;
}}
"""
    try:
        ms = compile_and_run_c(c_code)
        record("DotProduct", "C/-O3", str(N), ms, ms, ms, "Kahan dot, -O3")
    except Exception as e:
        print(f"  C: skipped ({e})")

    # Rust
    rust_code = f"""
use std::time::Instant;
const N: usize = {N};
fn main() {{
    let a: Vec<f64> = (0..N).map(|i| i as f64 * 1e-6).collect();
    let b: Vec<f64> = (0..N).map(|i| i as f64 * 1e-6).collect();
    let mut total = 0u128;
    for _ in 0..10 {{
        let t0 = Instant::now();
        let mut s: f64 = 0.0;
        let mut comp: f64 = 0.0;
        for i in 0..N {{
            let y = a[i]*b[i] - comp;
            let t = s + y;
            comp = (t - s) - y;
            s = t;
        }}
        total += t0.elapsed().as_nanos();
        std::hint::black_box(s);
    }}
    println!("{{:.4}}", total as f64 / 10.0 / 1e6);
}}
"""
    try:
        ms = compile_and_run_rust(rust_code)
        if ms > 0.0:
            record("DotProduct", "Rust/-O", str(N), ms, ms, ms, "Kahan dot")
    except Exception as e:
        print(f"  Rust: skipped ({e})")


# ═══════════════════════════════════════════════════════
# Run all benchmarks
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("Vir AI Stack — Cross-Language Performance Benchmark")
    print("=" * 70)

    bench_gemm()
    bench_softmax()
    bench_welford()
    bench_flash_attention()
    bench_fusion()
    bench_dot()

    # Save raw results
    out_dir = Path(__file__).parent.parent / "docs"
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / "benchmark_results.json"
    with open(json_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nRaw results saved to {json_path}")
    print(f"Total benchmarks run: {len(RESULTS)}")
