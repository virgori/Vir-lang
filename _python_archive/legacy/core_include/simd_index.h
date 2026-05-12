/*
 * simd_index.h – SIMD Structural Character Indexer
 * ==================================================
 * simdjson-inspired byte-level structural classifier.
 * Identifies JSON/CSV structural characters at 2.5-4 GB/s
 * using NEON (ARM64), AVX2 (x86-64), or scalar fallback.
 *
 * The indexer scans a byte buffer and builds a bitmap of
 * structural character positions ({, }, [, ], :, ,, ") that
 * can then be used for zero-copy parsing.
 */

#ifndef VIR_SIMD_INDEX_H
#define VIR_SIMD_INDEX_H

#include <stddef.h>
#include <stdint.h>

/* ═══════════════════════════════════════════════════════
 * Types
 * ═══════════════════════════════════════════════════════ */

/* Structural bitmap: bit N set → byte N is structural */
typedef struct {
    uint64_t *blocks;    /* Bitmap blocks (1 bit per input byte) */
    size_t    n_blocks;  /* Number of 64-bit blocks               */
    size_t    n_bytes;   /* Total input bytes indexed             */
} vir_structural_bitmap_t;

/* ═══════════════════════════════════════════════════════
 * API
 * ═══════════════════════════════════════════════════════ */

/* Initialize a bitmap for `n_bytes` of input.
 * Returns 0 on success, -1 on alloc failure. */
int  vir_sindex_init(vir_structural_bitmap_t *bm, size_t n_bytes);

/* Free bitmap memory. */
void vir_sindex_free(vir_structural_bitmap_t *bm);

/* Scan input buffer and populate structural bitmap.
 * Detects: { } [ ] : , "
 * Uses NEON/AVX2 when available, falls back to scalar.
 * Returns number of structural characters found. */
size_t vir_sindex_scan(vir_structural_bitmap_t *bm,
                       const uint8_t *data, size_t len);

/* Iterate structural positions from the bitmap.
 * Call with *pos = 0; returns next structural position,
 * or (size_t)-1 when exhausted. */
size_t vir_sindex_next(const vir_structural_bitmap_t *bm, size_t *pos);

/* Get the classification of a byte (for convenience). */
int vir_sindex_is_structural(uint8_t byte);

#endif /* VIR_SIMD_INDEX_H */
