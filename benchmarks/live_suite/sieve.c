#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int run_sieve(int limit) {
    char *is_prime = (char *)malloc(limit + 1);
    memset(is_prime, 1, limit + 1);
    is_prime[0] = 0;
    is_prime[1] = 0;

    for (int p = 2; p * p <= limit; p++) {
        if (is_prime[p]) {
            for (int k = p * p; k <= limit; k += p) {
                is_prime[k] = 0;
            }
        }
    }

    int count = 0;
    for (int c = 0; c <= limit; c++) {
        if (is_prime[c]) count++;
    }
    free(is_prime);
    return count;
}

int main(void) {
    int total_primes = 0;
    for (int iter = 0; iter < 10; iter++) {
        total_primes = run_sieve(1000000);
    }
    printf("Primes count: %d\n", total_primes);
    return 0;
}
