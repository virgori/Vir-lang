#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define N 64

int main(void) {
    int64_t *a = (int64_t *)malloc(N * sizeof(int64_t));
    int64_t *b = (int64_t *)malloc(N * sizeof(int64_t));
    int64_t *c = (int64_t *)malloc(N * sizeof(int64_t));

    for (int i = 0; i < N; i++) {
        a[i] = (i + 1) * 3;
        b[i] = (i + 1) * 7;
    }

    int64_t sum = 0;
    for (int iter = 0; iter < 1000000; iter++) {
        for (int i = 0; i < 2; i++) {
            c[i] = a[i] + b[i];
        }
        sum += c[0] + c[1];
    }

    printf("%lld\n", (long long)sum);
    free(a);
    free(b);
    free(c);
    return 0;
}
