/*
 * huge_alloc.h – Huge-Page Memory Allocator
 * ============================================
 * Uses OS-level huge/super pages for large allocations:
 *   Linux:  mmap(MAP_HUGETLB)   – 2 MB / 1 GB
 *   macOS:  VM_FLAGS_SUPERPAGE_SIZE_2MB (arm64/x86_64)
 *   Windows: VirtualAlloc(MEM_LARGE_PAGES)
 *
 * Transparently falls back to regular mmap when huge pages
 * are unavailable or allocation is too small.
 */

#ifndef VIR_HUGE_ALLOC_H
#define VIR_HUGE_ALLOC_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "cpu_caps.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Huge-Page Info
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    bool     supported;        /* OS supports huge pages             */
    size_t   page_size;        /* Huge page size (bytes), e.g. 2MB  */
    size_t   min_alloc;        /* Min size to trigger huge alloc     */
} huge_page_info_t;

/* Query OS for huge page availability.
 * Reads from cpu_caps if provided (may be NULL). */
int huge_page_query(huge_page_info_t *info, const cpu_caps_t *caps);

/* ═══════════════════════════════════════════════════════
 * Allocation / Free
 * ═══════════════════════════════════════════════════════ */

/* Allocate with huge pages if size >= threshold.
 * Falls back to regular mmap on failure.
 * Returns NULL on total failure. */
void *huge_alloc(size_t size);

/* Allocate with explicit huge page request (no fallback). */
void *huge_alloc_strict(size_t size);

/* Free memory from huge_alloc / huge_alloc_strict.
 * Caller must provide the original size. */
void huge_free(void *ptr, size_t size);

/* ═══════════════════════════════════════════════════════
 * Statistics
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint64_t huge_allocs;      /* Number of huge-page allocations   */
    uint64_t fallback_allocs;  /* Allocations that fell back        */
    uint64_t total_huge_bytes; /* Total bytes via huge pages        */
    uint64_t total_fallback_bytes;
} huge_alloc_stats_t;

void huge_alloc_get_stats(huge_alloc_stats_t *stats);
void huge_alloc_reset_stats(void);

#ifdef __cplusplus
}
#endif

#endif /* VIR_HUGE_ALLOC_H */
