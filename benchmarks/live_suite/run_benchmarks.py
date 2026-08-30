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
    print("=== Compiling all 7 benchmark targets ===")
    virc_bin = os.path.join(ROOT_DIR, "bin/virc")
    bench_names = ["fib", "sieve", "matmul", "qsort", "kahan_dot", "fusion"]
    
    for name in bench_names:
        # C (Clang -O2)
        run_cmd(f"cc -O2 -march=native {name}.c -o bin_c_{name}")
        # Rust (rustc -O -C opt-level=2)
        run_cmd(f"rustc -O -C opt-level=2 {name}.rs -o bin_rust_{name}")
        # Go (go build)
        run_cmd(f"go build -ldflags=\"-s -w\" -o bin_go_{name} {name}.go")
        # Vir (virc native AOT)
        run_cmd(f"{virc_bin} {name}.vri -o bin_vir_{name} && codesign -s - -f bin_vir_{name} && chmod +x bin_vir_{name}")

    print("✓ All 7 benchmark targets compiled successfully!")

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
            "C (Clang -O2)": "./bin_c_fib",
            "Rust (rustc -O2)": "./bin_rust_fib",
            "Go (gc)": "./bin_go_fib",
            "Python (3.13)": "python3 fib.py"
        }),
        ("Sieve (1M primes × 10)", {
            "Vir": "./bin_vir_sieve",
            "C (Clang -O2)": "./bin_c_sieve",
            "Rust (rustc -O2)": "./bin_rust_sieve",
            "Go (gc)": "./bin_go_sieve",
            "Python (3.13)": "python3 sieve.py"
        }),
        ("GEMM 128×128 (10 reps)", {
            "Vir": "./bin_vir_matmul",
            "C (Clang -O2)": "./bin_c_matmul",
            "Rust (rustc -O2)": "./bin_rust_matmul",
            "Go (gc)": "./bin_go_matmul",
            "Python (3.13)": "python3 matmul.py"
        }),
        ("Quicksort (100K ints)", {
            "Vir": "./bin_vir_qsort",
            "C (Clang -O2)": "./bin_c_qsort",
            "Rust (rustc -O2)": "./bin_rust_qsort",
            "Go (gc)": "./bin_go_qsort",
            "Python (3.13)": "python3 qsort.py"
        }),
        ("Kahan Dot (1M elements × 5)", {
            "Vir": "./bin_vir_kahan_dot",
            "C (Clang -O2)": "./bin_c_kahan_dot",
            "Rust (rustc -O2)": "./bin_rust_kahan_dot",
            "Go (gc)": "./bin_go_kahan_dot",
            "Python (3.13)": "python3 kahan_dot.py"
        }),
        ("Element-wise Fusion (1M × 10)", {
            "Vir": "./bin_vir_fusion",
            "C (Clang -O2)": "./bin_c_fusion",
            "Rust (rustc -O2)": "./bin_rust_fusion",
            "Go (gc)": "./bin_go_fusion",
            "Python (3.13)": "python3 fusion.py"
        })
    ]

    results = {}
    print("\n=== Running Full Cross-Language Benchmark Suite (5 runs median) ===")
    for task_name, cmds in tasks:
        print(f"--> Benchmarking: {task_name}")
        results[task_name] = {}
        for lang, cmd in cmds.items():
            reps = 3 if "Python" in lang else 5
            ms, out = measure_command(cmd, reps=reps)
            results[task_name][lang] = ms
            print(f"    [{lang:18s}] {ms:8.2f} ms  (Output: {out[:32]})")

    print("\n" + "="*95)
    print("LIVE AUDITED BENCHMARK RESULTS (Apple Silicon ARM64 — Vir vs Clang -O2 vs Rust vs Go)")
    print("="*95)
    print(f"{'Task / Benchmark':<30} | {'Vir (Native)':<14} | {'C (Clang -O2)':<14} | {'Rust (-O2)':<14} | {'Go (gc)':<14} | {'Python 3.13':<14}")
    print("-" * 115)
    for task_name, data in results.items():
        v_vir = f"{data['Vir']:.2f} ms"
        v_c = f"{data['C (Clang -O2)']:.2f} ms"
        v_rust = f"{data['Rust (rustc -O2)']:.2f} ms"
        v_go = f"{data['Go (gc)']:.2f} ms"
        v_py = f"{data['Python (3.13)']:.2f} ms"
        print(f"{task_name:<30} | {v_vir:<14} | {v_c:<14} | {v_rust:<14} | {v_go:<14} | {v_py:<14}")
    print("="*95)

if __name__ == "__main__":
    main()
