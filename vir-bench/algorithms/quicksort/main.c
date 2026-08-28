// Algorithm Benchmark: quicksort (C Reference)
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

void swap(uint64_t* a, uint64_t* b) {
    uint64_t t = *a;
    *a = *b;
    *b = t;
}

int64_t partition(uint64_t* arr, int64_t low, int64_t high) {
    uint64_t pivot = arr[high];
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

void quicksort(uint64_t* arr, int64_t low, int64_t high) {
    if (low < high) {
        int64_t pi = partition(arr, low, high);
        quicksort(arr, low, pi - 1);
        quicksort(arr, pi + 1, high);
    }
}

int main() {
    int64_t n = 50000;
    uint64_t* arr = (uint64_t*)malloc(n * sizeof(uint64_t));
    
    // LCG PRNG
    uint64_t seed = 0x12345678ULL;
    for (int64_t i = 0; i < n; i++) {
        seed = (seed * 6364136223846793005ULL + 1ULL);
        arr[i] = seed % 1000000;
    }
    
    quicksort(arr, 0, n - 1);
    
    // Calculate checksum
    uint64_t chk = 0;
    for (int64_t i = 0; i < n; i++) {
        chk = (chk * 33) ^ arr[i];
    }
    free(arr);
    printf("checksum=%llu\n", (unsigned long long)chk);
    return 0;
}
