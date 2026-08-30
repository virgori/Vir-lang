def run_kahan_dot(n):
    a = [(i % 100) + 1 for i in range(n)]
    b = [(i % 50) + 1 for i in range(n)]

    total_sum = 0
    comp = 0
    for j in range(n):
        term = a[j] * b[j]
        y = term - comp
        t = total_sum + y
        comp = (t - total_sum) - y
        total_sum = t

    return total_sum

if __name__ == "__main__":
    res = 0
    for _ in range(2):
        res = run_kahan_dot(500000)
    print(f"Kahan Dot Sum: {res}")
