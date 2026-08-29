/* ═══════════════════════════════════════════════════════════════════════════════
 * Vir Native Core — C Implementation (SIMD Optimized)
 * ═══════════════════════════════════════════════════════════════════════════════
 * 
 * This is the C implementation of performance-critical operations.
 * Compile with: clang -O3 -mavx2 -c vir_native_core.c -o vir_native_core.o
 * Create library: ar rcs libvir_native.a vir_native_core.o
 *
 * The Vir transpiler generates Swift code that calls these functions
 * through the native bridge.
 * ═══════════════════════════════════════════════════════════════════════════════
 */

#include <stdint.h>
#include <stdbool.h>
#include <math.h>

#ifdef __ARM_NEON__
#include <arm_neon.h>
#endif

#ifdef __AVX2__
#include <immintrin.h>
#endif

/* ─────────────────────────────────────────────────────────────────────────────
 * Dot Product — SIMD Optimized
 * ───────────────────────────────────────────────────────────────────────────── */

float vir_simd_dot_f32(const float* a, const float* b, int64_t len) {
    float sum = 0.0f;
    int64_t i = 0;
    
#ifdef __ARM_NEON__
    // Apple Silicon (M1/M2/M3) NEON implementation
    float32x4_t vsum = vdupq_n_f32(0.0f);
    
    for (; i + 4 <= len; i += 4) {
        float32x4_t va = vld1q_f32(a + i);
        float32x4_t vb = vld1q_f32(b + i);
        vsum = vfmaq_f32(vsum, va, vb);  // Fused multiply-add
    }
    
    // Horizontal sum
    sum = vaddvq_f32(vsum);
    
#elif defined(__AVX2__)
    // x86 AVX2 implementation
    __m256 vsum = _mm256_setzero_ps();
    
    for (; i + 8 <= len; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        vsum = _mm256_fmadd_ps(va, vb, vsum);
    }
    
    // Horizontal sum of 8 floats
    __m128 vlow  = _mm256_castps256_ps128(vsum);
    __m128 vhigh = _mm256_extractf128_ps(vsum, 1);
    __m128 vsum128 = _mm_add_ps(vlow, vhigh);
    __m128 vshuf = _mm_movehdup_ps(vsum128);
    __m128 vsums = _mm_add_ps(vsum128, vshuf);
    vshuf = _mm_movehl_ps(vshuf, vsums);
    vsums = _mm_add_ss(vsums, vshuf);
    sum = _mm_cvtss_f32(vsums);
#endif
    
    // Scalar fallback for remaining elements
    for (; i < len; i++) {
        sum += a[i] * b[i];
    }
    
    return sum;
}

/* ─────────────────────────────────────────────────────────────────────────────
 * Matrix Multiplication — SIMD Optimized
 * ───────────────────────────────────────────────────────────────────────────── */

void vir_simd_matmul_f32(const float* a, const float* b, float* out,
                          int64_t m, int64_t n, int64_t k) {
    // Simple SIMD-optimized matrix multiplication
    // For production, consider using vendor BLAS (Accelerate on macOS)
    
    for (int64_t i = 0; i < m; i++) {
        for (int64_t j = 0; j < n; j++) {
            float sum = 0.0f;
            int64_t idx = 0;
            
#ifdef __ARM_NEON__
            float32x4_t vsum = vdupq_n_f32(0.0f);
            
            for (; idx + 4 <= k; idx += 4) {
                float32x4_t va = vld1q_f32(a + i * k + idx);
                // For b, we need column access - this is simplified
                float32x4_t vb = (float32x4_t){
                    b[(idx + 0) * n + j],
                    b[(idx + 1) * n + j],
                    b[(idx + 2) * n + j],
                    b[(idx + 3) * n + j]
                };
                vsum = vfmaq_f32(vsum, va, vb);
            }
            sum = vaddvq_f32(vsum);
#endif
            
            // Scalar for remaining
            for (; idx < k; idx++) {
                sum += a[i * k + idx] * b[idx * n + j];
            }
            
            out[i * n + j] = sum;
        }
    }
}

/* ─────────────────────────────────────────────────────────────────────────────
 * ReLU Activation — SIMD Optimized
 * ───────────────────────────────────────────────────────────────────────────── */

void vir_simd_relu_f32(float* data, int64_t len) {
    int64_t i = 0;
    
#ifdef __ARM_NEON__
    float32x4_t vzero = vdupq_n_f32(0.0f);
    
    for (; i + 4 <= len; i += 4) {
        float32x4_t v = vld1q_f32(data + i);
        v = vmaxq_f32(v, vzero);  // max(v, 0)
        vst1q_f32(data + i, v);
    }
    
#elif defined(__AVX2__)
    __m256 vzero = _mm256_setzero_ps();
    
    for (; i + 8 <= len; i += 8) {
        __m256 v = _mm256_loadu_ps(data + i);
        v = _mm256_max_ps(v, vzero);
        _mm256_storeu_ps(data + i, v);
    }
#endif
    
    // Scalar fallback
    for (; i < len; i++) {
        if (data[i] < 0.0f) {
            data[i] = 0.0f;
        }
    }
}

/* ─────────────────────────────────────────────────────────────────────────────
 * Vector Addition — SIMD Optimized
 * ───────────────────────────────────────────────────────────────────────────── */

void vir_simd_vec_add_f32(const float* a, const float* b, float* out, int64_t len) {
    int64_t i = 0;
    
#ifdef __ARM_NEON__
    for (; i + 4 <= len; i += 4) {
        float32x4_t va = vld1q_f32(a + i);
        float32x4_t vb = vld1q_f32(b + i);
        float32x4_t vc = vaddq_f32(va, vb);
        vst1q_f32(out + i, vc);
    }
#elif defined(__AVX2__)
    for (; i + 8 <= len; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        __m256 vc = _mm256_add_ps(va, vb);
        _mm256_storeu_ps(out + i, vc);
    }
#endif
    
    for (; i < len; i++) {
        out[i] = a[i] + b[i];
    }
}

/* ─────────────────────────────────────────────────────────────────────────────
 * Softmax — Numerically Stable Implementation
 * ───────────────────────────────────────────────────────────────────────────── */

void vir_simd_softmax_f32(const float* input, float* output, int64_t len) {
    // Find max for numerical stability
    float max_val = input[0];
    for (int64_t i = 1; i < len; i++) {
        if (input[i] > max_val) max_val = input[i];
    }
    
    // Compute exp(x - max) and sum
    float sum = 0.0f;
    for (int64_t i = 0; i < len; i++) {
        output[i] = expf(input[i] - max_val);
        sum += output[i];
    }
    
    // Normalize
    float inv_sum = 1.0f / sum;
    int64_t i = 0;
    
#ifdef __ARM_NEON__
    float32x4_t vinv = vdupq_n_f32(inv_sum);
    for (; i + 4 <= len; i += 4) {
        float32x4_t v = vld1q_f32(output + i);
        v = vmulq_f32(v, vinv);
        vst1q_f32(output + i, v);
    }
#endif
    
    for (; i < len; i++) {
        output[i] *= inv_sum;
    }
}

/* ─────────────────────────────────────────────────────────────────────────────
 * L2 Norm — SIMD Optimized
 * ───────────────────────────────────────────────────────────────────────────── */

float vir_simd_l2_norm_f32(const float* data, int64_t len) {
    float sum_sq = vir_simd_dot_f32(data, data, len);
    return sqrtf(sum_sq);
}

/* ─────────────────────────────────────────────────────────────────────────────
 * Cosine Similarity — SIMD Optimized  
 * ───────────────────────────────────────────────────────────────────────────── */

float vir_simd_cosine_similarity_f32(const float* a, const float* b, int64_t len) {
    float dot = vir_simd_dot_f32(a, b, len);
    float norm_a = vir_simd_l2_norm_f32(a, len);
    float norm_b = vir_simd_l2_norm_f32(b, len);
    
    if (norm_a < 1e-8f || norm_b < 1e-8f) {
        return 0.0f;
    }
    
    return dot / (norm_a * norm_b);
}
