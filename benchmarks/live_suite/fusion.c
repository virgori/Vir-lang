#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

int64_t run_fusion(int n) {
    int64_t *a = (int64_t *)malloc(n * sizeof(int64_t));
    int64_t *b = (int64_t *)malloc(n * sizeof(int64_t));
    int64_t *d = (int64_t *)malloc(n * sizeof(int64_t));
    int64_t *c = (int64_t *)malloc(n * sizeof(int64_t));

    for (int i = 0; i < n; i++) {
        a[i] = (i % 50) + 1;
        b[i] = (i % 30) + 1;
        d[i] = 100;
    }

    for (int j = 0; j < n; j++) {
        int64_t val = a[j] * b[j] - d[j];
        c[j] = (val > 0) ? val : 0;
    }

    int64_t res = c[n / 2];
    free(a); free(b); free(d); free(c);
    return res;
}

int main(void) {
    int64_t res = 0;
    for (int iter = 0; iter < 10; iter++) {
        res = run_fusion(1000000);
    }
    printf("Fusion Checksum: %lld\n", (long long)res);
    return 0;
}
