/*
 * bench_comprehensive_cpp.cpp — Vir Cross-Language Benchmark (C++)
 * ================================================================
 * Covers: Throughput, Memory, System I/O, Scalability
 * Compile: clang++ -std=c++17 -O3 -march=native -o bench_cpp bench_comprehensive_cpp.cpp
 */

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <chrono>
#include <thread>
#include <atomic>
#include <vector>
#include <algorithm>
#include <numeric>
#include <mutex>

using Clock = std::chrono::high_resolution_clock;
using us = std::chrono::microseconds;
using ns = std::chrono::nanoseconds;

static volatile double g_sink = 0.0;

// ═══════════════════════════════════════════════════════
// 1. COMPUTATIONAL THROUGHPUT
// ═══════════════════════════════════════════════════════

// 1a. GEMM (tiled, NEON-friendly ikj)
void gemm_tiled(const double* A, const double* B, double* C, int N) {
    constexpr int TILE = 64;
    std::memset(C, 0, N * N * sizeof(double));
    for (int i0 = 0; i0 < N; i0 += TILE)
    for (int k0 = 0; k0 < N; k0 += TILE)
    for (int j0 = 0; j0 < N; j0 += TILE) {
        int ie = std::min(i0 + TILE, N);
        int ke = std::min(k0 + TILE, N);
        int je = std::min(j0 + TILE, N);
        for (int i = i0; i < ie; i++)
        for (int k = k0; k < ke; k++) {
            double a = A[i * N + k];
            for (int j = j0; j < je; j++)
                C[i * N + j] += a * B[k * N + j]; // FMA pattern
        }
    }
}

// 1b. Winograd F(2,3) — single tile
void winograd_f2x3_tile(const double tile[16], const double filt[16], double out[4]) {
    // B^T · tile · B (input transform, no multiply)
    double d[16];
    double r00=tile[0]-tile[8], r01=tile[1]-tile[9], r02=tile[2]-tile[10], r03=tile[3]-tile[11];
    double r10=tile[4]+tile[8], r11=tile[5]+tile[9], r12=tile[6]+tile[10], r13=tile[7]+tile[11];
    double r20=tile[8]-tile[4], r21=tile[9]-tile[5], r22=tile[10]-tile[6], r23=tile[11]-tile[7];
    double r30=tile[4]-tile[12],r31=tile[5]-tile[13],r32=tile[6]-tile[14],r33=tile[7]-tile[15];

    d[0]=r00-r02; d[1]=r01+r02; d[2]=r02-r01; d[3]=r01-r03;
    d[4]=r10-r12; d[5]=r11+r12; d[6]=r12-r11; d[7]=r11-r13;
    d[8]=r20-r22; d[9]=r21+r22; d[10]=r22-r21;d[11]=r21-r23;
    d[12]=r30-r32;d[13]=r31+r32;d[14]=r32-r31;d[15]=r31-r33;

    // Hadamard: d ⊙ filt (16 muls)
    double v[16];
    for(int i=0;i<16;i++) v[i]=d[i]*filt[i];

    // A^T · v · A (output transform)
    double s00=v[0]+v[4]+v[8], s01=v[1]+v[5]+v[9], s02=v[2]+v[6]+v[10], s03=v[3]+v[7]+v[11];
    double s10=v[4]-v[8]-v[12],s11=v[5]-v[9]-v[13],s12=v[6]-v[10]-v[14],s13=v[7]-v[11]-v[15];

    out[0]=s00+s01+s02;
    out[1]=s01-s02-s03;
    out[2]=s10+s11+s12;
    out[3]=s11-s12-s13;
}

// 1c. Kahan dot product
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

// 1d. Online Softmax (2-pass)
void softmax_online(const double* x, double* out, int n) {
    double run_max = -1e308, run_sum = 0.0;
    for (int i = 0; i < n; i++) {
        if (x[i] > run_max) {
            run_sum = run_sum * std::exp(run_max - x[i]);
            run_max = x[i];
        }
        run_sum += std::exp(x[i] - run_max);
    }
    for (int i = 0; i < n; i++)
        out[i] = std::exp(x[i] - run_max) / run_sum;
}

// 1e. Fused elementwise: y = relu(a * x + b)
void fused_ew(const double* x, double* y, int n, double a_val, double b_val) {
    for (int i = 0; i < n; i++) {
        double v = a_val * x[i] + b_val;
        y[i] = v > 0.0 ? v : 0.0;
    }
}

void unfused_ew(const double* x, double* y, int n, double a_val, double b_val) {
    auto* t1 = (double*)std::malloc(n * sizeof(double));
    auto* t2 = (double*)std::malloc(n * sizeof(double));
    for (int i = 0; i < n; i++) t1[i] = a_val * x[i];
    for (int i = 0; i < n; i++) t2[i] = t1[i] + b_val;
    for (int i = 0; i < n; i++) y[i] = t2[i] > 0.0 ? t2[i] : 0.0;
    std::free(t1); std::free(t2);
}

// 1f. Welford with Kahan compensation
struct WelfordState { double mean; double m2; double comp; int64_t count; };

WelfordState welford_kahan(const double* x, int n) {
    double mean=0, m2=0, comp=0;
    for (int i = 0; i < n; i++) {
        double delta = x[i] - mean;
        mean += delta / (i + 1);
        double delta2 = x[i] - mean;
        double y = delta * delta2 - comp;
        double s = m2 + y;
        comp = (s - m2) - y;
        m2 = s;
    }
    return {mean, m2, comp, (int64_t)n};
}

// ═══════════════════════════════════════════════════════
// 2. MEMORY DISCIPLINE
// ═══════════════════════════════════════════════════════

// 2a. Allocation latency (malloc/free cycle)
double bench_alloc_latency(int n_allocs, int size) {
    auto start = Clock::now();
    for (int i = 0; i < n_allocs; i++) {
        void* p = std::malloc(size);
        *(volatile char*)p = 0;  // Touch to prevent optimization
        std::free(p);
    }
    auto end = Clock::now();
    return std::chrono::duration_cast<ns>(end - start).count() / (double)n_allocs;
}

// 2b. Peak memory during matmul: standard attention O(N²)
size_t peak_mem_standard_attention(int N, int d) {
    // Q,K,V: N*d each, scores: N*N, output: N*d
    return (size_t)(3 * N * d + N * (size_t)N + N * d) * sizeof(double);
}

size_t peak_mem_flash_attention(int N, int d, int tile) {
    // Q,K,V: N*d each, tile buffers: tile*d*2 + tile*tile
    return (size_t)(3 * N * d + 2 * tile * d + tile * (size_t)tile) * sizeof(double);
}

// ═══════════════════════════════════════════════════════
// 3. SYSTEM I/O
// ═══════════════════════════════════════════════════════

// Binary size is measured externally (file stat)

// 3a. Cold-start simulation (fork+exec timing done externally)

// 3b. memcpy throughput (proxy for I/O)
double bench_memcpy(size_t bytes) {
    auto* src = (char*)std::malloc(bytes);
    auto* dst = (char*)std::malloc(bytes);
    std::memset(src, 42, bytes);
    auto start = Clock::now();
    std::memcpy(dst, src, bytes);
    auto end = Clock::now();
    g_sink = dst[bytes / 2]; // prevent DCE
    double elapsed = std::chrono::duration_cast<ns>(end - start).count() / 1000.0;
    std::free(src); std::free(dst);
    return elapsed;
}

// ═══════════════════════════════════════════════════════
// 5. SCALABILITY
// ═══════════════════════════════════════════════════════

static std::atomic<double> shared_sum{0.0};

void parallel_reduce(const double* data, int n, int n_threads) {
    shared_sum.store(0.0);
    std::vector<std::thread> threads;
    int chunk = n / n_threads;
    for (int t = 0; t < n_threads; t++) {
        int start = t * chunk;
        int end = (t == n_threads - 1) ? n : start + chunk;
        threads.emplace_back([&, start, end]() {
            double local = 0.0;
            for (int i = start; i < end; i++) local += data[i];
            // Atomic add
            double expected = shared_sum.load();
            while (!shared_sum.compare_exchange_weak(expected, expected + local));
        });
    }
    for (auto& t : threads) t.join();
}

// With mutex (simulating lock-based)
static std::mutex mtx;
static double locked_sum = 0.0;

void parallel_reduce_locked(const double* data, int n, int n_threads) {
    locked_sum = 0.0;
    std::vector<std::thread> threads;
    int chunk = n / n_threads;
    for (int t = 0; t < n_threads; t++) {
        int start = t * chunk;
        int end = (t == n_threads - 1) ? n : start + chunk;
        threads.emplace_back([&, start, end]() {
            double local = 0.0;
            for (int i = start; i < end; i++) local += data[i];
            std::lock_guard<std::mutex> lock(mtx);
            locked_sum += local;
        });
    }
    for (auto& t : threads) t.join();
}

// ═══════════════════════════════════════════════════════
// NUMERICAL STABILITY TEST
// ═══════════════════════════════════════════════════════

double summation_naive(const double* x, int n) {
    double s = 0;
    for (int i = 0; i < n; i++) s += x[i];
    return s;
}

double summation_kahan(const double* x, int n) {
    double s = 0, c = 0;
    for (int i = 0; i < n; i++) {
        double y = x[i] - c;
        double t = s + y;
        c = (t - s) - y;
        s = t;
    }
    return s;
}

// ═══════════════════════════════════════════════════════
// MAIN BENCHMARK DRIVER
// ═══════════════════════════════════════════════════════

#define BENCH(label, iters, body) do { \
    body; /* warmup */ \
    auto _s = Clock::now(); \
    for (int _i = 0; _i < iters; _i++) { body; } \
    auto _e = Clock::now(); \
    double _us = std::chrono::duration_cast<ns>(_e - _s).count() / 1000.0 / iters; \
    std::printf("%-40s %12.1f µs\n", label, _us); \
} while(0)

int main() {
    std::printf("═══════════════════════════════════════════\n");
    std::printf("  C++ Comprehensive Benchmark (clang -O3)\n");
    std::printf("═══════════════════════════════════════════\n\n");

    // ── 1. COMPUTATIONAL THROUGHPUT ──────────────────
    std::printf("▓ 1. COMPUTATIONAL THROUGHPUT\n");
    std::printf("───────────────────────────────────────────\n");

    // GEMM 512
    {
        const int N = 512;
        auto* A = (double*)std::calloc(N * N, sizeof(double));
        auto* B = (double*)std::calloc(N * N, sizeof(double));
        auto* C = (double*)std::calloc(N * N, sizeof(double));
        for (int i = 0; i < N*N; i++) { A[i] = (i % 97) * 0.01; B[i] = (i % 89) * 0.01; }
        BENCH("GEMM 512×512 tiled", 5, gemm_tiled(A, B, C, N));
        std::free(A); std::free(B); std::free(C);
    }

    // GEMM 1024
    {
        const int N = 1024;
        auto* A = (double*)std::calloc(N * N, sizeof(double));
        auto* B = (double*)std::calloc(N * N, sizeof(double));
        auto* C = (double*)std::calloc(N * N, sizeof(double));
        for (int i = 0; i < N*N; i++) { A[i] = (i % 97) * 0.01; B[i] = (i % 89) * 0.01; }
        BENCH("GEMM 1024×1024 tiled", 3, gemm_tiled(A, B, C, N));
        std::free(A); std::free(B); std::free(C);
    }

    // Winograd
    {
        double tile[16], filt[16], out[4];
        for (int i = 0; i < 16; i++) { tile[i] = i * 0.1; filt[i] = (15 - i) * 0.1; }
        int ntiles = 100000;
        BENCH("Winograd F(2,3) 100K tiles", 10, {
            double acc = 0.0;
            for (int t = 0; t < ntiles; t++) {
                tile[0] = t * 0.00001;
                winograd_f2x3_tile(tile, filt, out);
                acc += out[0];
            }
            g_sink = acc;
        });
    }

    // Softmax
    {
        const int N = 100000;
        auto* x = (double*)std::malloc(N * sizeof(double));
        auto* y = (double*)std::malloc(N * sizeof(double));
        for (int i = 0; i < N; i++) x[i] = (i % 1000) * 0.001 - 0.5;
        BENCH("Softmax (2-pass online) 100K", 200, { softmax_online(x, y, N); g_sink = y[N/2]; });
        std::free(x); std::free(y);
    }

    // Fused EW
    {
        const int N = 1000000;
        auto* x = (double*)std::malloc(N * sizeof(double));
        auto* y = (double*)std::malloc(N * sizeof(double));
        for (int i = 0; i < N; i++) x[i] = i * 0.000001;

        BENCH("EW fused (mul+add+relu) 1M", 200, { fused_ew(x, y, N, 2.0, -0.5); g_sink = y[N/2]; });
        BENCH("EW unfused 3-pass 1M", 200, { unfused_ew(x, y, N, 2.0, -0.5); g_sink = y[N/2]; });
        std::free(x); std::free(y);
    }

    // Welford
    {
        const int N = 1000000;
        auto* x = (double*)std::malloc(N * sizeof(double));
        for (int i = 0; i < N; i++) x[i] = (i % 10000) * 0.0001;
        volatile double sink;
        BENCH("Welford-Kahan variance 1M", 50, { auto w = welford_kahan(x, N); sink = w.m2; });
        std::free(x);
    }

    // Kahan dot
    {
        const int N = 10000000;
        auto* a = (double*)std::malloc(N * sizeof(double));
        auto* b = (double*)std::malloc(N * sizeof(double));
        for (int i = 0; i < N; i++) { a[i] = 1.0 + 1e-8 * i; b[i] = 1.0 - 1e-8 * i; }
        volatile double sink;
        BENCH("Kahan dot product 10M", 10, sink = kahan_dot(a, b, N));
        std::free(a); std::free(b);
    }

    // ── 2. MEMORY DISCIPLINE ────────────────────────
    std::printf("\n▓ 2. MEMORY DISCIPLINE\n");
    std::printf("───────────────────────────────────────────\n");

    std::printf("%-40s %12.1f ns/op\n", "malloc/free 64B", bench_alloc_latency(1000000, 64));
    std::printf("%-40s %12.1f ns/op\n", "malloc/free 4KB", bench_alloc_latency(1000000, 4096));
    std::printf("%-40s %12.1f ns/op\n", "malloc/free 1MB", bench_alloc_latency(100000, 1048576));

    // Peak memory analysis
    for (int N : {256, 1024, 4096, 8192, 16384}) {
        size_t std_mem = peak_mem_standard_attention(N, 64);
        size_t flash_mem = peak_mem_flash_attention(N, 64, 32);
        std::printf("  Attention N=%5d: standard=%8.1f MB  flash=%8.3f MB  ratio=%.0f×\n",
            N, std_mem / 1e6, flash_mem / 1e6, (double)std_mem / flash_mem);
    }

    // ── 3. SYSTEM I/O ───────────────────────────────
    std::printf("\n▓ 3. SYSTEM I/O\n");
    std::printf("───────────────────────────────────────────\n");

    for (size_t sz : {(size_t)1<<20, (size_t)1<<25, (size_t)1<<30}) {
        double t = bench_memcpy(sz);
        double bw = sz / (t + 0.001); // bytes/µs = MB/s
        std::printf("  memcpy %6.0f MB: %12.1f µs  (%6.1f GB/s)\n",
            sz / 1e6, t, bw / 1000.0);
    }

    // ── 5. SCALABILITY ──────────────────────────────
    std::printf("\n▓ 5. SCALABILITY & THREADING\n");
    std::printf("───────────────────────────────────────────\n");

    {
        const int N = 10000000;
        auto* data = (double*)std::malloc(N * sizeof(double));
        for (int i = 0; i < N; i++) data[i] = 1.0;

        // Single threaded
        BENCH("Sum 10M (1 thread)", 20, {
            volatile double s = 0;
            for (int i = 0; i < N; i++) s = (double)s + data[i];
        });

        for (int nt : {2, 4, 8}) {
            char label[64];
            std::snprintf(label, sizeof(label), "Sum 10M (atomic, %d threads)", nt);
            BENCH(label, 20, parallel_reduce(data, N, nt));
        }

        for (int nt : {2, 4, 8}) {
            char label[64];
            std::snprintf(label, sizeof(label), "Sum 10M (mutex, %d threads)", nt);
            BENCH(label, 20, parallel_reduce_locked(data, N, nt));
        }

        std::free(data);
    }

    // ── NUMERICAL STABILITY ──────────────────────────
    std::printf("\n▓ NUMERICAL STABILITY\n");
    std::printf("───────────────────────────────────────────\n");

    {
        const int N = 10000000;
        auto* x = (double*)std::malloc(N * sizeof(double));
        // Condition: sum of 1 + tiny perturbation. True sum ≈ N
        for (int i = 0; i < N; i++) x[i] = 1.0 + 1e-12 * (i - N/2);
        double true_sum = (double)N; // approximately

        double naive = summation_naive(x, N);
        double kahan = summation_kahan(x, N);

        std::printf("  True sum (analytic): %.15e\n", true_sum);
        std::printf("  Naive summation:     %.15e  (err=%.2e)\n", naive, std::abs(naive - true_sum));
        std::printf("  Kahan summation:     %.15e  (err=%.2e)\n", kahan, std::abs(kahan - true_sum));

        std::free(x);
    }

    std::printf("\n═══════════════════════════════════════════\n");
    return 0;
}
