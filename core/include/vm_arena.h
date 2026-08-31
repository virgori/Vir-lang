/*
 * vm_arena.h — Per-VM bump arena (§4.5–4.7)
 *
 * Language objects (string, array, entity, dict) allocate from the current
 * TL arena via Q_ALLOC.  Pages are mmap-backed; watermark save/restore
 * implements scope batch-free.  FFI pointers use vm_heap (Q_HEAP_ALLOC).
 */
#ifndef VIR_VM_ARENA_H
#define VIR_VM_ARENA_H

#include <stddef.h>
#include <stdint.h>

typedef struct vm_state vm_state_t;

#define VM_ARENA_DEFAULT_SIZE   (64 * 1024)
#define VM_ARENA_MAX_ARENAS     256
#define VM_ARENA_MAX_TL_DEPTH   32
#define VM_ARENA_ALIGNMENT      16u

typedef struct vm_arena_page {
    uint8_t                *base;
    size_t                  capacity;
    size_t                  mapping_size;
    size_t                  offset;
    struct vm_arena_page   *next;
} vm_arena_page_t;

typedef struct vm_arena {
    vm_arena_page_t *pages;
    vm_arena_page_t *current;
    size_t           page_size;
    size_t           used;
    size_t           alignment;
    double           growth;
    int              id;
    int              parent_id;
    int              alive;
} vm_arena_t;

typedef struct vm_arena_ctx {
    vm_arena_t  arenas[VM_ARENA_MAX_ARENAS];
    int         arena_count;
    int         tl_stack[VM_ARENA_MAX_TL_DEPTH];
    int         tl_sp;
    int         tl_current;
} vm_arena_ctx_t;

void   vm_arena_ctx_init(vm_arena_ctx_t *ctx);
void   vm_arena_ctx_destroy(vm_arena_ctx_t *ctx);

int    vm_arena_create_in(vm_arena_ctx_t *ctx, size_t size);
int    vm_arena_create_child_in(vm_arena_ctx_t *ctx, int parent_id, size_t size);
void  *vm_arena_alloc_in(vm_arena_ctx_t *ctx, int arena_id, size_t size);
void   vm_arena_destroy_in(vm_arena_ctx_t *ctx, int arena_id);
size_t vm_arena_save_in(vm_arena_ctx_t *ctx, int arena_id);
void   vm_arena_restore_in(vm_arena_ctx_t *ctx, int arena_id, size_t watermark);
int    vm_arena_owner_in(const vm_arena_ctx_t *ctx, const void *ptr,
                         size_t size);
int    vm_arena_contains_after_in(const vm_arena_ctx_t *ctx, int arena_id,
                                  const void *ptr, size_t size,
                                  size_t watermark);
int    vm_arena_promote_in(vm_arena_ctx_t *ctx, int child_id,
                           int parent_id);

int    vm_arena_tl_get_in(vm_arena_ctx_t *ctx);
void  *vm_arena_tl_alloc_in(vm_arena_ctx_t *ctx, size_t size);
int    vm_arena_tl_push_in(vm_arena_ctx_t *ctx, int arena_id);
int    vm_arena_tl_pop_in(vm_arena_ctx_t *ctx);

/* Provenance check for guarded native memory shims. */
int    vm_arena_contains_in(const vm_arena_ctx_t *ctx, const void *ptr,
                            size_t size);

#endif /* VIR_VM_ARENA_H */
