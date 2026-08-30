package main

import "fmt"

func runKahanDot(n int) int64 {
	a := make([]int64, n)
	b := make([]int64, n)
	for i := 0; i < n; i++ {
		a[i] = int64((i % 100) + 1)
		b[i] = int64((i % 50) + 1)
	}

	var sum int64 = 0
	var comp int64 = 0
	for j := 0; j < n; j++ {
		term := a[j] * b[j]
		y := term - comp
		t := sum + y
		comp = (t - sum) - y
		sum = t
	}
	return sum
}

func main() {
	var res int64 = 0
	for iter := 0; iter < 5; iter++ {
		res = runKahanDot(1000000)
	}
	fmt.Printf("Kahan Dot Sum: %d\n", res)
}
