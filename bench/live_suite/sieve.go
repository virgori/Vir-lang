package main

import "fmt"

func runSieve(limit int) int {
	isPrime := make([]bool, limit+1)
	for i := 2; i <= limit; i++ {
		isPrime[i] = true
	}

	for p := 2; p*p <= limit; p++ {
		if isPrime[p] {
			for k := p * p; k <= limit; k += p {
				isPrime[k] = false
			}
		}
	}

	count := 0
	for c := 2; c <= limit; c++ {
		if isPrime[c] {
			count++
		}
	}
	return count
}

func main() {
	totalPrimes := 0
	for iter := 0; iter < 10; iter++ {
		totalPrimes = runSieve(1000000)
	}
	fmt.Printf("Primes count: %d\n", totalPrimes)
}
