package main

import "fmt"

func runMatmul(n int) int64 {
	a := make([]int64, n*n)
	b := make([]int64, n*n)
	c := make([]int64, n*n)

	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			a[i*n+j] = int64((i + j) % 100)
			b[i*n+j] = int64((i * j) % 100)
		}
	}

	for i := 0; i < n; i++ {
		for k := 0; k < n; k++ {
			aIK := a[i*n+k]
			for j := 0; j < n; j++ {
				c[i*n+j] += aIK * b[k*n+j]
			}
		}
	}

	return c[n*n-1]
}

func main() {
	var checksum int64
	for iter := 0; iter < 10; iter++ {
		checksum = runMatmul(128)
	}
	fmt.Printf("Matmul Checksum: %d\n", checksum)
}
