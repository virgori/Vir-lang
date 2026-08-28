// Allocator Benchmark: arena_linear (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t* buffer;
    size_t capacity;
    size_t offset;
} Arena;

void arena_init(Arena* a, size_t cap) {
    a->buffer = (uint8_t*)malloc(cap);
    a->capacity = cap;
    a->offset = 0;
}

void* arena_alloc(Arena* a, size_t size) {
    size = (size + 7) & ~7; // 8-byte align
    if (a->offset + size > a->capacity) {
        a->offset = 0; // reset for bench loop
    }
    void* ptr = a->buffer + a->offset;
    a->offset += size;
    return ptr;
}

void arena_free(Arena* a) {
    free(a->buffer);
}

int main() {
    Arena a;
    arena_init(&a, 64 * 1024 * 1024); // 64 MB arena
    
    uint64_t sum = 0;
    for (int rep = 0; rep < 5000000; rep++) {
        uint64_t* p = (uint64_t*)arena_alloc(&a, 64);
        *p = rep ^ 0xDEADBEEF;
        sum += *p;
    }
    
    arena_free(&a);
    printf("checksum=%llu\n", (unsigned long long)sum);
    return 0;
}
