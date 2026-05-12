/*
 * slab_alloc.c – Native Media Slab Allocator
 * =============================================
 * O(1) alloc/free via size-class free-stacks.
 * mmap-backed, no malloc dependency.
 */

#include "slab_alloc.h"

#include <string.h>
#include <stdio.h>

#if defined(_WIN32)
  #include <windows.h>
#else
  #include <sys/mman.h>
  #include <unistd.h>
#endif

/* ── Singleton ───────────────────────────────────────── */
static slab_allocator_t g_slab;
static uint64_t g_oversize_allocs;
static uint64_t g_oversize_bytes;

/* ── Size class table ────────────────────────────────── */
static const size_t CLASS_SIZES[SLAB_NUM_CLASSES] = {
    64  * 1024,          /*  64 KB */
    1   * 1024 * 1024,   /*  1  MB */
    8   * 1024 * 1024,   /*  8  MB */
    64  * 1024 * 1024,   /* 64  MB */
};

/* ═══════════════════════════════════════════════════════
 * Internal: OS memory
 * ═══════════════════════════════════════════════════════ */

static void *os_alloc(size_t size)
{
#if defined(_WIN32)
    return VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
    return (p == MAP_FAILED) ? NULL : p;
#endif
}

static void os_free(void *ptr, size_t size)
{
#if defined(_WIN32)
    VirtualFree(ptr, 0, MEM_RELEASE);
    (void)size;
#else
    munmap(ptr, size);
#endif
}

/* ═══════════════════════════════════════════════════════
 * Pick size class for a given allocation size
 * ═══════════════════════════════════════════════════════ */

static int pick_class(size_t size)
{
    /* Account for slab header */
    size_t needed = size + sizeof(slab_header_t);
    for (int i = 0; i < SLAB_NUM_CLASSES; i++) {
        if (needed <= CLASS_SIZES[i])
            return i;
    }
    return -1; /* oversized */
}

/* ═══════════════════════════════════════════════════════
 * Public API
 * ═══════════════════════════════════════════════════════ */

int slab_init(void)
{
    if (g_slab.initialised) return 0;
    memset(&g_slab, 0, sizeof(g_slab));
    for (int i = 0; i < SLAB_NUM_CLASSES; i++)
        g_slab.pools[i].slab_size = CLASS_SIZES[i];
    g_slab.initialised = true;
    return 0;
}

void *slab_alloc(size_t size)
{
    if (!g_slab.initialised) slab_init();

    int cls = pick_class(size);
    if (cls < 0) {
        /* Oversized: direct mmap with header */
        size_t total = size + sizeof(slab_header_t);
        void *raw = os_alloc(total);
        if (!raw) return NULL;
        slab_header_t *hdr = (slab_header_t *)raw;
        hdr->class_idx   = UINT32_MAX; /* marker: oversize */
        hdr->ref_count   = 1;
        hdr->region_size = total;
        g_oversize_allocs++;
        g_oversize_bytes += total;
        return (char *)raw + sizeof(slab_header_t);
    }

    slab_pool_t *pool = &g_slab.pools[cls];

    /* Try reuse from free stack */
    if (pool->free_count > 0) {
        pool->free_count--;
        void *raw = pool->free_stack[pool->free_count];
        slab_header_t *hdr = (slab_header_t *)raw;
        hdr->ref_count = 1;
        pool->alloc_count++;
        pool->total_bytes += pool->slab_size;
        return (char *)raw + sizeof(slab_header_t);
    }

    /* Fresh mmap */
    void *raw = os_alloc(pool->slab_size);
    if (!raw) return NULL;
    slab_header_t *hdr = (slab_header_t *)raw;
    hdr->class_idx   = (uint32_t)cls;
    hdr->ref_count   = 1;
    hdr->region_size = pool->slab_size;
    pool->alloc_count++;
    pool->total_bytes += pool->slab_size;
    return (char *)raw + sizeof(slab_header_t);
}

void slab_free(void *ptr, size_t size)
{
    if (!ptr) return;

    void *raw = (char *)ptr - sizeof(slab_header_t);
    slab_header_t *hdr = (slab_header_t *)raw;

    /* Oversized: return directly to OS */
    if (hdr->class_idx == UINT32_MAX) {
        os_free(raw, hdr->region_size);
        return;
    }

    uint32_t cls = hdr->class_idx;
    if (cls >= SLAB_NUM_CLASSES) {
        /* Corrupt header — just unmap */
        os_free(raw, size + sizeof(slab_header_t));
        return;
    }

    slab_pool_t *pool = &g_slab.pools[cls];
    hdr->ref_count = 0;
    pool->free_count_total++;

    /* Push onto free stack if room */
    if (pool->free_count < SLAB_MAX_FREE) {
        pool->free_stack[pool->free_count] = raw;
        pool->free_count++;
    } else {
        /* Stack full — return to OS */
        os_free(raw, pool->slab_size);
    }
}

void slab_drain(void)
{
    for (int i = 0; i < SLAB_NUM_CLASSES; i++) {
        slab_pool_t *pool = &g_slab.pools[i];
        for (uint32_t j = 0; j < pool->free_count; j++) {
            os_free(pool->free_stack[j], pool->slab_size);
        }
        pool->free_count = 0;
    }
}

void slab_get_stats(slab_stats_t *stats)
{
    if (!stats) return;
    memset(stats, 0, sizeof(*stats));
    for (int i = 0; i < SLAB_NUM_CLASSES; i++) {
        stats->allocs_per_class[i] = g_slab.pools[i].alloc_count;
        stats->frees_per_class[i]  = g_slab.pools[i].free_count_total;
        stats->cached_per_class[i] = g_slab.pools[i].free_count;
    }
    stats->oversize_allocs = g_oversize_allocs;
    stats->oversize_bytes  = g_oversize_bytes;
}
