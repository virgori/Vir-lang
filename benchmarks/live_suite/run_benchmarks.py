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
    print("=== Compiling all benchmark targets (Clang -O3, Clang -O2, Rust -O3, Go, Vir) ===")
    virc_bin = os.path.join(ROOT_DIR, "bin/virc")
    bench_names = ["fib", "sieve", "matmul", "qsort", "kahan_dot", "fusion"]
    
    for name in bench_names:
        # C (Clang -O3 LTO fast-math)
        run_cmd(f"clang -O3 -march=native -ffast-math -flto {name}.c -o bin_c_o3_{name}")
        # C (Clang -O2)
        run_cmd(f"clang -O2 -march=native {name}.c -o bin_c_o2_{name}")
        # Rust (rustc -O3 fat LTO)
        run_cmd(f"rustc -C opt-level=3 -C target-cpu=native -C lto=fat -C codegen-units=1 {name}.rs -o bin_rust_o3_{name}")
        # Rust (rustc -O2)
        run_cmd(f"rustc -C opt-level=2 {name}.rs -o bin_rust_o2_{name}")
        # Go (go build)
        run_cmd(f"go build -ldflags=\"-s -w\" -o bin_go_{name} {name}.go")
        # Vir (virc native AOT)
        vri_src = os.path.join(BASE_DIR, f"{name}.vri")
        vri_out = os.path.join(BASE_DIR, f"bin_vir_{name}")
        run_cmd(f"{virc_bin} {vri_src} -o {vri_out} && codesign -s - -f {vri_out} && chmod +x {vri_out}")

    print("✓ All benchmark targets compiled successfully!")

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
        ("Recursive Fib(35)", {
            "Vir": "./bin_vir_fib",
            "C (Clang -O3)": "./bin_c_o3_fib",
            "C (Clang -O2)": "./bin_c_o2_fib",
            "Rust (-O3 LTO)": "./bin_rust_o3_fib",
            "Rust (-O2)": "./bin_rust_o2_fib",
            "Go (gc)": "./bin_go_fib",
        }),
        ("Sieve (1M primes × 10)", {
            "Vir": "./bin_vir_sieve",
            "C (Clang -O3)": "./bin_c_o3_sieve",
            "C (Clang -O2)": "./bin_c_o2_sieve",
            "Rust (-O3 LTO)": "./bin_rust_o3_sieve",
            "Rust (-O2)": "./bin_rust_o2_sieve",
            "Go (gc)": "./bin_go_sieve",
        }),
        ("GEMM 128×128 (10 reps)", {
            "Vir": "./bin_vir_matmul",
            "C (Clang -O3)": "./bin_c_o3_matmul",
            "C (Clang -O2)": "./bin_c_o2_matmul",
            "Rust (-O3 LTO)": "./bin_rust_o3_matmul",
            "Rust (-O2)": "./bin_rust_o2_matmul",
            "Go (gc)": "./bin_go_matmul",
        }),
        ("Quicksort (100K ints)", {
            "Vir": "./bin_vir_qsort",
            "C (Clang -O3)": "./bin_c_o3_qsort",
            "C (Clang -O2)": "./bin_c_o2_qsort",
            "Rust (-O3 LTO)": "./bin_rust_o3_qsort",
            "Rust (-O2)": "./bin_rust_o2_qsort",
            "Go (gc)": "./bin_go_qsort",
        }),
        ("Kahan Dot (1M elements × 5)", {
            "Vir": "./bin_vir_kahan_dot",
            "C (Clang -O3)": "./bin_c_o3_kahan_dot",
            "C (Clang -O2)": "./bin_c_o2_kahan_dot",
            "Rust (-O3 LTO)": "./bin_rust_o3_kahan_dot",
            "Rust (-O2)": "./bin_rust_o2_kahan_dot",
            "Go (gc)": "./bin_go_kahan_dot",
        }),
        ("Element-wise Fusion (1M × 10)", {
            "Vir": "./bin_vir_fusion",
            "C (Clang -O3)": "./bin_c_o3_fusion",
            "C (Clang -O2)": "./bin_c_o2_fusion",
            "Rust (-O3 LTO)": "./bin_rust_o3_fusion",
            "Rust (-O2)": "./bin_rust_o2_fusion",
            "Go (gc)": "./bin_go_fusion",
        })
    ]

    results = {}
    print("\n=== Running Full Cross-Language Benchmark Suite (5 runs median) ===")
    for task_name, cmds in tasks:
        print(f"--> Benchmarking: {task_name}")
        results[task_name] = {}
        for lang, cmd in cmds.items():
            ms, out = measure_command(cmd, reps=5)
            results[task_name][lang] = ms
            print(f"    [{lang:18s}] {ms:8.2f} ms  (Output: {out[:32]})")

    print("\n" + "="*110)
    print("LIVE AUDITED BENCHMARK RESULTS (Apple M2 ARM64 — Vir v2.2 vs Clang -O3 vs Rust -O3 vs Go)")
    print("="*110)
    print(f"{'Task / Benchmark':<30} | {'Vir (Native)':<13} | {'Clang -O3':<13} | {'Clang -O2':<13} | {'Rust -O3':<13} | {'Rust -O2':<13} | {'Go (gc)':<13}")
    print("-" * 110)
    for task_name, data in results.items():
        v_vir = f"{data['Vir']:.2f} ms"
        v_c3 = f"{data['C (Clang -O3)']:.2f} ms"
        v_c2 = f"{data['C (Clang -O2)']:.2f} ms"
        v_r3 = f"{data['Rust (-O3 LTO)']:.2f} ms"
        v_r2 = f"{data['Rust (-O2)']:.2f} ms"
        v_go = f"{data['Go (gc)']:.2f} ms"
        print(f"{task_name:<30} | {v_vir:<13} | {v_c3:<13} | {v_c2:<13} | {v_r3:<13} | {v_r2:<13} | {v_go:<13}")
    print("="*110)

if __name__ == "__main__":
    main()
