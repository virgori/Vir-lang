// Algorithm Benchmark: quicksort (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

void swap(int64_t* a, int64_t* b) {
    int64_t t = *a;
    *a = *b;
    *b = t;
}

int64_t partition(int64_t* arr, int64_t low, int64_t high) {
    int64_t pivot = arr[high];
    int64_t i = low - 1;
    for (int64_t j = low; j < high; j++) {
        if (arr[j] <= pivot) {
            i++;
            swap(&arr[i], &arr[j]);
        }
    }
    swap(&arr[i + 1], &arr[high]);
    return i + 1;
}

void quicksort(int64_t* arr, int64_t low, int64_t high) {
    if (low < high) {
        int64_t pi = partition(arr, low, high);
        quicksort(arr, low, pi - 1);
        quicksort(arr, pi + 1, high);
    }
}

int main() {
    int64_t n = 50000;
    int64_t* arr = (int64_t*)malloc(n * sizeof(int64_t));
    
    // Standard POSIX LCG PRNG
    int64_t seed = 12345678;
    for (int64_t i = 0; i < n; i++) {
        seed = ((seed * 1103515245) + 12345) & 0x7FFFFFFF;
        arr[i] = seed % 1000000;
    }
    
    quicksort(arr, 0, n - 1);
    
    // Calculate checksum
    int64_t chk = 0;
    for (int64_t i = 0; i < n; i++) {
        chk = (chk * 33) ^ arr[i];
    }
    free(arr);
    printf("checksum=%lld\n", (long long)chk);
    return 0;
}
