/*
 * bench_gemm_blas.cpp — Fair GEMM Comparison: Hand-written vs BLAS (Accelerate)
 * ==============================================================================
 * Purpose: Address the critique that our C++ GEMM benchmark used naive tiled loops
 *          while numpy called Apple Accelerate BLAS, making the comparison unfair.
 *
 * This benchmark runs BOTH:
 *   1. Hand-written tiled GEMM (same as bench_comprehensive_cpp.cpp)
 *   2. Apple Accelerate cblas_dgemm (same BLAS that numpy calls)
 *
 * Compile (macOS):
 *   clang++ -std=c++17 -O3 -march=native -framework Accelerate -o bench_gemm_blas bench_gemm_blas.cpp
 */

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <chrono>
#include <algorithm>

// Apple Accelerate BLAS
#include <Accelerate/Accelerate.h>

using Clock = std::chrono::high_resolution_clock;
using ns = std::chrono::nanoseconds;

static volatile double g_sink = 0.0;

// ── Hand-written tiled GEMM (same as our original benchmark) ──
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
                C[i * N + j] += a * B[k * N + j];
        }
    }
}

// ── BLAS GEMM (Apple Accelerate — same as numpy backend) ──
void gemm_blas(const double* A, const double* B, double* C, int N) {
    // C = 1.0 * A * B + 0.0 * C
    cblas_dgemm(CblasRowMajor, CblasNoTrans, CblasNoTrans,
                N, N, N,
                1.0, A, N, B, N,
                0.0, C, N);
}

// ── Correctness check ──
double max_diff(const double* A, const double* B, int n) {
    double maxd = 0.0;
    for (int i = 0; i < n; i++) {
        double d = std::abs(A[i] - B[i]);
        if (d > maxd) maxd = d;
    }
    return maxd;
}

// ── Benchmark macro ──
#define BENCH(label, iters, body) do { \
    body; /* warmup */ \
    auto _s = Clock::now(); \
    for (int _i = 0; _i < iters; _i++) { body; } \
    auto _e = Clock::now(); \
    double _us = std::chrono::duration_cast<ns>(_e - _s).count() / 1000.0 / iters; \
    std::printf("  %-42s %12.1f µs\n", label, _us); \
    results[result_idx++] = _us; \
} while(0)

int main() {
    double results[20] = {};
    int result_idx = 0;

    std::printf("╔══════════════════════════════════════════════════════════╗\n");
    std::printf("║  Fair GEMM Benchmark: Hand-tiled vs BLAS (Accelerate)   ║\n");
    std::printf("║  Compile: clang++ -O3 -march=native -framework Accelerate ║\n");
    std::printf("╚══════════════════════════════════════════════════════════╝\n\n");

    int sizes[] = {256, 512, 1024, 2048};

    for (int si = 0; si < 4; si++) {
        int N = sizes[si];
        int iters = N <= 512 ? 10 : (N <= 1024 ? 5 : 3);

        std::printf("  ▓ GEMM %d×%d (f64, %d iterations)\n", N, N, iters);
        std::printf("  ─────────────────────────────────────────\n");

        auto* A = (double*)std::calloc(N * N, sizeof(double));
        auto* B = (double*)std::calloc(N * N, sizeof(double));
        auto* C_tiled = (double*)std::calloc(N * N, sizeof(double));
        auto* C_blas  = (double*)std::calloc(N * N, sizeof(double));

        // Initialize with non-trivial values
        for (int i = 0; i < N * N; i++) {
            A[i] = (i % 97) * 0.01;
            B[i] = (i % 89) * 0.01;
        }

        // Run benchmarks
        char label1[80], label2[80];
        std::snprintf(label1, sizeof(label1), "Hand-tiled GEMM %d×%d", N, N);
        std::snprintf(label2, sizeof(label2), "BLAS (Accelerate) GEMM %d×%d", N, N);

        BENCH(label1, iters, { gemm_tiled(A, B, C_tiled, N); g_sink = C_tiled[N/2]; });
        BENCH(label2, iters, { gemm_blas(A, B, C_blas, N); g_sink = C_blas[N/2]; });

        // Correctness: verify both produce same answer
        gemm_tiled(A, B, C_tiled, N);
        gemm_blas(A, B, C_blas, N);
        double err = max_diff(C_tiled, C_blas, N * N);

        double tiled_us = results[result_idx - 2];
        double blas_us  = results[result_idx - 1];
        double ratio = tiled_us / blas_us;

        std::printf("  Max error (tiled vs BLAS):   %.2e\n", err);
        std::printf("  BLAS speedup over tiled:     %.1fx\n", ratio);
        std::printf("  GFLOP/s (tiled):             %.2f\n",
                    2.0 * N * N * N / (tiled_us * 1e-6) / 1e9);
        std::printf("  GFLOP/s (BLAS):              %.2f\n",
                    2.0 * N * N * N / (blas_us * 1e-6) / 1e9);
        std::printf("\n");

        std::free(A); std::free(B); std::free(C_tiled); std::free(C_blas);
    }

    // ── Summary ──
    std::printf("  ▓ SUMMARY\n");
    std::printf("  ═════════════════════════════════════════════════════\n");
    std::printf("  Apple Accelerate BLAS uses AMX coprocessor + NEON.\n");
    std::printf("  Hand-tiled code uses only scalar/auto-vectorized NEON.\n");
    std::printf("  The BLAS numbers represent the TRUE ceiling for CPU GEMM.\n");
    std::printf("  numpy achieves the same speed because it calls the same BLAS.\n");
    std::printf("  ═════════════════════════════════════════════════════\n");

    return 0;
}
