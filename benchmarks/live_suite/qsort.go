package main

import "fmt"

func qsortCustom(arr []int64, low, high int) {
	if low < high {
		pivot := arr[high]
		i := low
		for j := low; j < high; j++ {
			if arr[j] <= pivot {
				arr[i], arr[j] = arr[j], arr[i]
				i++
			}
		}
		arr[i], arr[high] = arr[high], arr[i]
		pi := i
		if pi > 0 {
			qsortCustom(arr, low, pi-1)
		}
		qsortCustom(arr, pi+1, high)
	}
}

func main() {
	n := 100000
	arr := make([]int64, n)
	for i := 0; i < n; i++ {
		arr[i] = (int64(i)*1664525 + 1013904223) % 1000000
	}
	qsortCustom(arr, 0, n-1)
	fmt.Printf("Qsort Checksum: %d\n", arr[n/2])
}
