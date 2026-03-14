/*
 * amx_accel.h – AMX Matrix Acceleration
 * ========================================
 * Apple AMX (M1-M4): Undocumented matrix coprocessor
 *   via MSR S3_4_C15_C<n>_<op> instructions.
 *   16×16 FP32 tiles, ~200 GFLOP/s.
 *
 * Intel AMX (Sapphire Rapids+): TILECFG + TDPBF16PS/TDPBSSD
 *   8 tile registers (TMM0-7), each up to 1 KB.
 *
 * Falls back to NEON/AVX micro-kernel GEMM if AMX unavailable.
 */

#ifndef VIR_AMX_ACCEL_H
#define VIR_AMX_ACCEL_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "cpu_caps.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * AMX Backend Selection
 * ═══════════════════════════════════════════════════════ */

typedef enum {
    AMX_BACKEND_NONE       = 0,
    AMX_BACKEND_APPLE_AMX  = 1,   /* Apple M1-M4 coprocessor */
    AMX_BACKEND_INTEL_AMX  = 2,   /* Intel Sapphire Rapids+ */
    AMX_BACKEND_FALLBACK   = 3,   /* NEON/AVX micro-kernel */
} amx_backend_t;

/* Detect which AMX backend to use. */
amx_backend_t amx_detect(const cpu_caps_t *caps);

/* ═══════════════════════════════════════════════════════
 * GEMM: C[M×N] = alpha * A[M×K] × B[K×N] + beta * C
 * ═══════════════════════════════════════════════════════ */

/* General GEMM — dispatches to best available backend. */
void amx_sgemm(
    int M, int N, int K,
    float alpha,
    const float *A, int lda,
    const float *B, int ldb,
    float beta,
    float *C, int ldc
);

/* ═══════════════════════════════════════════════════════
 * Tile Operations (Low-level)
 * ═══════════════════════════════════════════════════════ */

/* Apple AMX: Enable/Disable coprocessor. */
void amx_apple_enable(void);
void amx_apple_disable(void);

/* Apple AMX: 16×16 FP32 tile multiply-accumulate. */
void amx_apple_fma32_tile(
    const float *A,    /* 16×16 tile in A */
    const float *B,    /* 16×16 tile in B */
    float *C           /* 16×16 accumulator in/out */
);

/* ═══════════════════════════════════════════════════════
 * Statistics
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    amx_backend_t backend;
    uint64_t      gemm_calls;
    uint64_t      total_flops;       /* 2*M*N*K per GEMM */
} amx_stats_t;

void amx_get_stats(amx_stats_t *stats);
void amx_reset_stats(void);

#ifdef __cplusplus
}
#endif

#endif /* VIR_AMX_ACCEL_H */
