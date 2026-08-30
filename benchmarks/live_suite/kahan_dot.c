#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

int64_t run_kahan_dot(int n) {
    int64_t *a = (int64_t *)malloc(n * sizeof(int64_t));
    int64_t *b = (int64_t *)malloc(n * sizeof(int64_t));

    for (int i = 0; i < n; i++) {
        a[i] = (i % 100) + 1;
        b[i] = (i % 50) + 1;
    }

    int64_t sum = 0;
    int64_t comp = 0;
    for (int j = 0; j < n; j++) {
        int64_t term = a[j] * b[j];
        int64_t y = term - comp;
        int64_t t = sum + y;
        comp = (t - sum) - y;
        sum = t;
    }

    free(a); free(b);
    return sum;
}

int main(void) {
    int64_t res = 0;
    for (int iter = 0; iter < 5; iter++) {
        res = run_kahan_dot(1000000);
    }
    printf("Kahan Dot Sum: %lld\n", (long long)res);
    return 0;
}
