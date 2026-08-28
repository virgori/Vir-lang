// Microbenchmark: loop_sum (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

uint64_t bench_loop_sum(uint64_t n) {
    uint64_t s = 0;
    for (uint64_t i = 0; i < n; i++) {
        s += (i & 0xFFF);
    }
    return s;
}

int main(int argc, char** argv) {
    uint64_t n = 50000000; // 50 million iterations
    if (argc > 1) {
        n = strtoull(argv[1], NULL, 10);
    }
    uint64_t res = bench_loop_sum(n);
    printf("checksum=%llu\n", (unsigned long long)res);
    return 0;
}
