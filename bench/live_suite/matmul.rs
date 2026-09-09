fn run_matmul(n: usize) -> i64 {
    let mut a = vec![0i64; n * n];
    let mut b = vec![0i64; n * n];
    let mut c = vec![0i64; n * n];

    for i in 0..n {
        for j in 0..n {
            a[i * n + j] = ((i + j) % 100) as i64;
            b[i * n + j] = ((i * j) % 100) as i64;
        }
    }

    for i in 0..n {
        for k in 0..n {
            let a_ik = a[i * n + k];
            for j in 0..n {
                c[i * n + j] += a_ik * b[k * n + j];
            }
        }
    }

    c[n * n - 1]
}

fn main() {
    let mut checksum = 0;
    for _ in 0..10 {
        checksum = run_matmul(128);
    }
    println!("Matmul Checksum: {}", checksum);
}
