package main

import "fmt"

func runFusion(n int) int64 {
	a := make([]int64, n)
	b := make([]int64, n)
	d := make([]int64, n)
	c := make([]int64, n)

	for i := 0; i < n; i++ {
		a[i] = int64((i % 50) + 1)
		b[i] = int64((i % 30) + 1)
		d[i] = 100
	}

	for j := 0; j < n; j++ {
		val := a[j]*b[j] - d[j]
		if val > 0 {
			c[j] = val
		} else {
			c[j] = 0
		}
	}

	return c[n/2]
}

func main() {
	var res int64 = 0
	for iter := 0; iter < 10; iter++ {
		res = runFusion(1000000)
	}
	fmt.Printf("Fusion Checksum: %d\n", res)
}
