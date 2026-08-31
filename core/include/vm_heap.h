/*
 * vm_heap.h — Per-VM FFI / escape-promoted heap registry (§4.5)
 *
 * Language objects (string, array, entity, dict) live in the current arena
 * (Q_ALLOC).  This registry tracks only:
 *   - Q_HEAP_ALLOC / vir_alloc / native malloc paths (FFI)
 *   - Values promoted to heap on function return (GlobalEscape)
 *
 * Q_FREE frees registered heap blocks; arena pointers are never freed here.
 */
#ifndef VIR_VM_HEAP_H
#define VIR_VM_HEAP_H

#include <stddef.h>
#include <stdint.h>

typedef struct vm_state vm_state_t;

typedef enum {
    VM_HEAP_KIND_GENERIC = 0,
    VM_HEAP_KIND_PROMOTED,
} vm_heap_kind_t;

typedef struct vm_heap_entry {
    void         *ptr;
    size_t        size;
    uint32_t      next;   /* bucket-chain index + 1; 0 is end */
    uint32_t      free_next; /* free-slot chain index + 1 */
    uint32_t      range_head; /* range-node chain index + 1 */
    uint8_t       live;
    uint8_t       kind;
} vm_heap_entry_t;

typedef struct vm_heap_range_node {
    uintptr_t page;
    uint32_t  entry;       /* heap entry index + 1 */
    uint32_t  bucket_next; /* range bucket chain index + 1 */
    uint32_t  entry_next;  /* per-entry chain index + 1 */
    uint32_t  free_next;   /* reusable node index + 1 */
} vm_heap_range_node_t;

typedef struct vm_heap {
    vm_heap_entry_t *entries;
    uint32_t         count;
    uint32_t         cap;
    uint32_t        *buckets;
    uint32_t         bucket_cap;
    uint32_t         free_head;  /* reusable entry index + 1 */
    uint32_t         live_count;
    /* Interior-pointer index. Each allocation is registered under every
     * 4-KiB address page it spans, so native field/data accesses avoid a
     * linear scan over all live heap objects. */
    vm_heap_range_node_t *range_nodes;
    uint32_t              range_count;
    uint32_t              range_cap;
    uint32_t             *range_buckets;
    uint32_t              range_bucket_cap;
    uint32_t              range_free_head;
    uint32_t              range_live_count;
    uint8_t               range_degraded;
} vm_heap_t;

void   vm_heap_init(vm_heap_t *heap);
void   vm_heap_destroy(vm_heap_t *heap);

void  *vm_heap_alloc(vm_heap_t *heap, size_t size);
int    vm_heap_register(vm_heap_t *heap, void *ptr, size_t size,
                        vm_heap_kind_t kind);
int    vm_heap_rebind(vm_heap_t *heap, void *old_ptr, void *new_ptr, size_t new_size);
int    vm_heap_free(vm_heap_t *heap, void *ptr);
void  *vm_heap_realloc(vm_heap_t *heap, void *ptr, size_t new_size);
int    vm_heap_owns_live(const vm_heap_t *heap, const void *ptr);
int    vm_heap_contains(const vm_heap_t *heap, const void *ptr, size_t size);
size_t vm_heap_size_of(const vm_heap_t *heap, const void *ptr);
uint32_t vm_heap_live_count(const vm_heap_t *heap);

#endif /* VIR_VM_HEAP_H */
