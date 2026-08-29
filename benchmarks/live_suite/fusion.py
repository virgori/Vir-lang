def run_fusion(n):
    a = [(i % 50) + 1 for i in range(n)]
    b = [(i % 30) + 1 for i in range(n)]
    d = [100] * n
    c = [0] * n

    for j in range(n):
        val = a[j] * b[j] - d[j]
        c[j] = val if val > 0 else 0

    return c[n // 2]

if __name__ == "__main__":
    res = 0
    for _ in range(2):
        res = run_fusion(500000)
    print(f"Fusion Checksum: {res}")
