// bench_comprehensive_go.go — Vir Cross-Language Benchmark (Go)
// Run: go run bench_comprehensive_go.go
package main

import (
	"fmt"
	"math"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
	"unsafe"
)

// ═══════════════════════════════════════════════════════
// 1. COMPUTATIONAL THROUGHPUT
// ═══════════════════════════════════════════════════════

func gemmTiled(a, b, c []float64, n int) {
	const TILE = 64
	for i := range c {
		c[i] = 0
	}
	for i0 := 0; i0 < n; i0 += TILE {
		for k0 := 0; k0 < n; k0 += TILE {
			for j0 := 0; j0 < n; j0 += TILE {
				ie := min(i0+TILE, n)
				ke := min(k0+TILE, n)
				je := min(j0+TILE, n)
				for i := i0; i < ie; i++ {
					for k := k0; k < ke; k++ {
						aik := a[i*n+k]
						for j := j0; j < je; j++ {
							c[i*n+j] += aik * b[k*n+j]
						}
					}
				}
			}
		}
	}
}

func winogradF2x3(tile, filt [16]float64) [4]float64 {
	r00 := tile[0] - tile[8]
	r01 := tile[1] - tile[9]
	r02 := tile[2] - tile[10]
	r03 := tile[3] - tile[11]
	r10 := tile[4] + tile[8]
	r11 := tile[5] + tile[9]
	r12 := tile[6] + tile[10]
	r13 := tile[7] + tile[11]
	r20 := tile[8] - tile[4]
	r21 := tile[9] - tile[5]
	r22 := tile[10] - tile[6]
	r23 := tile[11] - tile[7]
	r30 := tile[4] - tile[12]
	r31 := tile[5] - tile[13]
	r32 := tile[6] - tile[14]
	r33 := tile[7] - tile[15]

	d := [16]float64{
		r00 - r02, r01 + r02, r02 - r01, r01 - r03,
		r10 - r12, r11 + r12, r12 - r11, r11 - r13,
		r20 - r22, r21 + r22, r22 - r21, r21 - r23,
		r30 - r32, r31 + r32, r32 - r31, r31 - r33,
	}

	var v [16]float64
	for i := 0; i < 16; i++ {
		v[i] = d[i] * filt[i]
	}

	s00 := v[0] + v[4] + v[8]
	s01 := v[1] + v[5] + v[9]
	s02 := v[2] + v[6] + v[10]
	s03 := v[3] + v[7] + v[11]
	s10 := v[4] - v[8] - v[12]
	s11 := v[5] - v[9] - v[13]
	s12 := v[6] - v[10] - v[14]
	s13 := v[7] - v[11] - v[15]
	return [4]float64{s00 + s01 + s02, s01 - s02 - s03, s10 + s11 + s12, s11 - s12 - s13}
}

func kahanDot(a, b []float64) float64 {
	sum, comp := 0.0, 0.0
	for i := range a {
		y := a[i]*b[i] - comp
		s := sum + y
		comp = (s - sum) - y
		sum = s
	}
	return sum
}

func softmaxOnline(x, out []float64) {
	runMax := math.Inf(-1)
	runSum := 0.0
	for _, v := range x {
		if v > runMax {
			runSum = runSum * math.Exp(runMax-v)
			runMax = v
		}
		runSum += math.Exp(v - runMax)
	}
	for i, v := range x {
		out[i] = math.Exp(v-runMax) / runSum
	}
}

func fusedEW(x, y []float64, a, b float64) {
	for i := range x {
		v := a*x[i] + b
		if v > 0 {
			y[i] = v
		} else {
			y[i] = 0
		}
	}
}

func unfusedEW(x, y []float64, a, b float64) {
	n := len(x)
	t1 := make([]float64, n)
	t2 := make([]float64, n)
	for i := 0; i < n; i++ {
		t1[i] = a * x[i]
	}
	for i := 0; i < n; i++ {
		t2[i] = t1[i] + b
	}
	for i := 0; i < n; i++ {
		if t2[i] > 0 {
			y[i] = t2[i]
		} else {
			y[i] = 0
		}
	}
}

func welfordKahan(x []float64) (float64, float64) {
	mean, m2, comp := 0.0, 0.0, 0.0
	for i, v := range x {
		delta := v - mean
		mean += delta / float64(i+1)
		delta2 := v - mean
		y := delta*delta2 - comp
		s := m2 + y
		comp = (s - m2) - y
		m2 = s
	}
	return mean, m2 / float64(len(x))
}

// ═══════════════════════════════════════════════════════
// 2. MEMORY
// ═══════════════════════════════════════════════════════

func benchAllocLatency(n, size int) float64 {
	start := time.Now()
	for i := 0; i < n; i++ {
		b := make([]byte, size)
		b[0] = 1 // touch
		_ = b
	}
	return float64(time.Since(start).Nanoseconds()) / float64(n)
}

// ═══════════════════════════════════════════════════════
// 5. SCALABILITY
// ═══════════════════════════════════════════════════════

func parallelSum(data []float64, nThreads int) float64 {
	chunk := len(data) / nThreads
	var wg sync.WaitGroup
	// Use atomic uint64 to store float64 bits
	var result uint64
	atomic.StoreUint64(&result, math.Float64bits(0.0))

	for t := 0; t < nThreads; t++ {
		start := t * chunk
		end := start + chunk
		if t == nThreads-1 {
			end = len(data)
		}
		wg.Add(1)
		go func(s, e int) {
			defer wg.Done()
			local := 0.0
			for i := s; i < e; i++ {
				local += data[i]
			}
			for {
				old := atomic.LoadUint64(&result)
				newVal := math.Float64frombits(old) + local
				if atomic.CompareAndSwapUint64(&result, old, math.Float64bits(newVal)) {
					break
				}
			}
		}(start, end)
	}
	wg.Wait()
	return math.Float64frombits(atomic.LoadUint64(&result))
}

// ═══════════════════════════════════════════════════════
// NUMERICAL STABILITY
// ═══════════════════════════════════════════════════════

func sumNaive(x []float64) float64 {
	s := 0.0
	for _, v := range x {
		s += v
	}
	return s
}

func sumKahan(x []float64) float64 {
	s, c := 0.0, 0.0
	for _, v := range x {
		y := v - c
		t := s + y
		c = (t - s) - y
		s = t
	}
	return s
}

// ═══════════════════════════════════════════════════════
// BENCHMARK HELPER
// ═══════════════════════════════════════════════════════

func bench(label string, iters int, body func()) float64 {
	body() // warmup
	start := time.Now()
	for i := 0; i < iters; i++ {
		body()
	}
	us := float64(time.Since(start).Nanoseconds()) / 1000.0 / float64(iters)
	fmt.Printf("%-40s %12.1f µs\n", label, us)
	return us
}

func main() {
	runtime.GOMAXPROCS(runtime.NumCPU())
	_ = unsafe.Sizeof(0)

	fmt.Println("═══════════════════════════════════════════")
	fmt.Printf("  Go Comprehensive Benchmark (go %s)\n", runtime.Version())
	fmt.Println("═══════════════════════════════════════════")
	fmt.Println()

	// ── 1. THROUGHPUT ────────────────────────────────
	fmt.Println("▓ 1. COMPUTATIONAL THROUGHPUT")
	fmt.Println("───────────────────────────────────────────")

	// GEMM 512
	{
		n := 512
		a := make([]float64, n*n)
		b := make([]float64, n*n)
		c := make([]float64, n*n)
		for i := range a {
			a[i] = float64(i%97) * 0.01
			b[i] = float64(i%89) * 0.01
		}
		bench("GEMM 512×512 tiled", 5, func() { gemmTiled(a, b, c, n) })
	}

	// GEMM 1024
	{
		n := 1024
		a := make([]float64, n*n)
		b := make([]float64, n*n)
		c := make([]float64, n*n)
		for i := range a {
			a[i] = float64(i%97) * 0.01
			b[i] = float64(i%89) * 0.01
		}
		bench("GEMM 1024×1024 tiled", 3, func() { gemmTiled(a, b, c, n) })
	}

	// Winograd
	{
		var tile [16]float64
		var filt [16]float64
		for i := 0; i < 16; i++ {
			tile[i] = float64(i) * 0.1
			filt[i] = float64(15-i) * 0.1
		}
		bench("Winograd F(2,3) 100K tiles", 10, func() {
			for t := 0; t < 100000; t++ {
				tile[0] = float64(t) * 0.00001
				_ = winogradF2x3(tile, filt)
			}
		})
	}

	// Softmax
	{
		n := 100000
		x := make([]float64, n)
		y := make([]float64, n)
		for i := range x {
			x[i] = float64(i%1000)*0.001 - 0.5
		}
		bench("Softmax (2-pass online) 100K", 200, func() { softmaxOnline(x, y) })
	}

	// Fused EW
	{
		n := 1000000
		x := make([]float64, n)
		y := make([]float64, n)
		for i := range x {
			x[i] = float64(i) * 1e-6
		}
		bench("EW fused (mul+add+relu) 1M", 200, func() { fusedEW(x, y, 2.0, -0.5) })
		bench("EW unfused 3-pass 1M", 200, func() { unfusedEW(x, y, 2.0, -0.5) })
	}

	// Welford
	{
		n := 1000000
		x := make([]float64, n)
		for i := range x {
			x[i] = float64(i%10000) * 0.0001
		}
		bench("Welford-Kahan variance 1M", 50, func() { welfordKahan(x) })
	}

	// Kahan dot
	{
		n := 10000000
		a := make([]float64, n)
		b := make([]float64, n)
		for i := range a {
			a[i] = 1.0 + 1e-8*float64(i)
			b[i] = 1.0 - 1e-8*float64(i)
		}
		bench("Kahan dot product 10M", 10, func() { kahanDot(a, b) })
	}

	// ── 2. MEMORY ───────────────────────────────────
	fmt.Println("\n▓ 2. MEMORY DISCIPLINE (GC-managed)")
	fmt.Println("───────────────────────────────────────────")

	fmt.Printf("%-40s %12.1f ns/op\n", "make([]byte, 64)", benchAllocLatency(1000000, 64))
	fmt.Printf("%-40s %12.1f ns/op\n", "make([]byte, 4KB)", benchAllocLatency(1000000, 4096))
	fmt.Printf("%-40s %12.1f ns/op\n", "make([]byte, 1MB)", benchAllocLatency(100000, 1048576))

	// GC pause
	{
		// Allocate a lot of small objects, measure GC
		runtime.GC()
		start := time.Now()
		for i := 0; i < 100000; i++ {
			b := make([]byte, 1024)
			b[0] = byte(i)
			_ = b
		}
		runtime.GC()
		elapsed := time.Since(start)
		fmt.Printf("%-40s %12.1f µs\n", "100K alloc + GC cycle", float64(elapsed.Microseconds()))
	}

	// ── 5. SCALABILITY ──────────────────────────────
	fmt.Println("\n▓ 5. SCALABILITY & GOROUTINES")
	fmt.Println("───────────────────────────────────────────")

	{
		n := 10000000
		data := make([]float64, n)
		for i := range data {
			data[i] = 1.0
		}

		bench("Sum 10M (1 goroutine)", 20, func() { sumNaive(data) })

		for _, nt := range []int{2, 4, 8} {
			label := fmt.Sprintf("Sum 10M (%d goroutines)", nt)
			nThreads := nt
			bench(label, 20, func() { parallelSum(data, nThreads) })
		}
	}

	// ── NUMERICAL STABILITY ──────────────────────────
	fmt.Println("\n▓ NUMERICAL STABILITY")
	fmt.Println("───────────────────────────────────────────")

	{
		n := 10000000
		x := make([]float64, n)
		for i := range x {
			x[i] = 1.0 + 1e-12*float64(i-n/2)
		}
		naive := sumNaive(x)
		kahan := sumKahan(x)
		trueSum := float64(n)
		fmt.Printf("  True sum (analytic): %.15e\n", trueSum)
		fmt.Printf("  Naive summation:     %.15e  (err=%.2e)\n", naive, math.Abs(naive-trueSum))
		fmt.Printf("  Kahan summation:     %.15e  (err=%.2e)\n", kahan, math.Abs(kahan-trueSum))
	}

	fmt.Println("\n═══════════════════════════════════════════")
}
