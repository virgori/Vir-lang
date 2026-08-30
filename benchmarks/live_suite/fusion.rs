fn run_fusion(n: usize) -> i64 {
    let mut a = Vec::with_capacity(n);
    let mut b = Vec::with_capacity(n);
    let mut d = Vec::with_capacity(n);
    let mut c = vec![0i64; n];

    for i in 0..n {
        a.push(((i % 50) + 1) as i64);
        b.push(((i % 30) + 1) as i64);
        d.push(100i64);
    }

    for j in 0..n {
        let val = a[j] * b[j] - d[j];
        c[j] = if val > 0 { val } else { 0 };
    }

    c[n / 2]
}

fn main() {
    let mut res = 0;
    for _ in 0..10 {
        res = run_fusion(1000000);
    }
    println!("Fusion Checksum: {}", res);
}
