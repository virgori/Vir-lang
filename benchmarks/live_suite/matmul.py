def run_matmul(n):
    a = [0] * (n * n)
    b = [0] * (n * n)
    c = [0] * (n * n)

    for i in range(n):
        for j in range(n):
            a[i * n + j] = (i + j) % 100
            b[i * n + j] = (i * j) % 100

    for i in range(n):
        for k in range(n):
            a_ik = a[i * n + k]
            for j in range(n):
                c[i * n + j] += a_ik * b[k * n + j]

    return c[n * n - 1]

if __name__ == "__main__":
    checksum = 0
    for _ in range(2): # 2 reps for Python
        checksum = run_matmul(128)
    print(f"Matmul Checksum: {checksum}")
