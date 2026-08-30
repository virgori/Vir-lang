// Algorithm Benchmark: fnv1a_hash (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

uint32_t fnv1a_32(const uint8_t* data, size_t len) {
    uint32_t hash = 2166136261U;
    for (size_t i = 0; i < len; i++) {
        hash ^= data[i];
        hash *= 16777619U;
    }
    return hash;
}

int main() {
    size_t sz = 10 * 1024 * 1024; // 10 MB
    uint8_t* buf = (uint8_t*)malloc(sz);
    for (size_t i = 0; i < sz; i++) {
        buf[i] = (uint8_t)((i * 37) & 0xFF);
    }
    
    uint32_t final_hash = 0;
    for (int rep = 0; rep < 5; rep++) {
        final_hash = fnv1a_32(buf, sz);
    }
    free(buf);
    printf("checksum=%llu\n", (unsigned long long)final_hash);
    return 0;
}
