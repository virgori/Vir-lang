use std::time::Instant;

fn bench_softmax() {
    let n: usize = 100_000;
    let x: Vec<f64> = (0..n).map(|i| i as f64 * 0.001 - 50.0).collect();
    let mut out = vec![0.0f64; n];
    let mut total = 0u128;
    for _ in 0..200 {
        let t0 = Instant::now();
        let mut rm = x[0];
        let mut se = 1.0f64;
        for i in 1..n {
            if x[i] > rm {
                se = se * (rm - x[i]).exp();
                rm = x[i];
                se += 1.0;
            } else {
                se += (x[i] - rm).exp();
            }
        }
        let inv = 1.0 / se;
        for i in 0..n {
            out[i] = (x[i] - rm).exp() * inv;
        }
        total += t0.elapsed().as_nanos();
        std::hint::black_box(&out);
    }
    println!("Softmax(100K): {:.3} us", total as f64 / 200.0 / 1000.0);
}

fn bench_welford() {
    let n: usize = 1_000_000;
    let x: Vec<f64> = (0..n).map(|i| i as f64 * 0.001).collect();
    let mut total = 0u128;
    for _ in 0..100 {
        let t0 = Instant::now();
        let mut mean = 0.0f64;
        let mut m2 = 0.0f64;
        let mut comp = 0.0f64;
        for i in 0..n {
            let delta = x[i] - mean;
            mean += delta / (i as f64 + 1.0);
            let delta2 = x[i] - mean;
            let term = delta * delta2;
            let y = term - comp;
            let s = m2 + y;
            comp = (s - m2) - y;
            m2 = s;
        }
        let v = m2 / n as f64;
        total += t0.elapsed().as_nanos();
        std::hint::black_box(v);
    }
    println!("Welford(1M): {:.3} us", total as f64 / 100.0 / 1000.0);
}

fn bench_fusion() {
    let n: usize = 1_000_000;
    let a: Vec<f64> = (0..n).map(|i| i as f64 * 0.001).collect();
    let b: Vec<f64> = (0..n).map(|i| i as f64 * 0.002).collect();
    let c: Vec<f64> = (0..n).map(|i| i as f64 * 0.003).collect();
    let mut out = vec![0.0f64; n];

    // Fused
    let mut total = 0u128;
    for _ in 0..200 {
        let t0 = Instant::now();
        for i in 0..n {
            let v = a[i] * b[i] + c[i];
            out[i] = if v > 0.0 { v } else { 0.0 };
        }
        total += t0.elapsed().as_nanos();
        std::hint::black_box(&out);
    }
    println!("EWFused(1M): {:.3} us", total as f64 / 200.0 / 1000.0);

    // Unfused
    total = 0;
    for _ in 0..200 {
        let t0 = Instant::now();
        let t1: Vec<f64> = (0..n).map(|i| a[i] * b[i]).collect();
        let t2: Vec<f64> = (0..n).map(|i| t1[i] + c[i]).collect();
        for i in 0..n {
            out[i] = if t2[i] > 0.0 { t2[i] } else { 0.0 };
        }
        total += t0.elapsed().as_nanos();
        std::hint::black_box(&out);
    }
    println!("EWUnfused(1M): {:.3} us", total as f64 / 200.0 / 1000.0);
}

fn main() {
    bench_softmax();
    bench_welford();
    bench_fusion();
}
