/*
 * vm_heap.c — Dynamic per-VM allocation registry
 */
#include "vm_heap.h"

#include <stdlib.h>
#include <string.h>

#define VM_HEAP_INIT_CAP 256u
#define VM_HEAP_INIT_BUCKETS 512u
#define VM_HEAP_RANGE_INIT_BUCKETS 1024u
#define VM_HEAP_RANGE_PAGE_SHIFT 12u

static uint32_t vm_heap_hash_ptr(const void *ptr)
{
    uintptr_t x = (uintptr_t)ptr;
    x >>= 4; /* allocations are at least naturally aligned */
    x ^= x >> 16;
    x *= UINT64_C(0x45d9f3b);
    x ^= x >> 16;
    return (uint32_t)x;
}

static uint32_t vm_heap_hash_page(uintptr_t page)
{
    uint64_t x = (uint64_t)page;
    x ^= x >> 30;
    x *= UINT64_C(0xbf58476d1ce4e5b9);
    x ^= x >> 27;
    x *= UINT64_C(0x94d049bb133111eb);
    x ^= x >> 31;
    return (uint32_t)x;
}

static int vm_heap_range_rehash(vm_heap_t *heap, uint32_t new_cap)
{
    uint32_t *buckets = (uint32_t *)calloc(new_cap, sizeof(*buckets));
    if (!buckets)
        return -1;
    for (uint32_t i = 0; i < heap->range_count; i++) {
        vm_heap_range_node_t *node = &heap->range_nodes[i];
        if (!node->entry)
            continue;
        uint32_t bucket = vm_heap_hash_page(node->page) & (new_cap - 1u);
        node->bucket_next = buckets[bucket];
        buckets[bucket] = i + 1u;
    }
    free(heap->range_buckets);
    heap->range_buckets = buckets;
    heap->range_bucket_cap = new_cap;
    return 0;
}

static int vm_heap_range_reserve_node(vm_heap_t *heap)
{
    if (heap->range_free_head || heap->range_count < heap->range_cap)
        return 0;
    uint32_t new_cap = heap->range_cap ? heap->range_cap * 2u : 512u;
    vm_heap_range_node_t *nodes = (vm_heap_range_node_t *)realloc(
        heap->range_nodes, (size_t)new_cap * sizeof(*nodes));
    if (!nodes)
        return -1;
    memset(nodes + heap->range_cap, 0,
           (size_t)(new_cap - heap->range_cap) * sizeof(*nodes));
    heap->range_nodes = nodes;
    heap->range_cap = new_cap;
    return 0;
}

static int vm_heap_range_add_entry(vm_heap_t *heap, uint32_t entry_index)
{
    vm_heap_entry_t *entry = &heap->entries[entry_index];
    uintptr_t begin = (uintptr_t)entry->ptr;
    if (!entry->ptr || entry->size == 0 || entry->size - 1u > SIZE_MAX - begin)
        return -1;
    uintptr_t first = begin >> VM_HEAP_RANGE_PAGE_SHIFT;
    uintptr_t last = (begin + entry->size - 1u) >> VM_HEAP_RANGE_PAGE_SHIFT;

    if (!heap->range_bucket_cap &&
        vm_heap_range_rehash(heap, VM_HEAP_RANGE_INIT_BUCKETS) != 0)
        return -1;

    for (uintptr_t page = first;; page++) {
        if (heap->range_live_count + 1u >
            (heap->range_bucket_cap * 3u) / 4u) {
            if (vm_heap_range_rehash(heap, heap->range_bucket_cap * 2u) != 0)
                return -1;
        }
        if (vm_heap_range_reserve_node(heap) != 0)
            return -1;

        uint32_t index;
        if (heap->range_free_head) {
            index = heap->range_free_head - 1u;
            heap->range_free_head = heap->range_nodes[index].free_next;
        } else {
            index = heap->range_count++;
        }
        vm_heap_range_node_t *node = &heap->range_nodes[index];
        memset(node, 0, sizeof(*node));
        node->page = page;
        node->entry = entry_index + 1u;
        node->entry_next = entry->range_head;
        entry->range_head = index + 1u;
        uint32_t bucket = vm_heap_hash_page(page) &
                          (heap->range_bucket_cap - 1u);
        node->bucket_next = heap->range_buckets[bucket];
        heap->range_buckets[bucket] = index + 1u;
        heap->range_live_count++;
        if (page == last)
            break;
    }
    return 0;
}

static void vm_heap_range_remove_entry(vm_heap_t *heap, uint32_t entry_index)
{
    vm_heap_entry_t *entry = &heap->entries[entry_index];
    uint32_t head = entry->range_head;
    entry->range_head = 0;
    while (head) {
        uint32_t index = head - 1u;
        vm_heap_range_node_t *node = &heap->range_nodes[index];
        head = node->entry_next;
        if (node->entry && heap->range_bucket_cap) {
            uint32_t bucket = vm_heap_hash_page(node->page) &
                              (heap->range_bucket_cap - 1u);
            uint32_t *link = &heap->range_buckets[bucket];
            while (*link && *link != index + 1u)
                link = &heap->range_nodes[*link - 1u].bucket_next;
            if (*link == index + 1u)
                *link = node->bucket_next;
        }
        memset(node, 0, sizeof(*node));
        node->free_next = heap->range_free_head;
        heap->range_free_head = index + 1u;
        if (heap->range_live_count > 0)
            heap->range_live_count--;
    }
}

static int vm_heap_rehash(vm_heap_t *heap, uint32_t new_cap)
{
    uint32_t *buckets = (uint32_t *)calloc(new_cap, sizeof(*buckets));
    if (!buckets)
        return -1;
    for (uint32_t i = 0; i < heap->count; i++) {
        vm_heap_entry_t *e = &heap->entries[i];
        if (!e->live)
            continue;
        uint32_t bucket = vm_heap_hash_ptr(e->ptr) & (new_cap - 1u);
        e->next = buckets[bucket];
        buckets[bucket] = i + 1u;
    }
    free(heap->buckets);
    heap->buckets = buckets;
    heap->bucket_cap = new_cap;
    return 0;
}

static int vm_heap_grow(vm_heap_t *heap)
{
    uint32_t new_cap = heap->cap ? heap->cap * 2u : VM_HEAP_INIT_CAP;
    vm_heap_entry_t *nb =
        (vm_heap_entry_t *)realloc(heap->entries,
                                   (size_t)new_cap * sizeof(vm_heap_entry_t));
    if (!nb)
        return -1;
    heap->entries = nb;
    heap->cap = new_cap;
    return 0;
}

static vm_heap_entry_t *vm_heap_find(vm_heap_t *heap, const void *ptr)
{
    if (!heap || !ptr || !heap->bucket_cap)
        return NULL;
    uint32_t head = heap->buckets[vm_heap_hash_ptr(ptr) &
                                  (heap->bucket_cap - 1u)];
    while (head) {
        vm_heap_entry_t *e = &heap->entries[head - 1u];
        if (e->live && e->ptr == ptr)
            return e;
        head = e->next;
    }
    return NULL;
}

void vm_heap_init(vm_heap_t *heap)
{
    if (!heap)
        return;
    memset(heap, 0, sizeof(*heap));
}

void vm_heap_destroy(vm_heap_t *heap)
{
    if (!heap)
        return;
    for (uint32_t i = 0; i < heap->count; i++) {
        if (heap->entries[i].live && heap->entries[i].ptr)
            free(heap->entries[i].ptr);
    }
    free(heap->entries);
    free(heap->buckets);
    free(heap->range_nodes);
    free(heap->range_buckets);
    memset(heap, 0, sizeof(*heap));
}

void *vm_heap_alloc(vm_heap_t *heap, size_t size)
{
    if (!heap)
        return NULL;
    size_t alloc_sz = size > 0 ? size : 1u;
    void *p = calloc(1, alloc_sz);
    if (!p)
        return NULL;
    if (vm_heap_register(heap, p, alloc_sz, VM_HEAP_KIND_GENERIC) != 0) {
        free(p);
        return NULL;
    }
    return p;
}

int vm_heap_register(vm_heap_t *heap, void *ptr, size_t size, vm_heap_kind_t kind)
{
    if (!heap || !ptr)
        return -1;
    if (vm_heap_find(heap, ptr))
        return 0; /* already tracked */

    if (!heap->bucket_cap) {
        if (vm_heap_rehash(heap, VM_HEAP_INIT_BUCKETS) != 0)
            return -1;
    } else if (heap->live_count + 1u > (heap->bucket_cap * 3u) / 4u) {
        if (vm_heap_rehash(heap, heap->bucket_cap * 2u) != 0)
            return -1;
    }

    uint32_t index;
    if (heap->free_head) {
        index = heap->free_head - 1u;
        heap->free_head = heap->entries[index].free_next;
    } else {
        if (heap->count >= heap->cap && vm_heap_grow(heap) != 0)
            return -1;
        index = heap->count++;
    }
    vm_heap_entry_t *e = &heap->entries[index];
    memset(e, 0, sizeof(*e));
    e->ptr = ptr;
    e->size = size;
    e->live = 1;
    e->kind = (uint8_t)kind;
    uint32_t bucket = vm_heap_hash_ptr(ptr) & (heap->bucket_cap - 1u);
    e->next = heap->buckets[bucket];
    heap->buckets[bucket] = index + 1u;
    heap->live_count++;
    if (vm_heap_range_add_entry(heap, index) != 0)
        heap->range_degraded = 1;
    return 0;
}

int vm_heap_rebind(vm_heap_t *heap, void *old_ptr, void *new_ptr, size_t new_size)
{
    if (!heap || !old_ptr || !new_ptr)
        return -1;
    vm_heap_entry_t *e = vm_heap_find(heap, old_ptr);
    if (!e)
        return vm_heap_register(heap, new_ptr, new_size, VM_HEAP_KIND_GENERIC);
    uint32_t index = (uint32_t)(e - heap->entries);
    vm_heap_range_remove_entry(heap, index);
    e->ptr = new_ptr;
    e->size = new_size;
    (void)vm_heap_rehash(heap, heap->bucket_cap);
    if (vm_heap_range_add_entry(heap, index) != 0)
        heap->range_degraded = 1;
    return 0;
}

int vm_heap_free(vm_heap_t *heap, void *ptr)
{
    if (!heap || !ptr)
        return -1;
    vm_heap_entry_t *e = vm_heap_find(heap, ptr);
    if (!e)
        return -1;
    uint32_t index = (uint32_t)(e - heap->entries);
    vm_heap_range_remove_entry(heap, index);
    uint32_t bucket = vm_heap_hash_ptr(ptr) & (heap->bucket_cap - 1u);
    uint32_t *link = &heap->buckets[bucket];
    while (*link && *link != index + 1u)
        link = &heap->entries[*link - 1u].next;
    if (*link == index + 1u)
        *link = e->next;
    free(e->ptr);
    e->ptr = NULL;
    e->size = 0;
    e->live = 0;
    e->next = 0;
    e->range_head = 0;
    e->free_next = heap->free_head;
    heap->free_head = index + 1u;
    if (heap->live_count > 0)
        heap->live_count--;
    return 0;
}

void *vm_heap_realloc(vm_heap_t *heap, void *ptr, size_t new_size)
{
    if (!heap)
        return NULL;
    if (!ptr)
        return vm_heap_alloc(heap, new_size);
    if (new_size == 0) {
        vm_heap_free(heap, ptr);
        return NULL;
    }
    vm_heap_entry_t *e = vm_heap_find(heap, ptr);
    /* Q_REALLOC is valid only for memory allocated by this VM heap.
     * In particular, Vir's mmap runtime allocator has a distinct ABI. */
    if (!e)
        return NULL;
    size_t old_size = e->size;
    uint32_t index = (uint32_t)(e - heap->entries);
    vm_heap_range_remove_entry(heap, index);
    void *np = realloc(ptr, new_size);
    if (!np) {
        if (vm_heap_range_add_entry(heap, index) != 0)
            heap->range_degraded = 1;
        return NULL;
    }
    e->ptr = np;
    e->size = new_size;
    (void)vm_heap_rehash(heap, heap->bucket_cap);
    if (vm_heap_range_add_entry(heap, index) != 0)
        heap->range_degraded = 1;
    if (new_size > old_size)
        memset((uint8_t *)np + old_size, 0, new_size - old_size);
    return np;
}

int vm_heap_owns_live(const vm_heap_t *heap, const void *ptr)
{
    return vm_heap_find((vm_heap_t *)heap, ptr) != NULL;
}

int vm_heap_contains(const vm_heap_t *heap, const void *ptr, size_t size)
{
    if (!heap || !ptr)
        return 0;
    uintptr_t addr = (uintptr_t)ptr;
    if (size > SIZE_MAX - addr)
        return 0;
    uintptr_t end = addr + size;

    /* Native shims overwhelmingly receive the allocation base (entity,
     * Vec backing buffer, fat string).  Resolve that common case through
     * the pointer hash instead of scanning every live token/entity. */
    vm_heap_entry_t *exact = vm_heap_find((vm_heap_t *)heap, ptr);
    if (exact) {
        uintptr_t begin = (uintptr_t)exact->ptr;
        if (exact->size <= SIZE_MAX - begin && end <= begin + exact->size)
            return 1;
    }

    /* Interior pointers use the allocation-page index.  A bucket contains
     * only allocations overlapping this 4-KiB page, rather than every live
     * token/entity in the VM. */
    if (heap->range_bucket_cap) {
        uintptr_t page = addr >> VM_HEAP_RANGE_PAGE_SHIFT;
        uint32_t head = heap->range_buckets[
            vm_heap_hash_page(page) & (heap->range_bucket_cap - 1u)];
        while (head) {
            const vm_heap_range_node_t *node = &heap->range_nodes[head - 1u];
            if (node->page == page && node->entry) {
                const vm_heap_entry_t *e = &heap->entries[node->entry - 1u];
                if (e->live && e->ptr) {
                    uintptr_t begin = (uintptr_t)e->ptr;
                    if (e->size <= SIZE_MAX - begin && addr >= begin &&
                        end <= begin + e->size)
                        return 1;
                }
            }
            head = node->bucket_next;
        }
    }

    /* Preserve correctness if range-index allocation ever failed. */
    if (heap->range_degraded) {
        for (uint32_t i = 0; i < heap->count; i++) {
            const vm_heap_entry_t *e = &heap->entries[i];
            if (!e->live || !e->ptr)
                continue;
            uintptr_t begin = (uintptr_t)e->ptr;
            if (e->size <= SIZE_MAX - begin && addr >= begin &&
                end <= begin + e->size)
                return 1;
        }
    }
    return 0;
}

size_t vm_heap_size_of(const vm_heap_t *heap, const void *ptr)
{
    vm_heap_entry_t *e = vm_heap_find((vm_heap_t *)heap, ptr);
    return e ? e->size : 0;
}

uint32_t vm_heap_live_count(const vm_heap_t *heap)
{
    return heap ? heap->live_count : 0;
}
