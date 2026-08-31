/*
 * vm_arena.c — Per-VM arena allocator
 */
#include "vm_arena.h"

#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

/* Arena payload and its small page descriptor share one anonymous mapping.
 * This keeps the C-VM on the same mmap/munmap backing model as alloc.vri. */
static size_t arena_os_page_size(void)
{
    long n = sysconf(_SC_PAGESIZE);
    return n > 0 ? (size_t)n : 4096u;
}

static size_t arena_round_page(size_t n)
{
    size_t page = arena_os_page_size();
    if (n > SIZE_MAX - (page - 1u))
        return 0;
    return (n + page - 1u) & ~(page - 1u);
}

static vm_arena_t *arena_get(vm_arena_ctx_t *ctx, int arena_id)
{
    if (!ctx || arena_id < 0 || arena_id >= ctx->arena_count)
        return NULL;
    if (!ctx->arenas[arena_id].alive)
        return NULL;
    return &ctx->arenas[arena_id];
}

static size_t arena_align_up(size_t n, size_t align)
{
    if (align < 1)
        align = 1;
    return (n + align - 1) & ~(align - 1);
}

static vm_arena_page_t *arena_page_new(size_t capacity)
{
    const size_t header = arena_align_up(sizeof(vm_arena_page_t), 16u);
    if (capacity > SIZE_MAX - header)
        return NULL;
    size_t mapping_size = arena_round_page(header + capacity);
    if (mapping_size == 0)
        return NULL;
    void *mapping = mmap(NULL, mapping_size, PROT_READ | PROT_WRITE,
                         MAP_PRIVATE | MAP_ANON, -1, 0);
    if (mapping == MAP_FAILED)
        return NULL;
    vm_arena_page_t *p = (vm_arena_page_t *)mapping;
    memset(p, 0, sizeof(*p));
    p->base = (uint8_t *)mapping + header;
    p->capacity = mapping_size - header;
    p->mapping_size = mapping_size;
    p->offset = 0;
    p->next = NULL;
    return p;
}

static void arena_pages_free_from(vm_arena_page_t *p)
{
    while (p) {
        vm_arena_page_t *n = p->next;
        munmap(p, p->mapping_size);
        p = n;
    }
}

static int arena_init_slot(vm_arena_ctx_t *ctx, int id, size_t size, int parent_id)
{
    if (size == 0)
        size = VM_ARENA_DEFAULT_SIZE;
    vm_arena_page_t *page = arena_page_new(size);
    if (!page)
        return -1;
    vm_arena_t *a = &ctx->arenas[id];
    memset(a, 0, sizeof(*a));
    a->pages = page;
    a->current = page;
    a->page_size = size;
    a->used = 0;
    a->alignment = VM_ARENA_ALIGNMENT;
    a->growth = 1.0;
    a->id = id;
    a->parent_id = parent_id;
    a->alive = 1;
    return id;
}

static void *arena_alloc_raw(vm_arena_t *a, size_t size, size_t align)
{
    if (!a || size == 0)
        return NULL;
    size_t need = arena_align_up(size, align);

    if (a->current && a->current->offset + need <= a->current->capacity) {
        void *ptr = a->current->base + a->current->offset;
        a->current->offset += need;
        a->used += need;
        return ptr;
    }

    size_t next_cap = a->page_size;
    if (a->growth > 1.0) {
        double g = (double)a->page_size * a->growth;
        if (g > (double)next_cap)
            next_cap = (size_t)g;
    }
    if (need > next_cap)
        next_cap = need;

    vm_arena_page_t *np = arena_page_new(next_cap);
    if (!np)
        return NULL;
    if (a->growth > 1.0)
        a->page_size = next_cap;

    if (!a->pages) {
        a->pages = np;
    } else if (a->current) {
        a->current->next = np;
    } else {
        vm_arena_page_t *tail = a->pages;
        while (tail->next)
            tail = tail->next;
        tail->next = np;
    }
    a->current = np;
    void *ptr = np->base;
    np->offset = need;
    a->used += need;
    return ptr;
}

void vm_arena_ctx_init(vm_arena_ctx_t *ctx)
{
    if (!ctx)
        return;
    memset(ctx, 0, sizeof(*ctx));
    if (arena_init_slot(ctx, 0, VM_ARENA_DEFAULT_SIZE, -1) < 0)
        return;
    ctx->arena_count = 1;
    ctx->tl_current = 0;
    ctx->tl_sp = 0;
}

void vm_arena_ctx_destroy(vm_arena_ctx_t *ctx)
{
    if (!ctx)
        return;
    for (int i = 0; i < ctx->arena_count; i++) {
        if (!ctx->arenas[i].alive)
            continue;
        arena_pages_free_from(ctx->arenas[i].pages);
        ctx->arenas[i].pages = NULL;
        ctx->arenas[i].current = NULL;
        ctx->arenas[i].alive = 0;
    }
    ctx->arena_count = 0;
    ctx->tl_current = -1;
    ctx->tl_sp = 0;
}

int vm_arena_create_in(vm_arena_ctx_t *ctx, size_t size)
{
    if (!ctx)
        return -1;
    int id = -1;
    for (int i = 1; i < ctx->arena_count; i++) {
        if (!ctx->arenas[i].alive) {
            id = i;
            break;
        }
    }
    if (id < 0) {
        if (ctx->arena_count >= VM_ARENA_MAX_ARENAS)
            return -1;
        id = ctx->arena_count++;
    }
    if (arena_init_slot(ctx, id, size, -1) < 0)
        return -1;
    return id;
}

int vm_arena_create_child_in(vm_arena_ctx_t *ctx, int parent_id, size_t size)
{
    if (!arena_get(ctx, parent_id))
        return -1;
    int id = vm_arena_create_in(ctx, size);
    if (id >= 0)
        ctx->arenas[id].parent_id = parent_id;
    return id;
}

void *vm_arena_alloc_in(vm_arena_ctx_t *ctx, int arena_id, size_t size)
{
    vm_arena_t *a = arena_get(ctx, arena_id);
    if (!a)
        return NULL;
    return arena_alloc_raw(a, size, a->alignment);
}

void vm_arena_destroy_in(vm_arena_ctx_t *ctx, int arena_id)
{
    vm_arena_t *a = arena_get(ctx, arena_id);
    if (!a)
        return;
    arena_pages_free_from(a->pages);
    a->pages = NULL;
    a->current = NULL;
    a->used = 0;
    a->alive = 0;
    if (ctx->tl_current == arena_id)
        ctx->tl_current = 0;
}

size_t vm_arena_save_in(vm_arena_ctx_t *ctx, int arena_id)
{
    vm_arena_t *a = arena_get(ctx, arena_id);
    return a ? a->used : 0;
}

void vm_arena_restore_in(vm_arena_ctx_t *ctx, int arena_id, size_t watermark)
{
    vm_arena_t *a = arena_get(ctx, arena_id);
    if (!a || !a->pages)
        return;
    if (watermark > a->used)
        watermark = a->used;

    size_t seen = 0;
    vm_arena_page_t *p = a->pages;
    while (p) {
        if (seen + p->offset >= watermark) {
            p->offset = watermark - seen;
            vm_arena_page_t *drop = p->next;
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

int vm_arena_tl_get_in(vm_arena_ctx_t *ctx)
{
    if (!ctx)
        return -1;
    if (ctx->tl_current >= 0 && arena_get(ctx, ctx->tl_current))
        return ctx->tl_current;
    if (ctx->arena_count <= 0)
        vm_arena_ctx_init(ctx);
    ctx->tl_current = 0;
    return ctx->tl_current;
}

void *vm_arena_tl_alloc_in(vm_arena_ctx_t *ctx, size_t size)
{
    int id = vm_arena_tl_get_in(ctx);
    if (id < 0)
        return NULL;
    return vm_arena_alloc_in(ctx, id, size);
}

int vm_arena_tl_push_in(vm_arena_ctx_t *ctx, int arena_id)
{
    if (!arena_get(ctx, arena_id))
        return -1;
    if (ctx->tl_sp >= VM_ARENA_MAX_TL_DEPTH)
        return -1;
    ctx->tl_stack[ctx->tl_sp++] = ctx->tl_current;
    ctx->tl_current = arena_id;
    return 0;
}

int vm_arena_tl_pop_in(vm_arena_ctx_t *ctx)
{
    if (!ctx || ctx->tl_sp <= 0) {
        if (ctx)
            ctx->tl_current = 0;
        return -1;
    }
    ctx->tl_current = ctx->tl_stack[--ctx->tl_sp];
    return ctx->tl_current;
}

int vm_arena_contains_in(const vm_arena_ctx_t *ctx, const void *ptr, size_t size)
{
    return vm_arena_owner_in(ctx, ptr, size) >= 0;
}

int vm_arena_owner_in(const vm_arena_ctx_t *ctx, const void *ptr, size_t size)
{
    if (!ctx || !ptr)
        return -1;
    uintptr_t p = (uintptr_t)ptr;
    if (size > SIZE_MAX - p)
        return -1;
    uintptr_t end = p + size;
    for (int i = 0; i < ctx->arena_count; i++) {
        const vm_arena_t *a = &ctx->arenas[i];
        if (!a->alive)
            continue;
        for (const vm_arena_page_t *page = a->pages; page; page = page->next) {
            uintptr_t begin = (uintptr_t)page->base;
            uintptr_t limit = begin + page->offset;
            if (p >= begin && end <= limit)
                return i;
        }
    }
    return -1;
}

int vm_arena_contains_after_in(const vm_arena_ctx_t *ctx, int arena_id,
                               const void *ptr, size_t size,
                               size_t watermark)
{
    if (!ctx || !ptr || arena_id < 0 || arena_id >= ctx->arena_count)
        return 0;
    const vm_arena_t *a = &ctx->arenas[arena_id];
    if (!a->alive || watermark > a->used)
        return 0;

    uintptr_t addr = (uintptr_t)ptr;
    if (size > SIZE_MAX - addr)
        return 0;
    uintptr_t end = addr + size;
    size_t seen = 0;
    for (const vm_arena_page_t *page = a->pages; page; page = page->next) {
        size_t page_end = seen + page->offset;
        if (page_end > watermark) {
            size_t local_wm = watermark > seen ? watermark - seen : 0;
            uintptr_t begin = (uintptr_t)page->base + local_wm;
            uintptr_t limit = (uintptr_t)page->base + page->offset;
            if (addr >= begin && end <= limit)
                return 1;
        }
        seen = page_end;
    }
    return 0;
}

int vm_arena_promote_in(vm_arena_ctx_t *ctx, int child_id, int parent_id)
{
    vm_arena_t *child = arena_get(ctx, child_id);
    vm_arena_t *parent = arena_get(ctx, parent_id);
    if (!child || !parent || child_id == parent_id)
        return -1;

    if (child->pages) {
        if (parent->current)
            parent->current->next = child->pages;
        else
            parent->pages = child->pages;
        parent->current = child->current;
        parent->used += child->used;
        if (child->page_size > parent->page_size)
            parent->page_size = child->page_size;
    }

    child->pages = NULL;
    child->current = NULL;
    child->used = 0;
    child->alive = 0;
    return 0;
}
