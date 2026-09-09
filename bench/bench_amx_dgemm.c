/*
 * bench_amx_dgemm.c — AMX/Accelerate DGEMM benchmark callable from Vir FFI
 * ==========================================================================
 * Calls cblas_dgemm via Apple Accelerate framework to benchmark
 * the Apple AMX coprocessor directly from the Vir ecosystem.
 *
 * Build (macOS arm64):
 *   cc -O2 -shared -fPIC -framework Accelerate \
 *      -o libvir_amx_bench.dylib bench_amx_dgemm.c
 *
 * Or standalone:
 *   cc -O2 -framework Accelerate -o bench_amx_dgemm bench_amx_dgemm.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define ACCELERATE_NEW_LAPACK 1
#include <Accelerate/Accelerate.h>

/* ═══════════════════════════════════════════════════════
 * Timing helpers
 * ═══════════════════════════════════════════════════════ */

static double now_sec(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

/* ═══════════════════════════════════════════════════════
 * DGEMM benchmark — single size
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    int    n;
    int    iters;
    double best_us;
    double avg_us;
    double gflops_best;
    double gflops_avg;
} bench_result_t;

static bench_result_t bench_dgemm(int n, int iters)
{
    size_t bytes = (size_t)n * n * sizeof(double);
    double *A = (double *)malloc(bytes);
    double *B = (double *)malloc(bytes);
    double *C = (double *)malloc(bytes);

    /* Initialize with small values to avoid overflow */
    srand(42);
    for (int i = 0; i < n * n; i++) {
        A[i] = (double)(rand() % 100) / 100.0;
        B[i] = (double)(rand() % 100) / 100.0;
    }

    double flops = 2.0 * (double)n * (double)n * (double)n;
    double best = 1e30;
    double total = 0.0;

    /* Warmup */
    memset(C, 0, bytes);
    cblas_dgemm(CblasRowMajor, CblasNoTrans, CblasNoTrans,
                n, n, n, 1.0, A, n, B, n, 0.0, C, n);

    for (int i = 0; i < iters; i++) {
        memset(C, 0, bytes);
        double t0 = now_sec();
        cblas_dgemm(CblasRowMajor, CblasNoTrans, CblasNoTrans,
                    n, n, n, 1.0, A, n, B, n, 0.0, C, n);
        double t1 = now_sec();
        double elapsed = (t1 - t0) * 1e6;  /* microseconds */
        if (elapsed < best) best = elapsed;
        total += elapsed;
    }

    free(A);
    free(B);
    free(C);

    bench_result_t r;
    r.n           = n;
    r.iters       = iters;
    r.best_us     = best;
    r.avg_us      = total / iters;
    r.gflops_best = flops / (best * 1e-6) / 1e9;
    r.gflops_avg  = flops / (r.avg_us * 1e-6) / 1e9;
    return r;
}

/* ═══════════════════════════════════════════════════════
 * FFI entry point — callable from Vir
 * ═══════════════════════════════════════════════════════
 * Returns peak GFLOP/s as int64 (x100 for 2 decimal precision)
 */

int64_t vir_amx_bench_dgemm(int64_t n, int64_t iters)
{
    bench_result_t r = bench_dgemm((int)n, (int)iters);
    printf("  DGEMM %dx%d: best=%.1f us  avg=%.1f us  "
           "GFLOP/s(best)=%.2f  GFLOP/s(avg)=%.2f\n",
           r.n, r.n, r.best_us, r.avg_us, r.gflops_best, r.gflops_avg);
    return (int64_t)(r.gflops_best * 100.0);
}

/* ═══════════════════════════════════════════════════════
 * SGEMM benchmark (f32) — uses AMX more efficiently
 * ═══════════════════════════════════════════════════════ */

int64_t vir_amx_bench_sgemm(int64_t n, int64_t iters)
{
    size_t bytes = (size_t)n * n * sizeof(float);
    float *A = (float *)malloc(bytes);
    float *B = (float *)malloc(bytes);
    float *C = (float *)malloc(bytes);

    srand(42);
    for (int i = 0; i < n * n; i++) {
        A[i] = (float)(rand() % 100) / 100.0f;
        B[i] = (float)(rand() % 100) / 100.0f;
    }

    double flops = 2.0 * (double)n * (double)n * (double)n;
    double best = 1e30;
    double total = 0.0;

    /* Warmup */
    memset(C, 0, bytes);
    cblas_sgemm(CblasRowMajor, CblasNoTrans, CblasNoTrans,
                n, n, n, 1.0f, A, (int)n, B, (int)n, 0.0f, C, (int)n);

    for (int i = 0; i < (int)iters; i++) {
        memset(C, 0, bytes);
        double t0 = now_sec();
        cblas_sgemm(CblasRowMajor, CblasNoTrans, CblasNoTrans,
                    n, n, n, 1.0f, A, (int)n, B, (int)n, 0.0f, C, (int)n);
        double t1 = now_sec();
        double elapsed = (t1 - t0) * 1e6;
        if (elapsed < best) best = elapsed;
        total += elapsed;
    }

    free(A);
    free(B);
    free(C);

    double gflops_best = flops / (best * 1e-6) / 1e9;
    double gflops_avg  = flops / ((total / iters) * 1e-6) / 1e9;

    printf("  SGEMM %lldx%lld: best=%.1f us  avg=%.1f us  "
           "GFLOP/s(best)=%.2f  GFLOP/s(avg)=%.2f\n",
           n, n, best, total / iters, gflops_best, gflops_avg);

    return (int64_t)(gflops_best * 100.0);
}

/* ═══════════════════════════════════════════════════════
 * Standalone main — run full benchmark suite
 * ═══════════════════════════════════════════════════════ */

#ifndef VIR_FFI_ONLY

int main(void)
{
    printf("╔══════════════════════════════════════════════════════════════╗\n");
    printf("║  Vir AMX Benchmark — Apple Accelerate BLAS via FFI         ║\n");
    printf("║  Platform: arm64 macOS (Apple Silicon AMX coprocessor)     ║\n");
    printf("╚══════════════════════════════════════════════════════════════╝\n\n");

    int sizes[]  = { 256, 512, 1024, 2048, 4096 };
    int iters[]  = {  20,  10,    5,    3,    2 };
    int nsizes = sizeof(sizes) / sizeof(sizes[0]);

    printf("=== DGEMM (f64) — Double Precision ===\n");
    for (int i = 0; i < nsizes; i++) {
        vir_amx_bench_dgemm(sizes[i], iters[i]);
    }

    printf("\n=== SGEMM (f32) — Single Precision ===\n");
    for (int i = 0; i < nsizes; i++) {
        vir_amx_bench_sgemm(sizes[i], iters[i]);
    }

    printf("\n=== Target: ~300 GFLOP/s (f64) or ~600 GFLOP/s (f32) on M-series ===\n");

    return 0;
}

#endif /* VIR_FFI_ONLY */
