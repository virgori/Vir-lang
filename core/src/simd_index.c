/*
 * simd_index.c – SIMD Structural Character Indexer
 * ==================================================
 * Multi-ISA implementation:
 *   - ARM64 NEON: 16-byte vectorized compare
 *   - x86-64 AVX2: 32-byte vectorized compare
 *   - Scalar fallback: lookup table
 *
 * Classifies JSON/CSV structural characters in bulk:
 *   { } [ ] : , "
 */

#include "simd_index.h"

#include <stdlib.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * Structural Character Lookup Table
 * ═══════════════════════════════════════════════════════ */

static const uint8_t STRUCTURAL_LUT[256] = {
    /* Initialize all to 0, then set structural chars to 1 */
    ['{'] = 1, ['}'] = 1,
    ['['] = 1, [']'] = 1,
    [':'] = 1, [','] = 1,
    ['"'] = 1,
};

int vir_sindex_is_structural(uint8_t byte) {
    return STRUCTURAL_LUT[byte];
}

/* ═══════════════════════════════════════════════════════
 * Bitmap Management
 * ═══════════════════════════════════════════════════════ */

int vir_sindex_init(vir_structural_bitmap_t *bm, size_t n_bytes) {
    bm->n_bytes  = n_bytes;
    bm->n_blocks = (n_bytes + 63) / 64;
    bm->blocks   = calloc(bm->n_blocks, sizeof(uint64_t));
    return bm->blocks ? 0 : -1;
}

void vir_sindex_free(vir_structural_bitmap_t *bm) {
    free(bm->blocks);
    bm->blocks   = NULL;
    bm->n_blocks = 0;
    bm->n_bytes  = 0;
}

static inline void bm_set(vir_structural_bitmap_t *bm, size_t pos) {
    bm->blocks[pos >> 6] |= (1ULL << (pos & 63));
}

size_t vir_sindex_next(const vir_structural_bitmap_t *bm, size_t *pos) {
    size_t block_idx = *pos >> 6;
    size_t bit_idx   = *pos & 63;

    while (block_idx < bm->n_blocks) {
        /* Mask off bits below current position within the block */
        uint64_t word = bm->blocks[block_idx] >> bit_idx;
        if (word) {
            int tz = __builtin_ctzll(word);
            size_t result = (block_idx << 6) + bit_idx + (size_t)tz;
            if (result >= bm->n_bytes)
                return (size_t)-1;
            *pos = result + 1;
            return result;
        }
        block_idx++;
        bit_idx = 0;
    }
    return (size_t)-1;
}

/* ═══════════════════════════════════════════════════════
 * Scalar Implementation
 * ═══════════════════════════════════════════════════════ */

static size_t scan_scalar(vir_structural_bitmap_t *bm,
                          const uint8_t *data, size_t len) {
    size_t count = 0;
    for (size_t i = 0; i < len; i++) {
        if (STRUCTURAL_LUT[data[i]]) {
            bm_set(bm, i);
            count++;
        }
    }
    return count;
}

/* ═══════════════════════════════════════════════════════
 * ARM64 NEON Implementation
 * ═══════════════════════════════════════════════════════ */

#if defined(__aarch64__)
#include <arm_neon.h>

static size_t scan_neon(vir_structural_bitmap_t *bm,
                        const uint8_t *data, size_t len) {
    size_t count = 0;

    /* Load structural character constants */
    const uint8x16_t v_brace_l = vdupq_n_u8('{');
    const uint8x16_t v_brace_r = vdupq_n_u8('}');
    const uint8x16_t v_brack_l = vdupq_n_u8('[');
    const uint8x16_t v_brack_r = vdupq_n_u8(']');
    const uint8x16_t v_colon   = vdupq_n_u8(':');
    const uint8x16_t v_comma   = vdupq_n_u8(',');
    const uint8x16_t v_quote   = vdupq_n_u8('"');

    size_t i = 0;
    for (; i + 16 <= len; i += 16) {
        uint8x16_t chunk = vld1q_u8(data + i);

        /* Compare against each structural char */
        uint8x16_t m = vceqq_u8(chunk, v_brace_l);
        m = vorrq_u8(m, vceqq_u8(chunk, v_brace_r));
        m = vorrq_u8(m, vceqq_u8(chunk, v_brack_l));
        m = vorrq_u8(m, vceqq_u8(chunk, v_brack_r));
        m = vorrq_u8(m, vceqq_u8(chunk, v_colon));
        m = vorrq_u8(m, vceqq_u8(chunk, v_comma));
        m = vorrq_u8(m, vceqq_u8(chunk, v_quote));

        /* Extract mask — narrow to per-byte bits */
        /* NEON doesn't have movemask; use shift + reduce */
        static const uint8_t bit_sel[16] = {
            1,2,4,8,16,32,64,128, 1,2,4,8,16,32,64,128
        };
        uint8x16_t bits = vld1q_u8(bit_sel);
        uint8x16_t masked = vandq_u8(m, bits);

        /* Reduce each 8-byte half to a byte mask */
        uint8x8_t lo = vget_low_u8(masked);
        uint8x8_t hi = vget_high_u8(masked);

        /* Horizontal OR within each half */
        uint8_t mask_lo = lo[0] | lo[1] | lo[2] | lo[3] |
                          lo[4] | lo[5] | lo[6] | lo[7];
        uint8_t mask_hi = hi[0] | hi[1] | hi[2] | hi[3] |
                          hi[4] | hi[5] | hi[6] | hi[7];

        /* Set bits in bitmap from mask */
        /* Actually use per-lane approach for correctness */
        uint8_t lane_vals[16];
        vst1q_u8(lane_vals, m);
        for (int j = 0; j < 16; j++) {
            if (lane_vals[j]) {
                bm_set(bm, i + (size_t)j);
                count++;
            }
        }
        (void)mask_lo;
        (void)mask_hi;
    }

    /* Scalar tail */
    for (; i < len; i++) {
        if (STRUCTURAL_LUT[data[i]]) {
            bm_set(bm, i);
            count++;
        }
    }
    return count;
}

#endif /* __aarch64__ */

/* ═══════════════════════════════════════════════════════
 * x86-64 AVX2 Implementation
 * ═══════════════════════════════════════════════════════ */

#if defined(__x86_64__) && defined(__AVX2__)
#include <immintrin.h>

static size_t scan_avx2(vir_structural_bitmap_t *bm,
                        const uint8_t *data, size_t len) {
    size_t count = 0;

    const __m256i v_brace_l = _mm256_set1_epi8('{');
    const __m256i v_brace_r = _mm256_set1_epi8('}');
    const __m256i v_brack_l = _mm256_set1_epi8('[');
    const __m256i v_brack_r = _mm256_set1_epi8(']');
    const __m256i v_colon   = _mm256_set1_epi8(':');
    const __m256i v_comma   = _mm256_set1_epi8(',');
    const __m256i v_quote   = _mm256_set1_epi8('"');

    size_t i = 0;
    for (; i + 32 <= len; i += 32) {
        __m256i chunk = _mm256_loadu_si256((const __m256i *)(data + i));

        __m256i m = _mm256_cmpeq_epi8(chunk, v_brace_l);
        m = _mm256_or_si256(m, _mm256_cmpeq_epi8(chunk, v_brace_r));
        m = _mm256_or_si256(m, _mm256_cmpeq_epi8(chunk, v_brack_l));
        m = _mm256_or_si256(m, _mm256_cmpeq_epi8(chunk, v_brack_r));
        m = _mm256_or_si256(m, _mm256_cmpeq_epi8(chunk, v_colon));
        m = _mm256_or_si256(m, _mm256_cmpeq_epi8(chunk, v_comma));
        m = _mm256_or_si256(m, _mm256_cmpeq_epi8(chunk, v_quote));

        uint32_t mask = (uint32_t)_mm256_movemask_epi8(m);
        while (mask) {
            int bit = __builtin_ctz(mask);
            bm_set(bm, i + (size_t)bit);
            count++;
            mask &= mask - 1;  /* clear lowest set bit */
        }
    }

    /* Scalar tail */
    for (; i < len; i++) {
        if (STRUCTURAL_LUT[data[i]]) {
            bm_set(bm, i);
            count++;
        }
    }
    return count;
}

#endif /* __x86_64__ && __AVX2__ */

/* ═══════════════════════════════════════════════════════
 * Dispatch
 * ═══════════════════════════════════════════════════════ */

size_t vir_sindex_scan(vir_structural_bitmap_t *bm,
                       const uint8_t *data, size_t len) {
    if (!bm || !data || len == 0) return 0;

    /* Clear bitmap */
    memset(bm->blocks, 0, bm->n_blocks * sizeof(uint64_t));

#if defined(__x86_64__) && defined(__AVX2__)
    return scan_avx2(bm, data, len);
#elif defined(__aarch64__)
    return scan_neon(bm, data, len);
#else
    return scan_scalar(bm, data, len);
#endif
}
