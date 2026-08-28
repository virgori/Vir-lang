// Algorithm Benchmark: fnv1a_hash (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define FNV_PRIME 0x100000001B3ULL
#define FNV_OFFSET 0xCBF29CE484222325ULL

int64_t fnv1a_64(const uint8_t* data, size_t len) {
    int64_t hash = (int64_t)FNV_OFFSET;
    for (size_t i = 0; i < len; i++) {
        hash ^= data[i];
        hash *= (int64_t)FNV_PRIME;
    }
    return hash;
}

int main() {
    size_t sz = 10 * 1024 * 1024; // 10 MB
    uint8_t* buf = (uint8_t*)malloc(sz);
    for (size_t i = 0; i < sz; i++) {
        buf[i] = (uint8_t)((i * 37) & 0xFF);
    }
    
    int64_t final_hash = 0;
    for (int rep = 0; rep < 5; rep++) {
        final_hash = fnv1a_64(buf, sz);
    }
    free(buf);
    printf("checksum=%lld\n", (long long)final_hash);
    return 0;
}
