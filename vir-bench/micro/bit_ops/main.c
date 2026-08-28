// Microbenchmark: bit_ops (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

static inline uint64_t rotl64(uint64_t x, int k) {
    return (x << k) | (x >> (64 - k));
}

int64_t bench_bit_ops(int64_t n) {
    uint64_t s = 0x123456789ABCDEF0ULL;
    for (int64_t i = 0; i < n; i++) {
        s = rotl64(s, 7) ^ (s >> 11);
        s += 0x9E3779B97F4A7C15ULL;
        s = (s & 0xAAAAAAAAAAAAAAAAULL) | ((s ^ (uint64_t)i) & 0x5555555555555555ULL);
    }
    return (int64_t)s;
}

int main(int argc, char** argv) {
    int64_t n = 20000000;
    int64_t res = bench_bit_ops(n);
    printf("checksum=%lld\n", (long long)res);
    return 0;
}
