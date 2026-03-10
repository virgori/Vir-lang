// bench_comprehensive_rust.rs — Vir Cross-Language Benchmark (Rust)
// Compile: rustc -O -o bench_rust bench_comprehensive_rust.rs
// Covers: Throughput, Memory, Scalability

use std::time::{Instant, Duration};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

// ═══════════════════════════════════════════════════════
// 1. COMPUTATIONAL THROUGHPUT
// ═══════════════════════════════════════════════════════

fn gemm_tiled(a: &[f64], b: &[f64], c: &mut [f64], n: usize) {
    const TILE: usize = 64;
    c.iter_mut().for_each(|x| *x = 0.0);
    for i0 in (0..n).step_by(TILE) {
    for k0 in (0..n).step_by(TILE) {
    for j0 in (0..n).step_by(TILE) {
        let ie = (i0+TILE).min(n);
        let ke = (k0+TILE).min(n);
        let je = (j0+TILE).min(n);
        for i in i0..ie {
        for k in k0..ke {
            let a_ik = a[i*n+k];
            for j in j0..je {
                c[i*n+j] += a_ik * b[k*n+j];
            }
        }}
    }}}
}

fn winograd_f2x3(tile: &[f64; 16], filt: &[f64; 16]) -> [f64; 4] {
    // B^T · tile · B
    let r00=tile[0]-tile[8]; let r01=tile[1]-tile[9]; let r02=tile[2]-tile[10]; let r03=tile[3]-tile[11];
    let r10=tile[4]+tile[8]; let r11=tile[5]+tile[9]; let r12=tile[6]+tile[10]; let r13=tile[7]+tile[11];
    let r20=tile[8]-tile[4]; let r21=tile[9]-tile[5]; let r22=tile[10]-tile[6]; let r23=tile[11]-tile[7];
    let r30=tile[4]-tile[12];let r31=tile[5]-tile[13];let r32=tile[6]-tile[14];let r33=tile[7]-tile[15];

    let d = [
        r00-r02, r01+r02, r02-r01, r01-r03,
        r10-r12, r11+r12, r12-r11, r11-r13,
        r20-r22, r21+r22, r22-r21, r21-r23,
        r30-r32, r31+r32, r32-r31, r31-r33,
    ];

    let v: [f64;16] = std::array::from_fn(|i| d[i]*filt[i]);

    let s00=v[0]+v[4]+v[8]; let s01=v[1]+v[5]+v[9]; let s02=v[2]+v[6]+v[10]; let s03=v[3]+v[7]+v[11];
    let s10=v[4]-v[8]-v[12];let s11=v[5]-v[9]-v[13];let s12=v[6]-v[10]-v[14];let s13=v[7]-v[11]-v[15];

    [s00+s01+s02, s01-s02-s03, s10+s11+s12, s11-s12-s13]
}

fn kahan_dot(a: &[f64], b: &[f64]) -> f64 {
    let mut sum = 0.0f64;
    let mut comp = 0.0f64;
    for i in 0..a.len() {
        let y = a[i] * b[i] - comp;
        let s = sum + y;
        comp = (s - sum) - y;
        sum = s;
    }
    sum
}

fn softmax_online(x: &[f64], out: &mut [f64]) {
    let mut run_max = f64::NEG_INFINITY;
    let mut run_sum = 0.0f64;
    for &v in x.iter() {
        if v > run_max {
            run_sum = run_sum * (run_max - v).exp();
            run_max = v;
        }
        run_sum += (v - run_max).exp();
    }
    for (i, &v) in x.iter().enumerate() {
        out[i] = (v - run_max).exp() / run_sum;
    }
}

fn fused_ew(x: &[f64], y: &mut [f64], a: f64, b: f64) {
    for i in 0..x.len() {
        let v = a * x[i] + b;
        y[i] = if v > 0.0 { v } else { 0.0 };
    }
}

fn unfused_ew(x: &[f64], y: &mut [f64], a: f64, b: f64) {
    let n = x.len();
    let mut t1 = vec![0.0; n];
    let mut t2 = vec![0.0; n];
    for i in 0..n { t1[i] = a * x[i]; }
    for i in 0..n { t2[i] = t1[i] + b; }
    for i in 0..n { y[i] = if t2[i] > 0.0 { t2[i] } else { 0.0 }; }
}

fn welford_kahan(x: &[f64]) -> (f64, f64) {
    let mut mean = 0.0f64;
    let mut m2 = 0.0f64;
    let mut comp = 0.0f64;
    for (i, &v) in x.iter().enumerate() {
        let delta = v - mean;
        mean += delta / (i as f64 + 1.0);
        let delta2 = v - mean;
        let y = delta * delta2 - comp;
        let s = m2 + y;
        comp = (s - m2) - y;
        m2 = s;
    }
    (mean, m2 / x.len() as f64)
}

// ═══════════════════════════════════════════════════════
// 2. MEMORY
// ═══════════════════════════════════════════════════════

fn bench_alloc_latency(n: usize, size: usize) -> f64 {
    let start = Instant::now();
    for _ in 0..n {
        let v = vec![0u8; size];
        std::hint::black_box(&v);
    }
    let elapsed = start.elapsed();
    elapsed.as_nanos() as f64 / n as f64
}

// ═══════════════════════════════════════════════════════
// 5. SCALABILITY
// ═══════════════════════════════════════════════════════

fn parallel_sum(data: &[f64], n_threads: usize) -> f64 {
    let data = Arc::new(data.to_vec());
    let chunk = data.len() / n_threads;
    let handles: Vec<_> = (0..n_threads).map(|t| {
        let data = Arc::clone(&data);
        let start = t * chunk;
        let end = if t == n_threads - 1 { data.len() } else { start + chunk };
        std::thread::spawn(move || {
            let mut s = 0.0;
            for i in start..end { s += data[i]; }
            s
        })
    }).collect();
    handles.into_iter().map(|h| h.join().unwrap()).sum()
}

// ═══════════════════════════════════════════════════════
// NUMERICAL STABILITY
// ═══════════════════════════════════════════════════════

fn sum_naive(x: &[f64]) -> f64 {
    x.iter().sum()
}

fn sum_kahan(x: &[f64]) -> f64 {
    let (mut s, mut c) = (0.0f64, 0.0f64);
    for &v in x {
        let y = v - c;
        let t = s + y;
        c = (t - s) - y;
        s = t;
    }
    s
}

// ═══════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════

macro_rules! bench {
    ($label:expr, $iters:expr, $body:expr) => {{
        // warmup
        let _ = $body;
        let start = Instant::now();
        for _ in 0..$iters { let _ = std::hint::black_box($body); }
        let us = start.elapsed().as_nanos() as f64 / 1000.0 / $iters as f64;
        println!("{:<40} {:>12.1} µs", $label, us);
        us
    }};
}

fn main() {
    println!("═══════════════════════════════════════════");
    println!("  Rust Comprehensive Benchmark (rustc -O)");
    println!("═══════════════════════════════════════════\n");

    // ── 1. THROUGHPUT ────────────────────────────────
    println!("▓ 1. COMPUTATIONAL THROUGHPUT");
    println!("───────────────────────────────────────────");

    // GEMM 512
    {
        let n = 512;
        let a: Vec<f64> = (0..n*n).map(|i| (i % 97) as f64 * 0.01).collect();
        let b: Vec<f64> = (0..n*n).map(|i| (i % 89) as f64 * 0.01).collect();
        let mut c = vec![0.0; n*n];
        bench!("GEMM 512×512 tiled", 5, gemm_tiled(&a, &b, &mut c, n));
    }

    // GEMM 1024
    {
        let n = 1024;
        let a: Vec<f64> = (0..n*n).map(|i| (i % 97) as f64 * 0.01).collect();
        let b: Vec<f64> = (0..n*n).map(|i| (i % 89) as f64 * 0.01).collect();
        let mut c = vec![0.0; n*n];
        bench!("GEMM 1024×1024 tiled", 3, gemm_tiled(&a, &b, &mut c, n));
    }

    // Winograd
    {
        let mut tile = [0.0f64; 16];
        let filt: [f64; 16] = std::array::from_fn(|i| (15 - i) as f64 * 0.1);
        for i in 0..16 { tile[i] = i as f64 * 0.1; }
        bench!("Winograd F(2,3) 100K tiles", 10, {
            let mut s = 0.0;
            for t in 0..100000 {
                tile[0] = t as f64 * 0.00001;
                let o = winograd_f2x3(&tile, &filt);
                s += o[0];
            }
            s
        });
    }

    // Softmax
    {
        let n = 100_000;
        let x: Vec<f64> = (0..n).map(|i| (i % 1000) as f64 * 0.001 - 0.5).collect();
        let mut y = vec![0.0; n];
        bench!("Softmax (2-pass online) 100K", 200, {
            softmax_online(&x, &mut y);
            y[n / 2]
        });
    }

    // Fused EW
    {
        let n = 1_000_000;
        let x: Vec<f64> = (0..n).map(|i| i as f64 * 1e-6).collect();
        let mut y = vec![0.0; n];
        bench!("EW fused (mul+add+relu) 1M", 200, { fused_ew(&x, &mut y, 2.0, -0.5); y[n/2] });
        bench!("EW unfused 3-pass 1M", 200, { unfused_ew(&x, &mut y, 2.0, -0.5); y[n/2] });
    }

    // Welford
    {
        let n = 1_000_000;
        let x: Vec<f64> = (0..n).map(|i| (i % 10000) as f64 * 0.0001).collect();
        bench!("Welford-Kahan variance 1M", 50, welford_kahan(&x));
    }

    // Kahan dot
    {
        let n = 10_000_000;
        let a: Vec<f64> = (0..n).map(|i| 1.0 + 1e-8 * i as f64).collect();
        let b: Vec<f64> = (0..n).map(|i| 1.0 - 1e-8 * i as f64).collect();
        bench!("Kahan dot product 10M", 10, kahan_dot(&a, &b));
    }

    // ── 2. MEMORY ───────────────────────────────────
    println!("\n▓ 2. MEMORY DISCIPLINE");
    println!("───────────────────────────────────────────");

    println!("{:<40} {:>12.1} ns/op", "Vec::new 64B", bench_alloc_latency(1_000_000, 64));
    println!("{:<40} {:>12.1} ns/op", "Vec::new 4KB", bench_alloc_latency(1_000_000, 4096));
    println!("{:<40} {:>12.1} ns/op", "Vec::new 1MB", bench_alloc_latency(100_000, 1048576));

    // ── 5. SCALABILITY ──────────────────────────────
    println!("\n▓ 5. SCALABILITY & THREADING");
    println!("───────────────────────────────────────────");

    {
        let n = 10_000_000;
        let data: Vec<f64> = (0..n).map(|_| 1.0).collect();

        bench!("Sum 10M (1 thread)", 20, sum_naive(&data));

        for nt in &[2, 4, 8] {
            let label = format!("Sum 10M (threads, {} threads)", nt);
            bench!(&label, 20, parallel_sum(&data, *nt));
        }
    }

    // ── NUMERICAL STABILITY ──────────────────────────
    println!("\n▓ NUMERICAL STABILITY");
    println!("───────────────────────────────────────────");

    {
        let n = 10_000_000usize;
        let x: Vec<f64> = (0..n).map(|i| 1.0 + 1e-12 * (i as f64 - n as f64 / 2.0)).collect();

        let naive = sum_naive(&x);
        let kahan = sum_kahan(&x);
        let true_sum = n as f64;

        println!("  True sum (analytic): {:.15e}", true_sum);
        println!("  Naive summation:     {:.15e}  (err={:.2e})", naive, (naive - true_sum).abs());
        println!("  Kahan summation:     {:.15e}  (err={:.2e})", kahan, (kahan - true_sum).abs());
    }

    println!("\n═══════════════════════════════════════════");
}
