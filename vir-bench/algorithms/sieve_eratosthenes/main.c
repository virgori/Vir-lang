// Algorithm Benchmark: sieve_eratosthenes (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

uint64_t bench_sieve(uint64_t limit) {
    uint8_t* is_prime = (uint8_t*)malloc(limit + 1);
    memset(is_prime, 1, limit + 1);
    is_prime[0] = 0;
    is_prime[1] = 0;
    
    for (uint64_t p = 2; p * p <= limit; p++) {
        if (is_prime[p]) {
            for (uint64_t i = p * p; i <= limit; i += p) {
                is_prime[i] = 0;
            }
        }
    }
    
    uint64_t count = 0;
    for (uint64_t i = 2; i <= limit; i++) {
        if (is_prime[i]) count++;
    }
    free(is_prime);
    return count;
}

int main(int argc, char** argv) {
    uint64_t limit = 1000000;
    uint64_t reps = 20;
    uint64_t last_count = 0;
    for (uint64_t r = 0; r < reps; r++) {
        last_count = bench_sieve(limit);
    }
    printf("checksum=%llu\n", (unsigned long long)last_count);
    return 0;
}
