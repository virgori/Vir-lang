def run_sieve(limit):
    is_prime = [True] * (limit + 1)
    is_prime[0] = False
    is_prime[1] = False

    p = 2
    while p * p <= limit:
        if is_prime[p]:
            for k in range(p * p, limit + 1, p):
                is_prime[k] = False
        p += 1

    return sum(is_prime)

if __name__ == "__main__":
    total_primes = 0
    for _ in range(2): # Python runs 2 reps to avoid taking too long
        total_primes = run_sieve(1000000)
    print(f"Primes count: {total_primes}")
