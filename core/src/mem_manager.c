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
#define VIR_MAX_ARENAS            256
#define VIR_MAX_TL_DEPTH          32
#define VIR_MAX_TL_POOL           64
#define VIR_REFCOUNT_MAGIC        0xABCD1234
#define VIR_MAX_POOLS             16
#define VIR_POOL_BLOCK_SIZE       4096

/* ═══════════════════════════════════════════════════════
 * Arena v2 — page chain + watermark + child (§4.6 / PLAN/07)
 * ═══════════════════════════════════════════════════════ */

typedef struct arena_page {
    uint8_t           *base;
    size_t             capacity;
    size_t             offset;
    struct arena_page *next;
} arena_page_t;

typedef struct vir_arena {
    arena_page_t *pages;       /* head (first page) */
    arena_page_t *current;     /* active bump page */
    size_t        page_size;   /* default page for overflow */
    size_t        used;        /* total bytes handed out */
    size_t        alignment;   /* default alloc alignment */
    double        growth;      /* overflow page growth (≥1) */
    int           id;
    int           parent_id;   /* -1 = root */
    int           alive;
} vir_arena_t;

static vir_arena_t g_arenas[VIR_MAX_ARENAS];
static int g_arena_count = 0;

static arena_page_t *arena_page_new(size_t capacity) {
    arena_page_t *p = (arena_page_t *)malloc(sizeof(arena_page_t));
    if (!p) return NULL;
    p->base = (uint8_t *)malloc(capacity);
    if (!p->base) {
        free(p);
        return NULL;
    }
    p->capacity = capacity;
    p->offset = 0;
    p->next = NULL;
    return p;
}

static void arena_pages_free_from(arena_page_t *p) {
    while (p) {
        arena_page_t *n = p->next;
        free(p->base);
        free(p);
        p = n;
    }
}

static vir_arena_t *arena_get(int arena_id) {
    if (arena_id < 0 || arena_id >= g_arena_count) return NULL;
    if (!g_arenas[arena_id].alive) return NULL;
    return &g_arenas[arena_id];
}

static size_t arena_align_up(size_t n, size_t align) {
    if (align < 1) align = 1;
    return (n + align - 1) & ~(align - 1);
}

static int arena_init_slot(int id, size_t size, int parent_id) {
    if (size == 0) size = VIR_ARENA_DEFAULT_SIZE;
    arena_page_t *page = arena_page_new(size);
    if (!page) return -1;
    vir_arena_t *a = &g_arenas[id];
    memset(a, 0, sizeof(*a));
    a->pages = page;
    a->current = page;
    a->page_size = size;
    a->used = 0;
    a->alignment = 8;
    a->growth = 1.0;
    a->id = id;
    a->parent_id = parent_id;
    a->alive = 1;
    return id;
}

int vir_arena_create(size_t size) {
    if (g_arena_count >= VIR_MAX_ARENAS) return -1;
    int id = g_arena_count;
    if (arena_init_slot(id, size, -1) < 0) return -1;
    g_arena_count++;
    return id;
}

int vir_arena_create_child(int parent_id, size_t size) {
    if (!arena_get(parent_id)) return -1;
    if (g_arena_count >= VIR_MAX_ARENAS) return -1;
    int id = g_arena_count;
    if (arena_init_slot(id, size, parent_id) < 0) return -1;
    g_arena_count++;
    return id;
}

static void *arena_alloc_raw(vir_arena_t *a, size_t size, size_t align) {
    if (!a || size == 0) return NULL;
    size_t need = arena_align_up(size, align);

    /* Fit in current page? */
    if (a->current &&
        a->current->offset + need <= a->current->capacity) {
        void *ptr = a->current->base + a->current->offset;
        a->current->offset += need;
        a->used += need;
        return ptr;
    }

    /* New page: at least `need`, else page_size (optionally grown). */
    size_t next_cap = a->page_size;
    if (a->growth > 1.0) {
        double g = (double)a->page_size * a->growth;
        if (g > (double)next_cap)
            next_cap = (size_t)g;
    }
    if (need > next_cap) next_cap = need;

    arena_page_t *np = arena_page_new(next_cap);
    if (!np) return NULL;
    if (a->growth > 1.0)
        a->page_size = next_cap;

    if (!a->pages) {
        a->pages = np;
    } else {
        arena_page_t *tail = a->pages;
        while (tail->next) tail = tail->next;
        tail->next = np;
    }
    a->current = np;
    void *ptr = np->base;
    np->offset = need;
    a->used += need;
    return ptr;
}

void *vir_arena_alloc(int arena_id, size_t size) {
    vir_arena_t *a = arena_get(arena_id);
    if (!a) return NULL;
    return arena_alloc_raw(a, size, a->alignment);
}

void *vir_arena_alloc_aligned(int arena_id, size_t size, size_t align) {
    vir_arena_t *a = arena_get(arena_id);
    if (!a) return NULL;
    if (align < 1) align = 1;
    /* Align the bump pointer itself before the object. */
    if (a->current) {
        size_t pad = arena_align_up(a->current->offset, align) - a->current->offset;
        if (pad > 0) {
            if (a->current->offset + pad <= a->current->capacity) {
                a->current->offset += pad;
                a->used += pad;
            } else {
                /* Force new page so object can be naturally aligned at base. */
                a->current->offset = a->current->capacity;
            }
        }
    }
    return arena_alloc_raw(a, size, align);
}

void vir_arena_reset(int arena_id) {
    vir_arena_t *a = arena_get(arena_id);
    if (!a || !a->pages) return;
    /* Keep first page; free overflow chain. */
    arena_pages_free_from(a->pages->next);
    a->pages->next = NULL;
    a->pages->offset = 0;
    a->current = a->pages;
    a->used = 0;
}

void vir_arena_destroy(int arena_id) {
    vir_arena_t *a = arena_get(arena_id);
    if (!a) return;
    arena_pages_free_from(a->pages);
    a->pages = NULL;
    a->current = NULL;
    a->used = 0;
    a->alive = 0;
}

size_t vir_arena_used(int arena_id) {
    vir_arena_t *a = arena_get(arena_id);
    return a ? a->used : 0;
}

size_t vir_arena_page_count(int arena_id) {
    vir_arena_t *a = arena_get(arena_id);
    if (!a) return 0;
    size_t n = 0;
    for (arena_page_t *p = a->pages; p; p = p->next) n++;
    return n;
}

size_t vir_arena_save(int arena_id) {
    vir_arena_t *a = arena_get(arena_id);
    return a ? a->used : 0;
}

void vir_arena_restore(int arena_id, size_t watermark) {
    vir_arena_t *a = arena_get(arena_id);
    if (!a || !a->pages) return;
    if (watermark > a->used) watermark = a->used;

    size_t seen = 0;
    arena_page_t *p = a->pages;
    while (p) {
        if (seen + p->offset >= watermark) {
            p->offset = watermark - seen;
            arena_page_t *drop = p->next;
            p->next = NULL;
            arena_pages_free_from(drop);
            a->current = p;
            a->used = watermark;
            return;
        }
        seen += p->offset;
        p = p->next;
    }
    a->used = watermark;
}

void vir_arena_set_alignment(int arena_id, size_t align) {
    vir_arena_t *a = arena_get(arena_id);
    if (!a) return;
    if (align < 1) align = 1;
    a->alignment = align;
}

void vir_arena_set_growth_factor(int arena_id, double factor) {
    vir_arena_t *a = arena_get(arena_id);
    if (!a) return;
    if (factor < 1.0) factor = 1.0;
    a->growth = factor;
}

/* ── Thread-local arena stack + pool ──────────────────── */

static _Thread_local int g_tl_stack[VIR_MAX_TL_DEPTH];
static _Thread_local int g_tl_sp = 0; /* 0 = empty; top at sp-1 */
static _Thread_local int g_tl_current = -1;

static int g_tl_pool[VIR_MAX_TL_POOL];
static size_t g_tl_pool_n = 0;
static int g_tl_pool_inited = 0;

void vir_tl_arena_pool_init(void) {
    g_tl_pool_inited = 1;
    g_tl_pool_n = 0;
}

int vir_tl_arena_get(void) {
    if (g_tl_current >= 0 && arena_get(g_tl_current))
        return g_tl_current;
    if (g_tl_pool_n > 0) {
        int id = g_tl_pool[--g_tl_pool_n];
        vir_arena_reset(id);
        g_tl_current = id;
        return id;
    }
    int id = vir_arena_create(VIR_ARENA_DEFAULT_SIZE);
    g_tl_current = id;
    return id;
}

void *vir_tl_arena_alloc(size_t size) {
    int id = vir_tl_arena_get();
    if (id < 0) return NULL;
    return vir_arena_alloc(id, size);
}

void vir_tl_arena_release(void) {
    if (g_tl_current < 0) return;
    if (g_tl_pool_n < VIR_MAX_TL_POOL) {
        vir_arena_reset(g_tl_current);
        g_tl_pool[g_tl_pool_n++] = g_tl_current;
    } else {
        vir_arena_destroy(g_tl_current);
    }
    g_tl_current = -1;
}

size_t vir_tl_arena_pool_size(void) { return g_tl_pool_n; }

void vir_tl_arena_pool_drain(void) {
    for (size_t i = 0; i < g_tl_pool_n; i++)
        vir_arena_destroy(g_tl_pool[i]);
    g_tl_pool_n = 0;
    g_tl_current = -1;
    g_tl_sp = 0;
}

int vir_tl_arena_push(int arena_id) {
    if (!arena_get(arena_id)) return -1;
    if (g_tl_sp >= VIR_MAX_TL_DEPTH) return -1;
    g_tl_stack[g_tl_sp++] = g_tl_current;
    g_tl_current = arena_id;
    return 0;
}

int vir_tl_arena_pop(void) {
    if (g_tl_sp <= 0) {
        g_tl_current = -1;
        return -1;
    }
    g_tl_current = g_tl_stack[--g_tl_sp];
    return g_tl_current;
}

int vir_tl_arena_current(void) { return g_tl_current; }

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
