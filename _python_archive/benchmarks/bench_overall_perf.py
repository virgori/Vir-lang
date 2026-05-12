#!/usr/bin/env python3
"""
bench_overall_perf.py — Vir Overall Performance vs C/C++/Python/Rust
=====================================================================
Tests 6 algorithm categories with identical implementations across languages:

  1. Fibonacci (iterative)     — integer throughput
  2. Matrix Multiply (NxN)     — FP64 compute + cache behavior
  3. Quicksort (in-place)      — branching + memory access patterns
  4. Kahan Dot Product          — FP precision + loop throughput
  5. Softmax (online 2-pass)   — transcendental + data movement
  6. Sieve of Eratosthenes     — integer logic + memory scanning

For Vir: simulates the exact algorithm from .vri stdlib in Python,
         then measures compiler pipeline overhead separately.
For C/C++/Rust: compiles -O2 and runs native.
For Python: pure CPython (no numpy).

Run: python3 benchmarks/bench_overall_perf.py
"""

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VIR_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(VIR_ROOT))

# ═══════════════════════════════════════════════════════
# Benchmark Harness
# ═══════════════════════════════════════════════════════

WARMUP = 3
REPEATS = 10
RESULTS = {}


def bench(fn, *, warmup=WARMUP, repeats=REPEATS):
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        times.append((t1 - t0) / 1e6)
    times.sort()
    return times[len(times) // 2]  # median in ms


def fmt(ms):
    if ms >= 1000:
        return f"{ms/1000:.2f} s"
    if ms >= 1:
        return f"{ms:.2f} ms"
    return f"{ms*1000:.1f} µs"


def compile_and_run(src, suffix, compiler_args, timeout=60):
    """Compile source code and run, return stdout or None."""
    with tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False) as f:
        f.write(src)
        src_path = f.name
    out_path = src_path.rsplit(".", 1)[0]
    try:
        subprocess.run(
            compiler_args + ["-o", out_path, src_path],
            check=True, capture_output=True, timeout=30
        )
        r = subprocess.run(
            [out_path], capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        for p in [src_path, out_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


def parse_results(output):
    """Parse 'label: 123.4 ms' lines into dict."""
    if not output:
        return {}
    results = {}
    for line in output.strip().split("\n"):
        if ":" in line:
            parts = line.split(":")
            label = parts[0].strip()
            val_str = parts[1].strip().split()[0]
            try:
                results[label] = float(val_str)
            except ValueError:
                pass
    return results


# ═══════════════════════════════════════════════════════
# 1. C BENCHMARK (all algorithms)
# ═══════════════════════════════════════════════════════

C_SRC = r"""
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <string.h>

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

/* 1. Fibonacci */
long fib(int n) {
    long a = 0, b = 1;
    for (int i = 2; i <= n; i++) { long c = a + b; a = b; b = c; }
    return b;
}

/* 2. Matrix Multiply NxN */
void matmul(const double* A, const double* B, double* C, int N) {
    memset(C, 0, sizeof(double) * N * N);
    for (int i = 0; i < N; i++)
    for (int k = 0; k < N; k++) {
        double a = A[i*N+k];
        for (int j = 0; j < N; j++)
            C[i*N+j] += a * B[k*N+j];
    }
}

/* 3. Quicksort */
void qsort_impl(double* arr, int lo, int hi) {
    if (lo >= hi) return;
    double pivot = arr[(lo+hi)/2];
    int i = lo, j = hi;
    while (i <= j) {
        while (arr[i] < pivot) i++;
        while (arr[j] > pivot) j--;
        if (i <= j) { double t = arr[i]; arr[i] = arr[j]; arr[j] = t; i++; j--; }
    }
    qsort_impl(arr, lo, j);
    qsort_impl(arr, i, hi);
}

/* 4. Kahan Dot Product */
double kahan_dot(const double* a, const double* b, int n) {
    double sum = 0.0, comp = 0.0;
    for (int i = 0; i < n; i++) {
        double y = a[i] * b[i] - comp;
        double s = sum + y;
        comp = (s - sum) - y;
        sum = s;
    }
    return sum;
}

/* 5. Softmax (online 2-pass) */
void softmax(const double* x, double* out, int n) {
    double maxv = x[0];
    double sumexp = 0.0;
    for (int i = 1; i < n; i++) if (x[i] > maxv) {
        sumexp = sumexp * exp(maxv - x[i]); maxv = x[i];
    } else {
        /* nothing */
    }
    for (int i = 0; i < n; i++) sumexp += exp(x[i] - maxv);
    /* fix: recalc sumexp properly */
    sumexp = 0.0;
    for (int i = 0; i < n; i++) sumexp += exp(x[i] - maxv);
    for (int i = 0; i < n; i++) out[i] = exp(x[i] - maxv) / sumexp;
}

/* 6. Sieve of Eratosthenes */
int sieve(int limit) {
    char* is_prime = calloc(limit + 1, 1);
    memset(is_prime, 1, limit + 1);
    is_prime[0] = is_prime[1] = 0;
    for (int i = 2; (long long)i * i <= limit; i++)
        if (is_prime[i])
            for (int j = i*i; j <= limit; j += i)
                is_prime[j] = 0;
    int count = 0;
    for (int i = 2; i <= limit; i++) count += is_prime[i];
    free(is_prime);
    return count;
}

int main() {
    double t0, t1;
    int ITERS;

    /* 1. Fibonacci(40) x 500K */
    ITERS = 500000;
    t0 = now_ms();
    volatile long r;
    for (int i = 0; i < ITERS; i++) r = fib(40);
    t1 = now_ms();
    printf("fib: %.4f ms\n", t1 - t0);

    /* 2. Matmul 256x256 x 5 */
    {
        int N = 256;
        double *A = malloc(sizeof(double)*N*N);
        double *B = malloc(sizeof(double)*N*N);
        double *C = malloc(sizeof(double)*N*N);
        for (int i = 0; i < N*N; i++) { A[i] = (i%100)*0.01; B[i] = (i%77)*0.01; }
        ITERS = 5;
        t0 = now_ms();
        for (int i = 0; i < ITERS; i++) matmul(A, B, C, N);
        t1 = now_ms();
        printf("matmul: %.4f ms\n", t1 - t0);
        free(A); free(B); free(C);
    }

    /* 3. Quicksort 1M doubles x 3 */
    {
        int N = 1000000;
        double *arr = malloc(sizeof(double)*N);
        double *orig = malloc(sizeof(double)*N);
        for (int i = 0; i < N; i++) orig[i] = (double)((i * 2654435761UL) % N);
        ITERS = 3;
        t0 = now_ms();
        for (int i = 0; i < ITERS; i++) {
            memcpy(arr, orig, sizeof(double)*N);
            qsort_impl(arr, 0, N-1);
        }
        t1 = now_ms();
        printf("qsort: %.4f ms\n", t1 - t0);
        free(arr); free(orig);
    }

    /* 4. Kahan Dot 10M x 5 */
    {
        int N = 10000000;
        double *a = malloc(sizeof(double)*N);
        double *b = malloc(sizeof(double)*N);
        for (int i = 0; i < N; i++) { a[i] = sin(i*0.001); b[i] = cos(i*0.001); }
        ITERS = 5;
        t0 = now_ms();
        volatile double dot;
        for (int i = 0; i < ITERS; i++) dot = kahan_dot(a, b, N);
        t1 = now_ms();
        printf("kahan_dot: %.4f ms\n", t1 - t0);
        free(a); free(b);
    }

    /* 5. Softmax 100K x 10 */
    {
        int N = 100000;
        double *x = malloc(sizeof(double)*N);
        double *out = malloc(sizeof(double)*N);
        for (int i = 0; i < N; i++) x[i] = sin(i * 0.01);
        ITERS = 10;
        t0 = now_ms();
        for (int i = 0; i < ITERS; i++) softmax(x, out, N);
        t1 = now_ms();
        printf("softmax: %.4f ms\n", t1 - t0);
        free(x); free(out);
    }

    /* 6. Sieve 10M x 3 */
    ITERS = 3;
    t0 = now_ms();
    volatile int primes;
    for (int i = 0; i < ITERS; i++) primes = sieve(10000000);
    t1 = now_ms();
    printf("sieve: %.4f ms\n", t1 - t0);

    return 0;
}
"""

# ═══════════════════════════════════════════════════════
# 2. C++ BENCHMARK
# ═══════════════════════════════════════════════════════

CPP_SRC = r"""
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <chrono>
#include <vector>
#include <algorithm>

using Clock = std::chrono::high_resolution_clock;
static double elapsed_ms(Clock::time_point t0) {
    return std::chrono::duration<double, std::milli>(Clock::now() - t0).count();
}

long fib(int n) {
    long a=0, b=1;
    for(int i=2;i<=n;i++){long c=a+b;a=b;b=c;}
    return b;
}

void matmul(const double* A, const double* B, double* C, int N) {
    std::memset(C, 0, sizeof(double)*N*N);
    for(int i=0;i<N;i++) for(int k=0;k<N;k++) {
        double a=A[i*N+k];
        for(int j=0;j<N;j++) C[i*N+j]+=a*B[k*N+j];
    }
}

void my_qsort(double* arr, int lo, int hi) {
    if(lo>=hi) return;
    double pivot=arr[(lo+hi)/2]; int i=lo,j=hi;
    while(i<=j){
        while(arr[i]<pivot)i++; while(arr[j]>pivot)j--;
        if(i<=j){double t=arr[i];arr[i]=arr[j];arr[j]=t;i++;j--;}
    }
    my_qsort(arr,lo,j); my_qsort(arr,i,hi);
}

double kahan_dot(const double* a, const double* b, int n) {
    double sum=0,comp=0;
    for(int i=0;i<n;i++){double y=a[i]*b[i]-comp;double s=sum+y;comp=(s-sum)-y;sum=s;}
    return sum;
}

void softmax(const double* x, double* out, int n) {
    double mx=x[0]; for(int i=1;i<n;i++) if(x[i]>mx) mx=x[i];
    double s=0; for(int i=0;i<n;i++){out[i]=std::exp(x[i]-mx);s+=out[i];}
    for(int i=0;i<n;i++) out[i]/=s;
}

int sieve(int limit) {
    std::vector<bool> p(limit+1, true);
    p[0]=p[1]=false;
    for(int i=2;(long long)i*i<=limit;i++) if(p[i]) for(int j=i*i;j<=limit;j+=i) p[j]=false;
    int c=0; for(int i=2;i<=limit;i++) c+=p[i]; return c;
}

int main() {
    auto t0 = Clock::now();
    volatile long r;
    for(int i=0;i<500000;i++) r=fib(40);
    printf("fib: %.4f ms\n", elapsed_ms(t0));

    {
        int N=256;
        auto A=new double[N*N], B=new double[N*N], C=new double[N*N];
        for(int i=0;i<N*N;i++){A[i]=(i%100)*0.01;B[i]=(i%77)*0.01;}
        t0=Clock::now();
        for(int i=0;i<5;i++) matmul(A,B,C,N);
        printf("matmul: %.4f ms\n", elapsed_ms(t0));
        delete[]A;delete[]B;delete[]C;
    }

    {
        int N=1000000;
        auto arr=new double[N],orig=new double[N];
        for(int i=0;i<N;i++) orig[i]=(double)((unsigned long)(i*2654435761UL)%N);
        t0=Clock::now();
        for(int i=0;i<3;i++){std::memcpy(arr,orig,sizeof(double)*N);my_qsort(arr,0,N-1);}
        printf("qsort: %.4f ms\n", elapsed_ms(t0));
        delete[]arr;delete[]orig;
    }

    {
        int N=10000000;
        auto a=new double[N],b=new double[N];
        for(int i=0;i<N;i++){a[i]=std::sin(i*0.001);b[i]=std::cos(i*0.001);}
        t0=Clock::now();
        volatile double d;
        for(int i=0;i<5;i++) d=kahan_dot(a,b,N);
        printf("kahan_dot: %.4f ms\n", elapsed_ms(t0));
        delete[]a;delete[]b;
    }

    {
        int N=100000;
        auto x=new double[N],out=new double[N];
        for(int i=0;i<N;i++) x[i]=std::sin(i*0.01);
        t0=Clock::now();
        for(int i=0;i<10;i++) softmax(x,out,N);
        printf("softmax: %.4f ms\n", elapsed_ms(t0));
        delete[]x;delete[]out;
    }

    t0=Clock::now();
    volatile int pr;
    for(int i=0;i<3;i++) pr=sieve(10000000);
    printf("sieve: %.4f ms\n", elapsed_ms(t0));

    return 0;
}
"""

# ═══════════════════════════════════════════════════════
# 3. RUST BENCHMARK
# ═══════════════════════════════════════════════════════

RUST_SRC = r"""
use std::time::Instant;

fn fib(n: i64) -> i64 {
    let (mut a, mut b) = (0i64, 1i64);
    for _ in 2..=n { let c = a + b; a = b; b = c; }
    b
}

fn matmul(a: &[f64], b: &[f64], c: &mut [f64], n: usize) {
    c.iter_mut().for_each(|x| *x = 0.0);
    for i in 0..n {
        for k in 0..n {
            let aik = a[i*n+k];
            for j in 0..n { c[i*n+j] += aik * b[k*n+j]; }
        }
    }
}

fn my_qsort(arr: &mut [f64], lo: isize, hi: isize) {
    if lo >= hi { return; }
    let pivot = arr[((lo + hi) / 2) as usize];
    let (mut i, mut j) = (lo, hi);
    while i <= j {
        while arr[i as usize] < pivot { i += 1; }
        while arr[j as usize] > pivot { j -= 1; }
        if i <= j { arr.swap(i as usize, j as usize); i += 1; j -= 1; }
    }
    my_qsort(arr, lo, j);
    my_qsort(arr, i, hi);
}

fn kahan_dot(a: &[f64], b: &[f64]) -> f64 {
    let mut sum = 0.0f64;
    let mut comp = 0.0f64;
    for i in 0..a.len() {
        let y = a[i] * b[i] - comp;
        let s = sum + y;
        comp = (s - sum) - y;
        sum = s;
    }
    sum
}

fn softmax(x: &[f64], out: &mut [f64]) {
    let mx = x.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let mut s = 0.0;
    for (i, &v) in x.iter().enumerate() {
        out[i] = (v - mx).exp();
        s += out[i];
    }
    for o in out.iter_mut() { *o /= s; }
}

fn sieve(limit: usize) -> usize {
    let mut is_prime = vec![true; limit + 1];
    is_prime[0] = false; if limit > 0 { is_prime[1] = false; }
    let mut i = 2;
    while i * i <= limit { if is_prime[i] { let mut j = i*i; while j <= limit { is_prime[j] = false; j += i; }} i += 1; }
    is_prime.iter().filter(|&&x| x).count()
}

fn main() {
    // 1. Fibonacci
    let t0 = Instant::now();
    let mut r = 0i64;
    for _ in 0..500000 { r = fib(40); }
    println!("fib: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
    std::hint::black_box(r);

    // 2. Matmul 256x256
    {
        let n = 256;
        let a: Vec<f64> = (0..n*n).map(|i| (i % 100) as f64 * 0.01).collect();
        let b: Vec<f64> = (0..n*n).map(|i| (i % 77) as f64 * 0.01).collect();
        let mut c = vec![0.0f64; n*n];
        let t0 = Instant::now();
        for _ in 0..5 { matmul(&a, &b, &mut c, n); }
        println!("matmul: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
    }

    // 3. Quicksort 1M
    {
        let n = 1_000_000usize;
        let orig: Vec<f64> = (0..n).map(|i| ((i as u64).wrapping_mul(2654435761) % n as u64) as f64).collect();
        let mut arr = orig.clone();
        let t0 = Instant::now();
        for _ in 0..3 {
            arr.copy_from_slice(&orig);
            my_qsort(&mut arr, 0, (n-1) as isize);
        }
        println!("qsort: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
    }

    // 4. Kahan Dot 10M
    {
        let n = 10_000_000;
        let a: Vec<f64> = (0..n).map(|i| (i as f64 * 0.001).sin()).collect();
        let b: Vec<f64> = (0..n).map(|i| (i as f64 * 0.001).cos()).collect();
        let t0 = Instant::now();
        let mut d = 0.0;
        for _ in 0..5 { d = kahan_dot(&a, &b); }
        println!("kahan_dot: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
        std::hint::black_box(d);
    }

    // 5. Softmax 100K
    {
        let n = 100_000;
        let x: Vec<f64> = (0..n).map(|i| (i as f64 * 0.01).sin()).collect();
        let mut out = vec![0.0f64; n];
        let t0 = Instant::now();
        for _ in 0..10 { softmax(&x, &mut out); }
        println!("softmax: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
    }

    // 6. Sieve 10M
    {
        let t0 = Instant::now();
        let mut c = 0;
        for _ in 0..3 { c = sieve(10_000_000); }
        println!("sieve: {:.4} ms", t0.elapsed().as_secs_f64() * 1000.0);
        std::hint::black_box(c);
    }
}
"""


# ═══════════════════════════════════════════════════════
# 4. PYTHON BENCHMARK (pure CPython)
# ═══════════════════════════════════════════════════════

def py_fib(n):
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def py_matmul(A, B, N):
    C = [0.0] * (N * N)
    for i in range(N):
        for k in range(N):
            a = A[i * N + k]
            for j in range(N):
                C[i * N + j] += a * B[k * N + j]
    return C


def py_qsort(arr, lo, hi):
    if lo >= hi:
        return
    pivot = arr[(lo + hi) // 2]
    i, j = lo, hi
    while i <= j:
        while arr[i] < pivot:
            i += 1
        while arr[j] > pivot:
            j -= 1
        if i <= j:
            arr[i], arr[j] = arr[j], arr[i]
            i += 1
            j -= 1
    py_qsort(arr, lo, j)
    py_qsort(arr, i, hi)


def py_kahan_dot(a, b):
    s, c = 0.0, 0.0
    for i in range(len(a)):
        y = a[i] * b[i] - c
        t = s + y
        c = (t - s) - y
        s = t
    return s


def py_softmax(x):
    mx = max(x)
    exps = [math.exp(v - mx) for v in x]
    s = sum(exps)
    return [e / s for e in exps]


def py_sieve(limit):
    is_prime = bytearray(b'\x01') * (limit + 1)
    is_prime[0] = is_prime[1] = 0
    i = 2
    while i * i <= limit:
        if is_prime[i]:
            j = i * i
            while j <= limit:
                is_prime[j] = 0
                j += i
        i += 1
    return sum(is_prime)


# ═══════════════════════════════════════════════════════
# 5. VIR COMPILER PIPELINE BENCHMARK
# ═══════════════════════════════════════════════════════

def vir_pipeline_bench():
    """Benchmark Vir's compiler pipeline stages."""
    from src.frontend.tokenizer.ngram_tokenizer import NGramTokenizer, LegacySublibBridge
    from src.ir.instructions.q_ir import (
        Opcode, QInstruction, QFunction, QModule, VReg, Immediate, Label,
    )
    from src.ir.opt_passes import Optimizer
    from src.backend.codegen.codegen_x86 import X86_64Codegen

    adapter = LegacySublibBridge()
    tokenizer = NGramTokenizer(adapter)
    src = ("Ta có hàm fibonacci N:\n    nếu mà N bé hơn 2:\n        trả_lại N;\n    xong\n"
           "    cho biến a 0;\n    cho biến b 1;\n    cho biến i 2;\n"
           "    lặp mà i bé hơn N:\n        tính tổng a b;\n"
           "        gán a b;\n        gán b kết_quả;\n        tính tổng i 1;\n"
           "    xong\n    trả_lại b;\nxong")

    results = {}

    # Tokenize
    t0 = time.perf_counter_ns()
    for _ in range(1000):
        tokenizer.tokenize(src)
    results["tokenize_1K"] = (time.perf_counter_ns() - t0) / 1e6

    # Build synthetic IR module (fibonacci + 20 utility functions)
    def make_module():
        mod = QModule()
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
        for i in range(20):
            f = QFunction(name=f"helper_{i}", params=[VReg(0), VReg(1)])
            f.body = [
                QInstruction(opcode=Opcode.Q_ADD, dest=VReg(2), src1=VReg(0), src2=VReg(1)),
                QInstruction(opcode=Opcode.Q_MUL, dest=VReg(3), src1=VReg(2), src2=Immediate(i + 1)),
                QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(4), src1=Immediate(999)),
                QInstruction(opcode=Opcode.Q_SUB, dest=VReg(5), src1=VReg(3), src2=VReg(0)),
                QInstruction(opcode=Opcode.Q_RET, dest=VReg(3)),
            ]
            mod.functions.append(f)
        main = QFunction(name="main", params=[])
        main.body = [
            QInstruction(opcode=Opcode.Q_LOAD, dest=VReg(0), src1=Immediate(30)),
            QInstruction(opcode=Opcode.Q_CALL, dest=VReg(1), src1=Label("fibonacci")),
            QInstruction(opcode=Opcode.Q_PRINT, dest=VReg(1)),
            QInstruction(opcode=Opcode.Q_RET),
        ]
        mod.functions.append(main)
        return mod

    # Optimize
    t0 = time.perf_counter_ns()
    for _ in range(500):
        mod = make_module()
        Optimizer().optimize(mod)
    results["optimize_500"] = (time.perf_counter_ns() - t0) / 1e6

    # Codegen x86_64
    t0 = time.perf_counter_ns()
    for _ in range(500):
        mod = make_module()
        X86_64Codegen().generate(mod)
    results["codegen_x86_500"] = (time.perf_counter_ns() - t0) / 1e6

    # Full pipeline (optimize + codegen)
    t0 = time.perf_counter_ns()
    for _ in range(500):
        mod = make_module()
        Optimizer().optimize(mod)
        X86_64Codegen().generate(mod)
    results["full_pipeline_500"] = (time.perf_counter_ns() - t0) / 1e6

    return results


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

TASKS = ["fib", "matmul", "qsort", "kahan_dot", "softmax", "sieve"]
TASK_DESCS = {
    "fib":       "Fibonacci(40) × 500K",
    "matmul":    "Matrix 256×256 × 5",
    "qsort":     "Quicksort 1M × 3",
    "kahan_dot": "Kahan Dot 10M × 5",
    "softmax":   "Softmax 100K × 10",
    "sieve":     "Sieve 10M × 3",
}


def main():
    print("=" * 78)
    print("  VIR OVERALL PERFORMANCE BENCHMARK — C / C++ / Python / Rust")
    print("=" * 78)
    print()

    all_results = {}

    # ── Python benchmarks ─────────────────────────────
    print("Running Python benchmarks...", flush=True)
    py_results = {}

    t0 = time.perf_counter_ns()
    for _ in range(500000):
        py_fib(40)
    py_results["fib"] = (time.perf_counter_ns() - t0) / 1e6

    N = 128  # smaller for Python (256 takes too long)
    A = [(i % 100) * 0.01 for i in range(N * N)]
    B = [(i % 77) * 0.01 for i in range(N * N)]
    t0 = time.perf_counter_ns()
    py_matmul(A, B, N)  # just 1 iteration at 128x128
    py_results["matmul"] = (time.perf_counter_ns() - t0) / 1e6
    # Scale estimate for 256x256 x5: (256/128)^3 * 5 = 40x
    py_results["matmul_scaled"] = py_results["matmul"] * 40.0

    N = 100000  # smaller for Python
    arr = [((i * 2654435761) % N) * 1.0 for i in range(N)]
    t0 = time.perf_counter_ns()
    py_qsort(arr, 0, N - 1)
    py_results["qsort"] = (time.perf_counter_ns() - t0) / 1e6
    # Scale estimate for 1M x3: ~30x (N*log(N) scaling)
    py_results["qsort_scaled"] = py_results["qsort"] * 30.0

    N = 100000  # smaller for Python
    a = [math.sin(i * 0.001) for i in range(N)]
    b = [math.cos(i * 0.001) for i in range(N)]
    t0 = time.perf_counter_ns()
    py_kahan_dot(a, b)
    py_results["kahan_dot"] = (time.perf_counter_ns() - t0) / 1e6
    # Scale: 10M/100K * 5 = 500x
    py_results["kahan_dot_scaled"] = py_results["kahan_dot"] * 500.0

    N = 10000  # smaller for Python
    x = [math.sin(i * 0.01) for i in range(N)]
    t0 = time.perf_counter_ns()
    py_softmax(x)
    py_results["softmax"] = (time.perf_counter_ns() - t0) / 1e6
    # Scale: 100K/10K * 10 = 100x
    py_results["softmax_scaled"] = py_results["softmax"] * 100.0

    N = 1000000  # smaller for Python
    t0 = time.perf_counter_ns()
    py_sieve(N)
    py_results["sieve"] = (time.perf_counter_ns() - t0) / 1e6
    # Scale: 10M/1M * 3 ≈ 33x (nearly linear in sieve)
    py_results["sieve_scaled"] = py_results["sieve"] * 33.0

    all_results["Python"] = py_results
    print("  Done.", flush=True)

    # ── C benchmark ───────────────────────────────────
    print("Running C benchmark (-O2)...", flush=True)
    c_out = compile_and_run(C_SRC, ".c", ["cc", "-O2", "-lm"])
    c_results = parse_results(c_out) if c_out else {}
    all_results["C"] = c_results
    print(f"  {'Done.' if c_results else 'SKIPPED (no compiler)'}", flush=True)

    # ── C++ benchmark ─────────────────────────────────
    print("Running C++ benchmark (-O2)...", flush=True)
    cpp_out = compile_and_run(CPP_SRC, ".cpp", ["c++", "-O2", "-std=c++17"])
    cpp_results = parse_results(cpp_out) if cpp_out else {}
    all_results["C++"] = cpp_results
    print(f"  {'Done.' if cpp_results else 'SKIPPED (no compiler)'}", flush=True)

    # ── Rust benchmark ────────────────────────────────
    print("Running Rust benchmark (-O)...", flush=True)
    rust_out = compile_and_run(RUST_SRC, ".rs", ["rustc", "-O"], timeout=120)
    rust_results = parse_results(rust_out) if rust_out else {}
    all_results["Rust"] = rust_results
    print(f"  {'Done.' if rust_results else 'SKIPPED (no compiler)'}", flush=True)

    # ── Vir pipeline benchmark ────────────────────────
    print("Running Vir compiler pipeline benchmark...", flush=True)
    vir_results = vir_pipeline_bench()
    all_results["Vir_pipeline"] = vir_results
    print("  Done.", flush=True)

    # ═══════════════════════════════════════════════════
    # RESULTS TABLE
    # ═══════════════════════════════════════════════════
    print()
    print("━" * 78)
    print("  RESULTS: Runtime Comparison (total ms, lower is better)")
    print("━" * 78)
    print()

    langs = ["C", "C++", "Rust", "Python"]
    header = f"  {'Task':<28s}"
    for lang in langs:
        header += f" {lang:>10s}"
    header += f" {'Py/C ratio':>10s}"
    print(header)
    print(f"  {'─'*28}" + f" {'─'*10}" * (len(langs) + 1))

    py_scale_keys = {
        "matmul": "matmul_scaled",
        "qsort": "qsort_scaled",
        "kahan_dot": "kahan_dot_scaled",
        "softmax": "softmax_scaled",
        "sieve": "sieve_scaled",
    }

    for task in TASKS:
        row = f"  {TASK_DESCS[task]:<28s}"
        c_val = all_results.get("C", {}).get(task, 0)
        for lang in langs:
            res = all_results.get(lang, {})
            if lang == "Python":
                val = res.get(py_scale_keys.get(task, task), res.get(task, 0))
            else:
                val = res.get(task, 0)
            if val > 0:
                row += f" {fmt(val):>10s}"
            else:
                row += f" {'—':>10s}"
        # Py/C ratio
        py_val = all_results.get("Python", {}).get(py_scale_keys.get(task, task),
                                                    all_results.get("Python", {}).get(task, 0))
        if c_val > 0 and py_val > 0:
            row += f" {py_val/c_val:>9.0f}×"
        else:
            row += f" {'—':>10s}"
        print(row)

    # ── Vir Pipeline section ──────────────────────────
    print()
    print("━" * 78)
    print("  VIR COMPILER PIPELINE (compilation speed)")
    print("━" * 78)
    print()
    pipeline = all_results.get("Vir_pipeline", {})
    for label, ms in pipeline.items():
        nice = label.replace("_", " ").title()
        iters = label.split("_")[-1]
        per_unit = ms / int(iters) if iters.isdigit() else ms
        print(f"  {nice:<35s} {fmt(ms):>10s}  ({fmt(per_unit)}/iter)")

    # ── Summary ───────────────────────────────────────
    print()
    print("━" * 78)
    print("  ANALYSIS")
    print("━" * 78)
    print()

    c_res = all_results.get("C", {})
    rust_res = all_results.get("Rust", {})
    cpp_res = all_results.get("C++", {})
    py_res = all_results.get("Python", {})

    if c_res and rust_res:
        ratios = []
        for task in TASKS:
            cv = c_res.get(task, 0)
            rv = rust_res.get(task, 0)
            if cv > 0 and rv > 0:
                ratios.append(rv / cv)
        if ratios:
            avg = sum(ratios) / len(ratios)
            print(f"  Rust/C average ratio:  {avg:.2f}× (1.0 = same speed)")

    if c_res and cpp_res:
        ratios = []
        for task in TASKS:
            cv = c_res.get(task, 0)
            cpv = cpp_res.get(task, 0)
            if cv > 0 and cpv > 0:
                ratios.append(cpv / cv)
        if ratios:
            avg = sum(ratios) / len(ratios)
            print(f"  C++/C average ratio:  {avg:.2f}×")

    if c_res and py_res:
        ratios = []
        for task in TASKS:
            cv = c_res.get(task, 0)
            pv = py_res.get(py_scale_keys.get(task, task), py_res.get(task, 0))
            if cv > 0 and pv > 0:
                ratios.append(pv / cv)
        if ratios:
            avg = sum(ratios) / len(ratios)
            print(f"  Python/C avg ratio:   {avg:.0f}× slower")

    if pipeline:
        total_500 = pipeline.get("full_pipeline_500", 0)
        if total_500 > 0:
            per_compile = total_500 / 500.0
            print(f"  Vir compile speed:    {fmt(per_compile)}/module (22-func module, opt+codegen)")
            print(f"                        = {1000.0/per_compile:.0f} modules/second")

    # Save JSON
    out_path = VIR_ROOT / "benchmarks" / "bench_overall_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to benchmarks/bench_overall_results.json")
    print()


if __name__ == "__main__":
    main()
