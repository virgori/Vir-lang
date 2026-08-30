// Microbenchmark: bit_ops (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

static inline uint32_t rotl32(uint32_t x, int k) {
    return (x << k) | (x >> (32 - k));
}

int64_t bench_bit_ops(int64_t n) {
    uint32_t s = 0x12345678;
    for (int64_t i = 0; i < n; i++) {
        s = rotl32(s, 7) ^ (s >> 11);
        s = (s + 0x9E3779B9) & 0xFFFFFFFF;
        s = (s & 0xAAAAAAAA) | ((s ^ (uint32_t)i) & 0x55555555);
    }
    return (int64_t)s;
}

int main(int argc, char** argv) {
    int64_t n = 20000000;
    int64_t res = bench_bit_ops(n);
    printf("checksum=%lld\n", (long long)res);
    return 0;
}
