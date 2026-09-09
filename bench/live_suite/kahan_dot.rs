fn run_kahan_dot(n: usize) -> i64 {
    let mut a = Vec::with_capacity(n);
    let mut b = Vec::with_capacity(n);
    for i in 0..n {
        a.push(((i % 100) + 1) as i64);
        b.push(((i % 50) + 1) as i64);
    }

    let mut sum = 0i64;
    let mut comp = 0i64;
    for j in 0..n {
        let term = a[j] * b[j];
        let y = term - comp;
        let t = sum + y;
        comp = (t - sum) - y;
        sum = t;
    }

    sum
}

fn main() {
    let mut res = 0;
    for _ in 0..5 {
        res = run_kahan_dot(1000000);
    }
    println!("Kahan Dot Sum: {}", res);
}
