#include <stdio.h>
#include <stdint.h>

uint64_t fib(uint64_t n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

int main(void) {
    uint64_t res = fib(40);
    printf("Result: %llu\n", (unsigned long long)res);
    return 0;
}
