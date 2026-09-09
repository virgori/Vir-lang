def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

if __name__ == "__main__":
    res = fib(35) # Note: fib(40) in pure python takes ~15s, so we test fib(35) and scale, or test fib(35)
    print(f"Result: {res}")
