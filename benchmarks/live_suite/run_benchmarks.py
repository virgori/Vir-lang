#!/usr/bin/env python3
import subprocess
import time
import os
import statistics

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "../.."))

def run_cmd(cmd, cwd=BASE_DIR):
    res = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"Error executing: {cmd}")
        print(res.stderr)
        raise RuntimeError(f"Command failed: {cmd}")
    return res.stdout.strip()

def compile_all():
    print("=== Compiling all benchmark targets ===")
    # 1. C (Clang -O3)
    run_cmd("cc -O3 -march=native fib.c -o bin_c_fib")
    run_cmd("cc -O3 -march=native sieve.c -o bin_c_sieve")
    run_cmd("cc -O3 -march=native matmul.c -o bin_c_matmul")

    # 2. Rust (rustc -O -C opt-level=3)
    run_cmd("rustc -O -C opt-level=3 fib.rs -o bin_rust_fib")
    run_cmd("rustc -O -C opt-level=3 sieve.rs -o bin_rust_sieve")
    run_cmd("rustc -O -C opt-level=3 matmul.rs -o bin_rust_matmul")

    # 3. Go (go build)
    run_cmd("go build -ldflags=\"-s -w\" -o bin_go_fib fib.go")
    run_cmd("go build -ldflags=\"-s -w\" -o bin_go_sieve sieve.go")
    run_cmd("go build -ldflags=\"-s -w\" -o bin_go_matmul matmul.go")

    # 4. Vir (virc native AOT)
    virc_bin = os.path.join(ROOT_DIR, "dist/virc-stage2")
    run_cmd(f"{virc_bin} fib.vri -o bin_vir_fib && codesign -s - -f bin_vir_fib && chmod +x bin_vir_fib")
    run_cmd(f"{virc_bin} sieve.vri -o bin_vir_sieve && codesign -s - -f bin_vir_sieve && chmod +x bin_vir_sieve")
    run_cmd(f"{virc_bin} matmul.vri -o bin_vir_matmul && codesign -s - -f bin_vir_matmul && chmod +x bin_vir_matmul")
    print("✓ All targets compiled successfully!")

def measure_command(cmd, reps=5):
    times = []
    output = None
    for _ in range(reps):
        t0 = time.perf_counter()
        res = subprocess.run(cmd, shell=True, cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        t1 = time.perf_counter()
        if res.returncode != 0:
            raise RuntimeError(f"Run failed: {cmd}\n{res.stderr}")
        times.append((t1 - t0) * 1000.0) # ms
        output = res.stdout.strip()
    median_ms = statistics.median(times)
    return median_ms, output

def main():
    compile_all()
    
    tasks = [
        ("Recursive Fib(40)", {
            "Vir": "./bin_vir_fib",
            "C (Clang -O3)": "./bin_c_fib",
            "Rust (rustc -O)": "./bin_rust_fib",
            "Go (gc)": "./bin_go_fib",
            "Python (3.13)": "python3 fib.py"
        }),
        ("Sieve (1M primes × 10)", {
            "Vir": "./bin_vir_sieve",
            "C (Clang -O3)": "./bin_c_sieve",
            "Rust (rustc -O)": "./bin_rust_sieve",
            "Go (gc)": "./bin_go_sieve",
            "Python (3.13)": "python3 sieve.py"
        }),
        ("GEMM 128×128 (10 reps)", {
            "Vir": "./bin_vir_matmul",
            "C (Clang -O3)": "./bin_c_matmul",
            "Rust (rustc -O)": "./bin_rust_matmul",
            "Go (gc)": "./bin_go_matmul",
            "Python (3.13)": "python3 matmul.py"
        })
    ]

    results = {}
    print("\n=== Running Benchmarks (5 runs median) ===")
    for task_name, cmds in tasks:
        print(f"--> Benchmarking: {task_name}")
        results[task_name] = {}
        for lang, cmd in cmds.items():
            reps = 3 if "Python" in lang else 5
            ms, out = measure_command(cmd, reps=reps)
            results[task_name][lang] = ms
            print(f"    [{lang:16s}] {ms:8.2f} ms  (Output: {out[:30]})")

    # Binary sizes
    sizes = {
        "Vir": os.path.getsize(os.path.join(BASE_DIR, "bin_vir_fib")),
        "C (Clang)": os.path.getsize(os.path.join(BASE_DIR, "bin_c_fib")),
        "Rust": os.path.getsize(os.path.join(BASE_DIR, "bin_rust_fib")),
        "Go": os.path.getsize(os.path.join(BASE_DIR, "bin_go_fib"))
    }

    print("\n" + "="*80)
    print("LIVE EMPIRICAL BENCHMARK REPORT (Apple Silicon M-series ARM64)")
    print("="*80)
    print(f"{'Task / Benchmark':<28} | {'Vir (Native)':<14} | {'C (Clang -O3)':<14} | {'Rust (-O)':<14} | {'Go (gc)':<14} | {'Python 3.13':<14}")
    print("-" * 105)
    for task_name, data in results.items():
        v_vir = f"{data['Vir']:.2f} ms"
        v_c = f"{data['C (Clang -O3)']:.2f} ms"
        v_rust = f"{data['Rust (rustc -O)']:.2f} ms"
        v_go = f"{data['Go (gc)']:.2f} ms"
        v_py = f"{data['Python (3.13)']:.2f} ms"
        print(f"{task_name:<28} | {v_vir:<14} | {v_c:<14} | {v_rust:<14} | {v_go:<14} | {v_py:<14}")

    print("-" * 105)
    print(f"{'Binary Size (Fib)':<28} | {sizes['Vir']/1024:<11.1f} KB | {sizes['C (Clang)']/1024:<11.1f} KB | {sizes['Rust']/1024:<11.1f} KB | {sizes['Go']/1024:<11.1f} KB | {'N/A':<14}")
    print("="*80)

if __name__ == "__main__":
    main()
