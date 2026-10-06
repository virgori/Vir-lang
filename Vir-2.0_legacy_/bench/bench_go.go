package main

import (
	"fmt"
	"math"
	"time"
)

func benchSoftmax() {
	n := 100000
	x := make([]float64, n)
	out := make([]float64, n)
	for i := range x {
		x[i] = float64(i)*0.001 - 50.0
	}
	var total int64
	for rep := 0; rep < 200; rep++ {
		t0 := time.Now()
		rm := x[0]
		se := 1.0
		for i := 1; i < n; i++ {
			if x[i] > rm {
				se = se * math.Exp(rm-x[i])
				rm = x[i]
				se += 1.0
			} else {
				se += math.Exp(x[i] - rm)
			}
		}
		inv := 1.0 / se
		for i := 0; i < n; i++ {
			out[i] = math.Exp(x[i]-rm) * inv
		}
		total += time.Since(t0).Nanoseconds()
		_ = out[0]
	}
	fmt.Printf("Softmax(100K): %.3f us\n", float64(total)/200.0/1000.0)
}

func benchWelford() {
	n := 1000000
	x := make([]float64, n)
	for i := range x {
		x[i] = float64(i) * 0.001
	}
	var total int64
	for rep := 0; rep < 100; rep++ {
		t0 := time.Now()
		mean := 0.0
		m2 := 0.0
		comp := 0.0
		for i := 0; i < n; i++ {
			delta := x[i] - mean
			mean += delta / float64(i+1)
			delta2 := x[i] - mean
			term := delta * delta2
			y := term - comp
			s := m2 + y
			comp = (s - m2) - y
			m2 = s
		}
		v := m2 / float64(n)
		total += time.Since(t0).Nanoseconds()
		_ = v
	}
	fmt.Printf("Welford(1M): %.3f us\n", float64(total)/100.0/1000.0)
}

func benchFusion() {
	n := 1000000
	a := make([]float64, n)
	b := make([]float64, n)
	c := make([]float64, n)
	out := make([]float64, n)
	for i := 0; i < n; i++ {
		a[i] = float64(i) * 0.001
		b[i] = float64(i) * 0.002
		c[i] = float64(i) * 0.003
	}
	var total int64
	for rep := 0; rep < 200; rep++ {
		t0 := time.Now()
		for i := 0; i < n; i++ {
			v := a[i]*b[i] + c[i]
			if v > 0.0 {
				out[i] = v
			} else {
				out[i] = 0.0
			}
		}
		total += time.Since(t0).Nanoseconds()
		_ = out[0]
	}
	fmt.Printf("EWFused(1M): %.3f us\n", float64(total)/200.0/1000.0)
}

func main() {
	benchSoftmax()
	benchWelford()
	benchFusion()
}
