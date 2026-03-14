/*
 * slab_alloc.h – Native Media Slab Allocator
 * =============================================
 * Size-class slab pools for fast O(1) alloc/free of
 * fixed-size objects (tensors, buffers, activations):
 *
 *   Class 0:  64 KB slabs   (small tensors, feature maps)
 *   Class 1:  1  MB slabs   (weight matrices, embeddings)
 *   Class 2:  8  MB slabs   (large activations, KV-cache)
 *   Class 3:  64 MB slabs   (model shards)
 *
 * Each class is a stack of mmap-backed slabs with
 * bitmap free-lists for O(1) allocation.
 */

#ifndef VIR_SLAB_ALLOC_H
#define VIR_SLAB_ALLOC_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Slab Size Classes
 * ═══════════════════════════════════════════════════════ */

#define SLAB_NUM_CLASSES    4
#define SLAB_CLASS_64K      0
#define SLAB_CLASS_1M       1
#define SLAB_CLASS_8M       2
#define SLAB_CLASS_64M      3

/* Max slabs per class (free-stack capacity) */
#define SLAB_MAX_FREE       256

/* ═══════════════════════════════════════════════════════
 * Slab Header (prepended to each mmap region)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint32_t class_idx;       /* Which size class         */
    uint32_t ref_count;       /* Active allocations       */
    size_t   region_size;     /* Total mmap size (bytes)  */
} slab_header_t;

/* ═══════════════════════════════════════════════════════
 * Slab Pool (one per size class)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    size_t   slab_size;                     /* Bytes per slab       */
    void    *free_stack[SLAB_MAX_FREE];     /* Free slab pointers   */
    uint32_t free_count;                    /* Stack top index      */
    uint64_t alloc_count;                   /* Total allocations    */
    uint64_t free_count_total;              /* Total frees          */
    uint64_t total_bytes;                   /* Bytes outstanding    */
} slab_pool_t;

/* ═══════════════════════════════════════════════════════
 * Global Slab Allocator
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    slab_pool_t pools[SLAB_NUM_CLASSES];
    bool        initialised;
} slab_allocator_t;

/* Initialise global slab allocator.
 * Safe to call multiple times (idempotent). */
int slab_init(void);

/* Allocate a buffer of at least `size` bytes.
 * Picks the smallest size class that fits.
 * Falls back to raw mmap for oversized requests. */
void *slab_alloc(size_t size);

/* Return buffer to pool for reuse.
 * Caller must provide original size for class lookup. */
void slab_free(void *ptr, size_t size);

/* Release all cached slabs back to OS.
 * Outstanding allocations are NOT affected. */
void slab_drain(void);

/* ═══════════════════════════════════════════════════════
 * Statistics
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint64_t allocs_per_class[SLAB_NUM_CLASSES];
    uint64_t frees_per_class[SLAB_NUM_CLASSES];
    uint64_t cached_per_class[SLAB_NUM_CLASSES];
    uint64_t oversize_allocs;
    uint64_t oversize_bytes;
} slab_stats_t;

void slab_get_stats(slab_stats_t *stats);

#ifdef __cplusplus
}
#endif

#endif /* VIR_SLAB_ALLOC_H */
