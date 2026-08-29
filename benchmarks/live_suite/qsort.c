#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

void qsort_custom(int64_t *arr, int low, int high) {
    if (low < high) {
        int64_t pivot = arr[high];
        int i = low;
        for (int j = low; j < high; j++) {
            if (arr[j] <= pivot) {
                int64_t temp = arr[i];
                arr[i] = arr[j];
                arr[j] = temp;
                i++;
            }
        }
        int64_t temp2 = arr[i];
        arr[i] = arr[high];
        arr[high] = temp2;

        int pi = i;
        if (pi > 0) qsort_custom(arr, low, pi - 1);
        qsort_custom(arr, pi + 1, high);
    }
}

int main(void) {
    int n = 100000;
    int64_t *arr = (int64_t *)malloc(n * sizeof(int64_t));
    for (int i = 0; i < n; i++) {
        arr[i] = ((int64_t)i * 1664525 + 1013904223) % 1000000;
    }
    qsort_custom(arr, 0, n - 1);
    printf("Qsort Checksum: %lld\n", (long long)arr[n / 2]);
    free(arr);
    return 0;
}
