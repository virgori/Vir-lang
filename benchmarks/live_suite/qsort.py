import sys
sys.setrecursionlimit(200000)

def qsort_custom(arr, low, high):
    if low < high:
        pivot = arr[high]
        i = low
        for j in range(low, high):
            if arr[j] <= pivot:
                arr[i], arr[j] = arr[j], arr[i]
                i += 1
        arr[i], arr[high] = arr[high], arr[i]
        pi = i
        if pi > 0:
            qsort_custom(arr, low, pi - 1)
        qsort_custom(arr, pi + 1, high)

if __name__ == "__main__":
    n = 20000 # 20k for python to avoid excessive run times
    arr = [((i * 1664525 + 1013904223) % 1000000) for i in range(n)]
    qsort_custom(arr, 0, n - 1)
    print(f"Qsort Checksum: {arr[n // 2]}")
