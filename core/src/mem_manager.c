/*
 * mem_manager.c – Memory Manager for Vir Runtime
 * =================================================
 * Phase 3 – H2: Deterministic memory management.
 *
 * Provides:
 *   - Arena allocator for function-scoped allocations
 *   - Reference counting for heap objects
 *   - Explicit free() with double-free detection
 *   - Memory pool (slab) for fixed-size objects
 *   - Stats tracking (allocs, frees, bytes)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

/* ═══════════════════════════════════════════════════════
 * Constants
 * ═══════════════════════════════════════════════════════ */

#define VIR_ARENA_DEFAULT_SIZE    (64 * 1024)   /* 64 KB */
#define VIR_MAX_ARENAS            64
#define VIR_REFCOUNT_MAGIC        0xABCD1234
#define VIR_MAX_POOLS             16
#define VIR_POOL_BLOCK_SIZE       4096

/* ═══════════════════════════════════════════════════════
 * Arena Allocator
 * ═══════════════════════════════════════════════════════ */

typedef struct vir_arena {
    uint8_t     *base;
    size_t       capacity;
    size_t       offset;
    int          id;
} vir_arena_t;

static vir_arena_t g_arenas[VIR_MAX_ARENAS];
static int g_arena_count = 0;

int vir_arena_create(size_t size) {
    if (g_arena_count >= VIR_MAX_ARENAS) return -1;
    if (size == 0) size = VIR_ARENA_DEFAULT_SIZE;

    int id = g_arena_count;
    g_arenas[id].base = (uint8_t *)malloc(size);
    if (!g_arenas[id].base) return -1;
    g_arenas[id].capacity = size;
    g_arenas[id].offset   = 0;
    g_arenas[id].id       = id;
    g_arena_count++;
    return id;
}

void *vir_arena_alloc(int arena_id, size_t size) {
    if (arena_id < 0 || arena_id >= g_arena_count) return NULL;
    vir_arena_t *a = &g_arenas[arena_id];

    /* Align to 8 bytes */
    size = (size + 7) & ~(size_t)7;
    if (a->offset + size > a->capacity) return NULL;

    void *ptr = a->base + a->offset;
    a->offset += size;
    return ptr;
}

void vir_arena_reset(int arena_id) {
    if (arena_id < 0 || arena_id >= g_arena_count) return;
    g_arenas[arena_id].offset = 0;
}

void vir_arena_destroy(int arena_id) {
    if (arena_id < 0 || arena_id >= g_arena_count) return;
    free(g_arenas[arena_id].base);
    g_arenas[arena_id].base     = NULL;
    g_arenas[arena_id].capacity = 0;
    g_arenas[arena_id].offset   = 0;
}

size_t vir_arena_used(int arena_id) {
    if (arena_id < 0 || arena_id >= g_arena_count) return 0;
    return g_arenas[arena_id].offset;
}

/* ═══════════════════════════════════════════════════════
 * Reference Counting
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint32_t     magic;
    int32_t      refcount;
    size_t       size;
    /* user data follows immediately */
} vir_rc_header_t;

static struct {
    size_t  total_allocs;
    size_t  total_frees;
    size_t  bytes_allocated;
    size_t  bytes_freed;
    size_t  current_objects;
} g_mem_stats;

void *vir_rc_alloc(size_t size) {
    vir_rc_header_t *hdr = (vir_rc_header_t *)malloc(
        sizeof(vir_rc_header_t) + size);
    if (!hdr) return NULL;
    hdr->magic    = VIR_REFCOUNT_MAGIC;
    hdr->refcount = 1;
    hdr->size     = size;
    g_mem_stats.total_allocs++;
    g_mem_stats.bytes_allocated += size;
    g_mem_stats.current_objects++;
    return (void *)(hdr + 1);  /* Return pointer past header */
}

static vir_rc_header_t *get_header(void *ptr) {
    return ((vir_rc_header_t *)ptr) - 1;
}

int vir_rc_retain(void *ptr) {
    if (!ptr) return -1;
    vir_rc_header_t *hdr = get_header(ptr);
    if (hdr->magic != VIR_REFCOUNT_MAGIC) {
        fprintf(stderr, "vir_rc_retain: invalid pointer (corrupt magic)\n");
        return -1;
    }
    hdr->refcount++;
    return hdr->refcount;
}

int vir_rc_release(void *ptr) {
    if (!ptr) return -1;
    vir_rc_header_t *hdr = get_header(ptr);
    if (hdr->magic != VIR_REFCOUNT_MAGIC) {
        fprintf(stderr, "vir_rc_release: invalid pointer (corrupt magic)\n");
        return -1;
    }
    if (hdr->refcount <= 0) {
        fprintf(stderr, "vir_rc_release: double free detected!\n");
        return -1;
    }
    hdr->refcount--;
    if (hdr->refcount == 0) {
        g_mem_stats.total_frees++;
        g_mem_stats.bytes_freed += hdr->size;
        g_mem_stats.current_objects--;
        hdr->magic = 0;  /* Poison */
        free(hdr);
        return 0;
    }
    return hdr->refcount;
}

int vir_rc_count(void *ptr) {
    if (!ptr) return 0;
    vir_rc_header_t *hdr = get_header(ptr);
    if (hdr->magic != VIR_REFCOUNT_MAGIC) return -1;
    return hdr->refcount;
}

/* ═══════════════════════════════════════════════════════
 * Explicit Free with Safety
 * ═══════════════════════════════════════════════════════ */

void vir_free(void *ptr) {
    if (!ptr) return;
    /* Check if it's a refcounted object first */
    vir_rc_header_t *hdr = get_header(ptr);
    if (hdr->magic == VIR_REFCOUNT_MAGIC) {
        vir_rc_release(ptr);
    } else {
        /* Plain free */
        free(ptr);
    }
}

/* ═══════════════════════════════════════════════════════
 * Memory Pool (Fixed-Size Slab)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint8_t *base;
    size_t   elem_size;
    size_t   capacity;       /* Max elements */
    size_t   count;          /* Currently allocated */
    uint8_t *free_list;      /* Intrusive free list */
    int      active;
} vir_pool_t;

static vir_pool_t g_pools[VIR_MAX_POOLS];
static int g_pool_count = 0;

int vir_pool_create(size_t elem_size, size_t count) {
    if (g_pool_count >= VIR_MAX_POOLS) return -1;
    if (elem_size < sizeof(void *)) elem_size = sizeof(void *);
    /* Align elem_size to 8 */
    elem_size = (elem_size + 7) & ~(size_t)7;

    int id = g_pool_count;
    vir_pool_t *pool = &g_pools[id];
    pool->base = (uint8_t *)malloc(elem_size * count);
    if (!pool->base) return -1;
    pool->elem_size = elem_size;
    pool->capacity  = count;
    pool->count     = 0;
    pool->active    = 1;

    /* Build free list */
    pool->free_list = pool->base;
    for (size_t i = 0; i < count - 1; i++) {
        uint8_t *curr = pool->base + i * elem_size;
        uint8_t *next = curr + elem_size;
        *(uint8_t **)curr = next;
    }
    /* Last element points to NULL */
    *(uint8_t **)(pool->base + (count - 1) * elem_size) = NULL;

    g_pool_count++;
    return id;
}

void *vir_pool_alloc(int pool_id) {
    if (pool_id < 0 || pool_id >= g_pool_count) return NULL;
    vir_pool_t *pool = &g_pools[pool_id];
    if (!pool->active || !pool->free_list) return NULL;

    void *ptr = pool->free_list;
    pool->free_list = *(uint8_t **)ptr;
    pool->count++;
    return ptr;
}

void vir_pool_free(int pool_id, void *ptr) {
    if (pool_id < 0 || pool_id >= g_pool_count || !ptr) return;
    vir_pool_t *pool = &g_pools[pool_id];
    if (!pool->active) return;

    *(uint8_t **)ptr = pool->free_list;
    pool->free_list  = (uint8_t *)ptr;
    pool->count--;
}

void vir_pool_destroy(int pool_id) {
    if (pool_id < 0 || pool_id >= g_pool_count) return;
    free(g_pools[pool_id].base);
    g_pools[pool_id].active = 0;
}

/* ═══════════════════════════════════════════════════════
 * Stats
 * ═══════════════════════════════════════════════════════ */

void vir_mem_stats_print(void) {
    printf("=== Vir Memory Stats ===\n");
    printf("  Allocs:     %zu\n", g_mem_stats.total_allocs);
    printf("  Frees:      %zu\n", g_mem_stats.total_frees);
    printf("  Bytes in:   %zu\n", g_mem_stats.bytes_allocated);
    printf("  Bytes out:  %zu\n", g_mem_stats.bytes_freed);
    printf("  Live objects: %zu\n", g_mem_stats.current_objects);
    printf("  Arenas:     %d\n", g_arena_count);
    printf("  Pools:      %d\n", g_pool_count);
}

size_t vir_mem_live_objects(void)  { return g_mem_stats.current_objects; }
size_t vir_mem_total_allocs(void)  { return g_mem_stats.total_allocs; }
size_t vir_mem_total_frees(void)   { return g_mem_stats.total_frees; }
