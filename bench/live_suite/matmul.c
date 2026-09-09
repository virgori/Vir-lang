#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

int64_t run_matmul(int n) {
    int64_t *a = (int64_t *)malloc(n * n * sizeof(int64_t));
    int64_t *b = (int64_t *)malloc(n * n * sizeof(int64_t));
    int64_t *c = (int64_t *)calloc(n * n, sizeof(int64_t));

    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            a[i * n + j] = (i + j) % 100;
            b[i * n + j] = (i * j) % 100;
        }
    }

    for (int i = 0; i < n; i++) {
        for (int k = 0; k < n; k++) {
            int64_t a_ik = a[i * n + k];
            for (int j = 0; j < n; j++) {
                c[i * n + j] += a_ik * b[k * n + j];
            }
        }
    }

    int64_t res = c[n * n - 1];
    free(a); free(b); free(c);
    return res;
}

int main(void) {
    int64_t checksum = 0;
    for (int iter = 0; iter < 10; iter++) {
        checksum = run_matmul(128);
    }
    printf("Matmul Checksum: %lld\n", (long long)checksum);
    return 0;
}
