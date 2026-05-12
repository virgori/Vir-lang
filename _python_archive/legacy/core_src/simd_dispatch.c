/*
 * simd_dispatch.c – Multi-ISA SIMD Dispatch Engine
 * ===================================================
 * Runtime selection of optimal SIMD path based on cpu_caps.
 *
 * Hierarchy (ARM64):  SVE2 > SVE > NEON > scalar
 * Hierarchy (x86_64): AVX-512 > AVX2 > SSE2 > scalar
 */

#include "simd_dispatch.h"

#include <string.h>
#include <math.h>

/* ═══════════════════════════════════════════════════════
 * SCALAR FALLBACK (always available)
 * ═══════════════════════════════════════════════════════ */

static void scalar_vadd_f32(float *d, const float *a, const float *b, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = a[i] + b[i]; }

static void scalar_vsub_f32(float *d, const float *a, const float *b, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = a[i] - b[i]; }

static void scalar_vmul_f32(float *d, const float *a, const float *b, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = a[i] * b[i]; }

static void scalar_vdiv_f32(float *d, const float *a, const float *b, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = a[i] / b[i]; }

static void scalar_vfma_f32(float *d, const float *a, const float *b, const float *c, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = a[i] * b[i] + c[i]; }

static void scalar_vrelu_f32(float *d, const float *s, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = s[i] > 0.0f ? s[i] : 0.0f; }

static void scalar_vabs_f32(float *d, const float *s, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = fabsf(s[i]); }

static void scalar_vneg_f32(float *d, const float *s, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = -s[i]; }

static float scalar_vreduce_sum_f32(const float *s, size_t n)
{ float acc = 0.0f; for (size_t i = 0; i < n; i++) acc += s[i]; return acc; }

static float scalar_vreduce_max_f32(const float *s, size_t n)
{ if (n == 0) return 0.0f; float m = s[0]; for (size_t i = 1; i < n; i++) if (s[i] > m) m = s[i]; return m; }

static float scalar_vreduce_min_f32(const float *s, size_t n)
{ if (n == 0) return 0.0f; float m = s[0]; for (size_t i = 1; i < n; i++) if (s[i] < m) m = s[i]; return m; }

static void scalar_vscale_f32(float *d, const float *s, float sc, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = s[i] * sc; }

static void scalar_vmax_f32(float *d, const float *a, const float *b, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = a[i] > b[i] ? a[i] : b[i]; }

static void scalar_vmin_f32(float *d, const float *a, const float *b, size_t n)
{ for (size_t i = 0; i < n; i++) d[i] = a[i] < b[i] ? a[i] : b[i]; }

static float scalar_vdot_f32(const float *a, const float *b, size_t n)
{ float acc = 0.0f; for (size_t i = 0; i < n; i++) acc += a[i] * b[i]; return acc; }

static void fill_scalar(simd_dispatch_t *d)
{
    d->backend      = SIMD_BACKEND_SCALAR;
    d->vector_width = 4; /* single float */
    d->vadd_f32     = scalar_vadd_f32;
    d->vsub_f32     = scalar_vsub_f32;
    d->vmul_f32     = scalar_vmul_f32;
    d->vdiv_f32     = scalar_vdiv_f32;
    d->vfma_f32     = scalar_vfma_f32;
    d->vrelu_f32    = scalar_vrelu_f32;
    d->vabs_f32     = scalar_vabs_f32;
    d->vneg_f32     = scalar_vneg_f32;
    d->vreduce_sum_f32 = scalar_vreduce_sum_f32;
    d->vreduce_max_f32 = scalar_vreduce_max_f32;
    d->vreduce_min_f32 = scalar_vreduce_min_f32;
    d->vscale_f32   = scalar_vscale_f32;
    d->vmax_f32     = scalar_vmax_f32;
    d->vmin_f32     = scalar_vmin_f32;
    d->vdot_f32     = scalar_vdot_f32;
}

/* ═══════════════════════════════════════════════════════
 * ARM64 NEON (128-bit, 4×f32)
 * ═══════════════════════════════════════════════════════ */

#if defined(__aarch64__)
#include <arm_neon.h>

static void neon_vadd_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vaddq_f32(vld1q_f32(a + i), vld1q_f32(b + i)));
    for (; i < n; i++) d[i] = a[i] + b[i];
}

static void neon_vsub_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vsubq_f32(vld1q_f32(a + i), vld1q_f32(b + i)));
    for (; i < n; i++) d[i] = a[i] - b[i];
}

static void neon_vmul_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vmulq_f32(vld1q_f32(a + i), vld1q_f32(b + i)));
    for (; i < n; i++) d[i] = a[i] * b[i];
}

static void neon_vdiv_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vdivq_f32(vld1q_f32(a + i), vld1q_f32(b + i)));
    for (; i < n; i++) d[i] = a[i] / b[i];
}

static void neon_vfma_f32(float *d, const float *a, const float *b, const float *c, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vfmaq_f32(vld1q_f32(c + i), vld1q_f32(a + i), vld1q_f32(b + i)));
    for (; i < n; i++) d[i] = a[i] * b[i] + c[i];
}

static void neon_vrelu_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    float32x4_t zero = vdupq_n_f32(0.0f);
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vmaxq_f32(vld1q_f32(s + i), zero));
    for (; i < n; i++) d[i] = s[i] > 0.0f ? s[i] : 0.0f;
}

static void neon_vabs_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vabsq_f32(vld1q_f32(s + i)));
    for (; i < n; i++) d[i] = fabsf(s[i]);
}

static void neon_vneg_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vnegq_f32(vld1q_f32(s + i)));
    for (; i < n; i++) d[i] = -s[i];
}

static float neon_vreduce_sum_f32(const float *s, size_t n)
{
    float32x4_t acc = vdupq_n_f32(0.0f);
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        acc = vaddq_f32(acc, vld1q_f32(s + i));
    float result = vaddvq_f32(acc);
    for (; i < n; i++) result += s[i];
    return result;
}

static float neon_vreduce_max_f32(const float *s, size_t n)
{
    if (n == 0) return 0.0f;
    float32x4_t acc = vdupq_n_f32(s[0]);
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        acc = vmaxq_f32(acc, vld1q_f32(s + i));
    float result = vmaxvq_f32(acc);
    for (; i < n; i++) if (s[i] > result) result = s[i];
    return result;
}

static float neon_vreduce_min_f32(const float *s, size_t n)
{
    if (n == 0) return 0.0f;
    float32x4_t acc = vdupq_n_f32(s[0]);
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        acc = vminq_f32(acc, vld1q_f32(s + i));
    float result = vminvq_f32(acc);
    for (; i < n; i++) if (s[i] < result) result = s[i];
    return result;
}

static void neon_vscale_f32(float *d, const float *s, float sc, size_t n)
{
    float32x4_t vsc = vdupq_n_f32(sc);
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vmulq_f32(vld1q_f32(s + i), vsc));
    for (; i < n; i++) d[i] = s[i] * sc;
}

static void neon_vmax_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vmaxq_f32(vld1q_f32(a + i), vld1q_f32(b + i)));
    for (; i < n; i++) d[i] = a[i] > b[i] ? a[i] : b[i];
}

static void neon_vmin_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        vst1q_f32(d + i, vminq_f32(vld1q_f32(a + i), vld1q_f32(b + i)));
    for (; i < n; i++) d[i] = a[i] < b[i] ? a[i] : b[i];
}

static float neon_vdot_f32(const float *a, const float *b, size_t n)
{
    float32x4_t acc = vdupq_n_f32(0.0f);
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        acc = vfmaq_f32(acc, vld1q_f32(a + i), vld1q_f32(b + i));
    float result = vaddvq_f32(acc);
    for (; i < n; i++) result += a[i] * b[i];
    return result;
}

static void fill_neon(simd_dispatch_t *d)
{
    d->backend      = SIMD_BACKEND_NEON;
    d->vector_width = 16; /* 128-bit */
    d->vadd_f32     = neon_vadd_f32;
    d->vsub_f32     = neon_vsub_f32;
    d->vmul_f32     = neon_vmul_f32;
    d->vdiv_f32     = neon_vdiv_f32;
    d->vfma_f32     = neon_vfma_f32;
    d->vrelu_f32    = neon_vrelu_f32;
    d->vabs_f32     = neon_vabs_f32;
    d->vneg_f32     = neon_vneg_f32;
    d->vreduce_sum_f32 = neon_vreduce_sum_f32;
    d->vreduce_max_f32 = neon_vreduce_max_f32;
    d->vreduce_min_f32 = neon_vreduce_min_f32;
    d->vscale_f32   = neon_vscale_f32;
    d->vmax_f32     = neon_vmax_f32;
    d->vmin_f32     = neon_vmin_f32;
    d->vdot_f32     = neon_vdot_f32;
}

/* ═══════════════════════════════════════════════════════
 * ARM64 SVE (Scalable Vector Extension, 128-2048 bit)
 * ═══════════════════════════════════════════════════════
 * SVE uses predicated, vector-length agnostic (VLA) code.
 * The same binary works on any SVE width.
 */

#if defined(__ARM_FEATURE_SVE)
#include <arm_sve.h>

static void sve_vadd_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    svbool_t pg;
    while (i < n) {
        pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svfloat32_t va = svld1_f32(pg, a + i);
        svfloat32_t vb = svld1_f32(pg, b + i);
        svst1_f32(pg, d + i, svadd_f32_x(pg, va, vb));
        i += svcntw();
    }
}

static void sve_vsub_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svst1_f32(pg, d + i, svsub_f32_x(pg, svld1_f32(pg, a + i), svld1_f32(pg, b + i)));
        i += svcntw();
    }
}

static void sve_vmul_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svst1_f32(pg, d + i, svmul_f32_x(pg, svld1_f32(pg, a + i), svld1_f32(pg, b + i)));
        i += svcntw();
    }
}

static void sve_vdiv_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svst1_f32(pg, d + i, svdiv_f32_x(pg, svld1_f32(pg, a + i), svld1_f32(pg, b + i)));
        i += svcntw();
    }
}

static void sve_vfma_f32(float *d, const float *a, const float *b, const float *c, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svfloat32_t vc = svld1_f32(pg, c + i);
        svfloat32_t va = svld1_f32(pg, a + i);
        svfloat32_t vb = svld1_f32(pg, b + i);
        svst1_f32(pg, d + i, svmla_f32_x(pg, vc, va, vb));
        i += svcntw();
    }
}

static void sve_vrelu_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svfloat32_t v = svld1_f32(pg, s + i);
        svst1_f32(pg, d + i, svmax_f32_x(pg, v, svdup_f32(0.0f)));
        i += svcntw();
    }
}

static void sve_vabs_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svst1_f32(pg, d + i, svabs_f32_x(pg, svld1_f32(pg, s + i)));
        i += svcntw();
    }
}

static void sve_vneg_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svst1_f32(pg, d + i, svneg_f32_x(pg, svld1_f32(pg, s + i)));
        i += svcntw();
    }
}

static float sve_vreduce_sum_f32(const float *s, size_t n)
{
    svfloat32_t acc = svdup_f32(0.0f);
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        acc = svadd_f32_m(pg, acc, svld1_f32(pg, s + i));
        i += svcntw();
    }
    return svaddv_f32(svptrue_b32(), acc);
}

static float sve_vreduce_max_f32(const float *s, size_t n)
{
    if (n == 0) return 0.0f;
    svfloat32_t acc = svdup_f32(s[0]);
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        acc = svmax_f32_m(pg, acc, svld1_f32(pg, s + i));
        i += svcntw();
    }
    return svmaxv_f32(svptrue_b32(), acc);
}

static float sve_vreduce_min_f32(const float *s, size_t n)
{
    if (n == 0) return 0.0f;
    svfloat32_t acc = svdup_f32(s[0]);
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        acc = svmin_f32_m(pg, acc, svld1_f32(pg, s + i));
        i += svcntw();
    }
    return svminv_f32(svptrue_b32(), acc);
}

static void sve_vscale_f32(float *d, const float *s, float sc, size_t n)
{
    svfloat32_t vsc = svdup_f32(sc);
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svst1_f32(pg, d + i, svmul_f32_x(pg, svld1_f32(pg, s + i), vsc));
        i += svcntw();
    }
}

static void sve_vmax_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svst1_f32(pg, d + i, svmax_f32_x(pg, svld1_f32(pg, a + i), svld1_f32(pg, b + i)));
        i += svcntw();
    }
}

static void sve_vmin_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        svst1_f32(pg, d + i, svmin_f32_x(pg, svld1_f32(pg, a + i), svld1_f32(pg, b + i)));
        i += svcntw();
    }
}

static float sve_vdot_f32(const float *a, const float *b, size_t n)
{
    svfloat32_t acc = svdup_f32(0.0f);
    size_t i = 0;
    while (i < n) {
        svbool_t pg = svwhilelt_b32((uint64_t)i, (uint64_t)n);
        acc = svmla_f32_m(pg, acc, svld1_f32(pg, a + i), svld1_f32(pg, b + i));
        i += svcntw();
    }
    return svaddv_f32(svptrue_b32(), acc);
}

static void fill_sve(simd_dispatch_t *d, uint32_t sve_width_bits)
{
    d->backend      = SIMD_BACKEND_SVE;
    d->vector_width = sve_width_bits / 8;
    d->vadd_f32     = sve_vadd_f32;
    d->vsub_f32     = sve_vsub_f32;
    d->vmul_f32     = sve_vmul_f32;
    d->vdiv_f32     = sve_vdiv_f32;
    d->vfma_f32     = sve_vfma_f32;
    d->vrelu_f32    = sve_vrelu_f32;
    d->vabs_f32     = sve_vabs_f32;
    d->vneg_f32     = sve_vneg_f32;
    d->vreduce_sum_f32 = sve_vreduce_sum_f32;
    d->vreduce_max_f32 = sve_vreduce_max_f32;
    d->vreduce_min_f32 = sve_vreduce_min_f32;
    d->vscale_f32   = sve_vscale_f32;
    d->vmax_f32     = sve_vmax_f32;
    d->vmin_f32     = sve_vmin_f32;
    d->vdot_f32     = sve_vdot_f32;
}

#endif /* __ARM_FEATURE_SVE */
#endif /* __aarch64__ */


/* ═══════════════════════════════════════════════════════
 * x86_64 SSE2 (128-bit, 4×f32)
 * ═══════════════════════════════════════════════════════ */

#if defined(__x86_64__) || defined(_M_X64)
#include <immintrin.h>

static void sse2_vadd_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_add_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i)));
    for (; i < n; i++) d[i] = a[i] + b[i];
}

static void sse2_vsub_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_sub_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i)));
    for (; i < n; i++) d[i] = a[i] - b[i];
}

static void sse2_vmul_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_mul_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i)));
    for (; i < n; i++) d[i] = a[i] * b[i];
}

static void sse2_vdiv_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_div_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i)));
    for (; i < n; i++) d[i] = a[i] / b[i];
}

static void sse2_vfma_f32(float *d, const float *a, const float *b, const float *c, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4) {
        __m128 va = _mm_loadu_ps(a + i);
        __m128 vb = _mm_loadu_ps(b + i);
        __m128 vc = _mm_loadu_ps(c + i);
        _mm_storeu_ps(d + i, _mm_add_ps(_mm_mul_ps(va, vb), vc));
    }
    for (; i < n; i++) d[i] = a[i] * b[i] + c[i];
}

static void sse2_vrelu_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    __m128 zero = _mm_setzero_ps();
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_max_ps(_mm_loadu_ps(s + i), zero));
    for (; i < n; i++) d[i] = s[i] > 0.0f ? s[i] : 0.0f;
}

static void sse2_vabs_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    __m128 sign_mask = _mm_set1_ps(-0.0f);
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_andnot_ps(sign_mask, _mm_loadu_ps(s + i)));
    for (; i < n; i++) d[i] = fabsf(s[i]);
}

static void sse2_vneg_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    __m128 sign_mask = _mm_set1_ps(-0.0f);
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_xor_ps(_mm_loadu_ps(s + i), sign_mask));
    for (; i < n; i++) d[i] = -s[i];
}

static float sse2_vreduce_sum_f32(const float *s, size_t n)
{
    __m128 acc = _mm_setzero_ps();
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        acc = _mm_add_ps(acc, _mm_loadu_ps(s + i));
    /* Horizontal sum */
    acc = _mm_hadd_ps(acc, acc);
    acc = _mm_hadd_ps(acc, acc);
    float result;
    _mm_store_ss(&result, acc);
    for (; i < n; i++) result += s[i];
    return result;
}

static float sse2_vreduce_max_f32(const float *s, size_t n)
{
    if (n == 0) return 0.0f;
    __m128 acc = _mm_set1_ps(s[0]);
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        acc = _mm_max_ps(acc, _mm_loadu_ps(s + i));
    /* Horizontal max */
    acc = _mm_max_ps(acc, _mm_shuffle_ps(acc, acc, _MM_SHUFFLE(2,3,0,1)));
    acc = _mm_max_ps(acc, _mm_shuffle_ps(acc, acc, _MM_SHUFFLE(1,0,3,2)));
    float result;
    _mm_store_ss(&result, acc);
    for (; i < n; i++) if (s[i] > result) result = s[i];
    return result;
}

static float sse2_vreduce_min_f32(const float *s, size_t n)
{
    if (n == 0) return 0.0f;
    __m128 acc = _mm_set1_ps(s[0]);
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        acc = _mm_min_ps(acc, _mm_loadu_ps(s + i));
    acc = _mm_min_ps(acc, _mm_shuffle_ps(acc, acc, _MM_SHUFFLE(2,3,0,1)));
    acc = _mm_min_ps(acc, _mm_shuffle_ps(acc, acc, _MM_SHUFFLE(1,0,3,2)));
    float result;
    _mm_store_ss(&result, acc);
    for (; i < n; i++) if (s[i] < result) result = s[i];
    return result;
}

static void sse2_vscale_f32(float *d, const float *s, float sc, size_t n)
{
    __m128 vsc = _mm_set1_ps(sc);
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_mul_ps(_mm_loadu_ps(s + i), vsc));
    for (; i < n; i++) d[i] = s[i] * sc;
}

static void sse2_vmax_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_max_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i)));
    for (; i < n; i++) d[i] = a[i] > b[i] ? a[i] : b[i];
}

static void sse2_vmin_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        _mm_storeu_ps(d + i, _mm_min_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i)));
    for (; i < n; i++) d[i] = a[i] < b[i] ? a[i] : b[i];
}

static float sse2_vdot_f32(const float *a, const float *b, size_t n)
{
    __m128 acc = _mm_setzero_ps();
    size_t i = 0;
    for (; i + 4 <= n; i += 4)
        acc = _mm_add_ps(acc, _mm_mul_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i)));
    acc = _mm_hadd_ps(acc, acc);
    acc = _mm_hadd_ps(acc, acc);
    float result;
    _mm_store_ss(&result, acc);
    for (; i < n; i++) result += a[i] * b[i];
    return result;
}

static void fill_sse2(simd_dispatch_t *d)
{
    d->backend      = SIMD_BACKEND_SSE2;
    d->vector_width = 16;
    d->vadd_f32     = sse2_vadd_f32;
    d->vsub_f32     = sse2_vsub_f32;
    d->vmul_f32     = sse2_vmul_f32;
    d->vdiv_f32     = sse2_vdiv_f32;
    d->vfma_f32     = sse2_vfma_f32;
    d->vrelu_f32    = sse2_vrelu_f32;
    d->vabs_f32     = sse2_vabs_f32;
    d->vneg_f32     = sse2_vneg_f32;
    d->vreduce_sum_f32 = sse2_vreduce_sum_f32;
    d->vreduce_max_f32 = sse2_vreduce_max_f32;
    d->vreduce_min_f32 = sse2_vreduce_min_f32;
    d->vscale_f32   = sse2_vscale_f32;
    d->vmax_f32     = sse2_vmax_f32;
    d->vmin_f32     = sse2_vmin_f32;
    d->vdot_f32     = sse2_vdot_f32;
}

/* ── AVX2 (256-bit, 8×f32) ─────────────────────────── */

#if defined(__AVX2__)
static void avx2_vadd_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 8 <= n; i += 8)
        _mm256_storeu_ps(d + i, _mm256_add_ps(_mm256_loadu_ps(a + i), _mm256_loadu_ps(b + i)));
    for (; i < n; i++) d[i] = a[i] + b[i];
}

static void avx2_vmul_f32(float *d, const float *a, const float *b, size_t n)
{
    size_t i = 0;
    for (; i + 8 <= n; i += 8)
        _mm256_storeu_ps(d + i, _mm256_mul_ps(_mm256_loadu_ps(a + i), _mm256_loadu_ps(b + i)));
    for (; i < n; i++) d[i] = a[i] * b[i];
}

static void avx2_vfma_f32(float *d, const float *a, const float *b, const float *c, size_t n)
{
    size_t i = 0;
    for (; i + 8 <= n; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        __m256 vc = _mm256_loadu_ps(c + i);
        _mm256_storeu_ps(d + i, _mm256_fmadd_ps(va, vb, vc));
    }
    for (; i < n; i++) d[i] = a[i] * b[i] + c[i];
}

static void avx2_vrelu_f32(float *d, const float *s, size_t n)
{
    size_t i = 0;
    __m256 zero = _mm256_setzero_ps();
    for (; i + 8 <= n; i += 8)
        _mm256_storeu_ps(d + i, _mm256_max_ps(_mm256_loadu_ps(s + i), zero));
    for (; i < n; i++) d[i] = s[i] > 0.0f ? s[i] : 0.0f;
}

static float avx2_vdot_f32(const float *a, const float *b, size_t n)
{
    __m256 acc = _mm256_setzero_ps();
    size_t i = 0;
    for (; i + 8 <= n; i += 8)
        acc = _mm256_fmadd_ps(_mm256_loadu_ps(a + i), _mm256_loadu_ps(b + i), acc);
    /* Reduce 256 → 128 → scalar */
    __m128 lo = _mm256_castps256_ps128(acc);
    __m128 hi = _mm256_extractf128_ps(acc, 1);
    __m128 sum = _mm_add_ps(lo, hi);
    sum = _mm_hadd_ps(sum, sum);
    sum = _mm_hadd_ps(sum, sum);
    float result;
    _mm_store_ss(&result, sum);
    for (; i < n; i++) result += a[i] * b[i];
    return result;
}

static void fill_avx2(simd_dispatch_t *d)
{
    /* Start with SSE2 for ops not yet specialized */
    fill_sse2(d);
    d->backend      = SIMD_BACKEND_AVX2;
    d->vector_width = 32;
    d->vadd_f32     = avx2_vadd_f32;
    d->vmul_f32     = avx2_vmul_f32;
    d->vfma_f32     = avx2_vfma_f32;
    d->vrelu_f32    = avx2_vrelu_f32;
    d->vdot_f32     = avx2_vdot_f32;
}
#endif /* __AVX2__ */

#endif /* __x86_64__ */


/* ═══════════════════════════════════════════════════════
 * Dispatch Initialisation
 * ═══════════════════════════════════════════════════════ */

int simd_dispatch_init(simd_dispatch_t *disp, const cpu_caps_t *caps)
{
    if (!disp) return -1;

    /* Start with scalar fallback */
    fill_scalar(disp);

    if (!caps) return 0;

#if defined(__aarch64__)
    /* ARM64: NEON is always available on AArch64 */
    fill_neon(disp);

#if defined(__ARM_FEATURE_SVE)
    if (caps->simd.sve) {
        uint32_t w = caps->simd.sve_width;
        if (w == 0) w = 128; /* minimal SVE */
        fill_sve(disp, w);
        if (caps->simd.sve2)
            disp->backend = SIMD_BACKEND_SVE2;
    }
#endif

#elif defined(__x86_64__) || defined(_M_X64)
    if (caps->simd.sse2)
        fill_sse2(disp);

#if defined(__AVX2__)
    if (caps->simd.avx2)
        fill_avx2(disp);
#endif

    /* AVX-512 would go here when EVEX emitters are ready */

#endif /* arch */

    return 0;
}

/* Global singleton */
static simd_dispatch_t g_disp;
static int g_disp_init = 0;

const simd_dispatch_t *simd_dispatch_get(void)
{
    if (!g_disp_init) {
        cpu_caps_t caps;
        cpu_caps_detect(&caps);
        simd_dispatch_init(&g_disp, &caps);
        g_disp_init = 1;
    }
    return &g_disp;
}

const char *simd_backend_name(simd_backend_t backend)
{
    switch (backend) {
        case SIMD_BACKEND_SCALAR: return "Scalar";
        case SIMD_BACKEND_NEON:   return "NEON-128";
        case SIMD_BACKEND_SVE:    return "SVE";
        case SIMD_BACKEND_SVE2:   return "SVE2";
        case SIMD_BACKEND_SSE2:   return "SSE2-128";
        case SIMD_BACKEND_AVX2:   return "AVX2-256";
        case SIMD_BACKEND_AVX512: return "AVX-512";
        default:                  return "Unknown";
    }
}
