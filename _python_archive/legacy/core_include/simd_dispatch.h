/*
 * simd_dispatch.h – Multi-ISA SIMD Dispatch Engine
 * ===================================================
 * Runtime dispatch to the best available SIMD path:
 *   ARM64:  NEON (128-bit) → SVE (128-2048 bit) → SVE2
 *   x86_64: SSE2 (128-bit) → AVX2 (256-bit) → AVX-512 (512-bit)
 *
 * Provides vectorized primitives for the tensor/AI pipeline:
 *   vadd, vsub, vmul, vdiv, vfma, vmax, vmin,
 *   vreduce_sum, vreduce_max, vrelu, vsigmoid, vtanh
 *
 * cpu_caps_t determines which path is used.
 */

#ifndef VIR_SIMD_DISPATCH_H
#define VIR_SIMD_DISPATCH_H

#include <stddef.h>
#include <stdint.h>
#include "cpu_caps.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * SIMD Backend IDs
 * ═══════════════════════════════════════════════════════ */

typedef enum {
    SIMD_BACKEND_SCALAR = 0,
    SIMD_BACKEND_NEON   = 1,   /* ARM64 128-bit */
    SIMD_BACKEND_SVE    = 2,   /* ARM64 scalable 128-2048 bit */
    SIMD_BACKEND_SVE2   = 3,   /* ARM64 scalable + extra ops */
    SIMD_BACKEND_SSE2   = 4,   /* x86 128-bit */
    SIMD_BACKEND_AVX2   = 5,   /* x86 256-bit */
    SIMD_BACKEND_AVX512 = 6,   /* x86 512-bit */
} simd_backend_t;

/* ═══════════════════════════════════════════════════════
 * Dispatch Table (function pointers)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    simd_backend_t backend;
    uint32_t       vector_width;  /* bytes per vector register */

    /* Element-wise: dst[i] = op(a[i], b[i]) */
    void (*vadd_f32)(float *dst, const float *a, const float *b, size_t n);
    void (*vsub_f32)(float *dst, const float *a, const float *b, size_t n);
    void (*vmul_f32)(float *dst, const float *a, const float *b, size_t n);
    void (*vdiv_f32)(float *dst, const float *a, const float *b, size_t n);
    void (*vfma_f32)(float *dst, const float *a, const float *b, const float *c, size_t n);

    /* Element-wise unary */
    void (*vrelu_f32)(float *dst, const float *src, size_t n);
    void (*vabs_f32)(float *dst, const float *src, size_t n);
    void (*vneg_f32)(float *dst, const float *src, size_t n);

    /* Reduction */
    float (*vreduce_sum_f32)(const float *src, size_t n);
    float (*vreduce_max_f32)(const float *src, size_t n);
    float (*vreduce_min_f32)(const float *src, size_t n);

    /* Scalar broadcast: dst[i] = a[i] * scalar */
    void (*vscale_f32)(float *dst, const float *src, float scalar, size_t n);

    /* Element-wise min/max */
    void (*vmax_f32)(float *dst, const float *a, const float *b, size_t n);
    void (*vmin_f32)(float *dst, const float *a, const float *b, size_t n);

    /* Dot product: sum(a[i]*b[i]) */
    float (*vdot_f32)(const float *a, const float *b, size_t n);
} simd_dispatch_t;

/* ═══════════════════════════════════════════════════════
 * Initialisation
 * ═══════════════════════════════════════════════════════ */

/* Detect and select the best SIMD backend.
 * Populates dispatch table with optimal function pointers. */
int simd_dispatch_init(simd_dispatch_t *disp, const cpu_caps_t *caps);

/* Get global (lazily-initialised) dispatch table. */
const simd_dispatch_t *simd_dispatch_get(void);

/* Get readable name: "NEON", "SVE-256", "AVX-512", etc. */
const char *simd_backend_name(simd_backend_t backend);

#ifdef __cplusplus
}
#endif

#endif /* VIR_SIMD_DISPATCH_H */
