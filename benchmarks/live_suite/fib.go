package main

import "fmt"

func fib(n uint64) uint64 {
	if n <= 1 {
		return n
	}
	return fib(n-1) + fib(n-2)
}

func main() {
	res := fib(40)
	fmt.Printf("Result: %d\n", res)
}
