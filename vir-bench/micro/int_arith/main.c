// Microbenchmark: int_arith (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

int64_t bench_int_arith(int64_t n) {
    int64_t x = 123456789;
    for (int64_t i = 0; i < n; i++) {
        x = ((x * 13) + 7) ^ (x >> 3);
        x = (x + (i * 3)) % 1000000007;
    }
    return x;
}

int main(int argc, char** argv) {
    int64_t n = 30000000;
    int64_t res = bench_int_arith(n);
    printf("checksum=%lld\n", (long long)res);
    return 0;
}
