fn run_sieve(limit: usize) -> usize {
    let mut is_prime = vec![true; limit + 1];
    is_prime[0] = false;
    is_prime[1] = false;

    let mut p = 2;
    while p * p <= limit {
        if is_prime[p] {
            let mut k = p * p;
            while k <= limit {
                is_prime[k] = false;
                k += p;
            }
        }
        p += 1;
    }

    is_prime.iter().filter(|&&x| x).count()
}

fn main() {
    let mut total_primes = 0;
    for _ in 0..10 {
        total_primes = run_sieve(1000000);
    }
    println!("Primes count: {}", total_primes);
}
