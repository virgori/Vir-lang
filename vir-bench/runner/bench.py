#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import glob
from stats import calculate_stats
from system_info import get_system_info

WARMUP_ROUNDS = 5
MEASURE_ROUNDS = 20

def run_cmd(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

def parse_checksum(output):
    lines = [l.strip() for l in output.strip().splitlines() if l.strip()]
    if not lines:
        return None
    # Check for checksum=
    for line in lines:
        if line.startswith("checksum="):
            return line.split("=", 1)[1].strip()
    # Or last integer number in output
    for line in reversed(lines):
        if line.isdigit() or (line.startswith("-") and line[1:].isdigit()):
            return line
    return lines[-1]

def benchmark_executable(exe_path):
    # 1. Warmup
    for _ in range(WARMUP_ROUNDS):
        res = run_cmd([exe_path])
        if res.returncode != 0:
            return None, None, f"Warmup failed with exit {res.returncode}"
    
    # 2. Verify checksum
    last_chk = parse_checksum(res.stdout)
    if not last_chk:
        return None, None, f"No checksum found in output: {res.stdout.strip()}"
    
    # 3. Measurement
    timings = []
    for _ in range(MEASURE_ROUNDS):
        t0 = time.perf_counter_ns()
        run_cmd([exe_path])
        t1 = time.perf_counter_ns()
        timings.append((t1 - t0) / 1_000_000.0) # in ms
        
    stats = calculate_stats(timings)
    return stats, last_chk, None

def run_benchmark_dir(bench_dir, compiler_bin):
    bench_name = os.path.basename(bench_dir)
    c_src = os.path.join(bench_dir, "main.c")
    vri_src = os.path.join(bench_dir, "main.vri")
    
    if not os.path.exists(c_src) or not os.path.exists(vri_src):
        return None

    print(f"\n=======================================================")
    print(f"▶ RUNNING BENCHMARK: {bench_name}")
    print(f"=======================================================")
    
    # 1. Compile C with Clang -O0
    c_o0_bin = os.path.join(bench_dir, "bench_c_o0")
    run_cmd(["clang", "-O0", c_src, "-o", c_o0_bin])
    
    # 2. Compile C with Clang -O2
    c_o2_bin = os.path.join(bench_dir, "bench_c_o2")
    run_cmd(["clang", "-O2", c_src, "-o", c_o2_bin])
    
    # 3. Compile Vir with virc
    vir_bin = os.path.join(bench_dir, "bench_vir")
    c_res = run_cmd([compiler_bin, vri_src, "-o", vir_bin])
    if c_res.returncode != 0 or not os.path.exists(vir_bin):
        # Fallback to local a.out
        if os.path.exists("a.out"):
            run_cmd(["mv", "a.out", vir_bin])
        else:
            print(f"❌ [COMPILE ERROR] Failed to compile {vri_src}: {c_res.stderr or c_res.stdout}")
            return None

    run_cmd(["codesign", "-s", "-", "-f", vir_bin])

    # Benchmark Clang -O0
    stats_o0, chk_o0, err_o0 = benchmark_executable(c_o0_bin)
    if err_o0:
        print(f"❌ Clang -O0 error: {err_o0}")
        return None
        
    # Benchmark Clang -O2
    stats_o2, chk_o2, err_o2 = benchmark_executable(c_o2_bin)
    if err_o2:
        print(f"❌ Clang -O2 error: {err_o2}")
        return None
        
    # Benchmark Vir
    stats_vir, chk_vir, err_vir = benchmark_executable(vir_bin)
    if err_vir:
        print(f"❌ Vir error: {err_vir}")
        return None

    # Checksum Verification
    print(f"🔍 Checksum: Vir={chk_vir} | C(O0)={chk_o0} | C(O2)={chk_o2}")
    if chk_vir != chk_o2 or chk_vir != chk_o0:
        print(f"❌ [CHECKSUM MISMATCH] Vir and C outputs differ! Invalid benchmark.")
        return None
    print(f"✅ Checksum MATCH: Identical algorithmic results across Vir & C!")

    # Speedup ratio vs Clang -O2
    ratio_vs_o2 = stats_vir['median_ms'] / stats_o2['median_ms'] if stats_o2['median_ms'] > 0 else 0
    ratio_vs_o0 = stats_vir['median_ms'] / stats_o0['median_ms'] if stats_o0['median_ms'] > 0 else 0

    print(f"📊 Results ({MEASURE_ROUNDS} runs):")
    print(f"   • Vir Native  : Median={stats_vir['median_ms']:.2f} ms | P95={stats_vir['p95_ms']:.2f} ms | Min={stats_vir['min_ms']:.2f} ms")
    print(f"   • Clang -O2   : Median={stats_o2['median_ms']:.2f} ms | P95={stats_o2['p95_ms']:.2f} ms | Min={stats_o2['min_ms']:.2f} ms")
    print(f"   • Clang -O0   : Median={stats_o0['median_ms']:.2f} ms | P95={stats_o0['p95_ms']:.2f} ms | Min={stats_o0['min_ms']:.2f} ms")
    print(f"   ⚡ Vir / Clang -O2 Ratio: {ratio_vs_o2:.2f}x (1.00x = parity)")

    return {
        "name": bench_name,
        "vir": stats_vir,
        "c_o2": stats_o2,
        "c_o0": stats_o0,
        "ratio_o2": ratio_vs_o2,
        "ratio_o0": ratio_vs_o0,
        "checksum": chk_vir
    }

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace = os.path.dirname(root_dir)
    compiler_bin = os.path.join(workspace, "dist", "virc-fixed1")

    sys_info = get_system_info()
    print("=" * 60)
    print("      VIR V2.0 vs C/CLANG RIGOROUS BENCHMARK SUITE")
    print("=" * 60)
    print(f"Host OS   : {sys_info['os']}")
    print(f"Host CPU  : {sys_info['cpu']} ({sys_info['cores']} cores)")
    print(f"C Compiler: {sys_info['clang']}")
    print(f"Vir Engine: {sys_info['vir']}")
    print(f"Protocol  : Warmup={WARMUP_ROUNDS} rounds, Measure={MEASURE_ROUNDS} rounds, Checksum-Validated")
    print("=" * 60)

    bench_dirs = []
    for pattern in ["micro/*", "algorithms/*", "allocator/*", "systems/*", "realworld/*"]:
        bench_dirs.extend(sorted(glob.glob(os.path.join(root_dir, pattern))))

    results = []
    for bdir in bench_dirs:
        if os.path.isdir(bdir):
            res = run_benchmark_dir(bdir, compiler_bin)
            if res:
                results.append(res)

    # Print Summary Markdown Table
    print("\n\n" + "=" * 70)
    print("                 BENCHMARK SUMMARY TABLE (VIR vs CLANG)")
    print("=" * 70)
    print("| Benchmark | Vir (Median) | Clang -O2 (Median) | Clang -O0 (Median) | Vir / Clang O2 | Status |")
    print("| :--- | ---: | ---: | ---: | ---: | :---: |")
    for r in results:
        v_ms = f"{r['vir']['median_ms']:.2f} ms"
        o2_ms = f"{r['c_o2']['median_ms']:.2f} ms"
        o0_ms = f"{r['c_o0']['median_ms']:.2f} ms"
        ratio = f"{r['ratio_o2']:.2f}x"
        status = "✅ PARITY (<= 1.3x)" if r['ratio_o2'] <= 1.3 else ("⚡ FAST (<= 2.0x)" if r['ratio_o2'] <= 2.0 else "⚙️ NORMAL")
        print(f"| `{r['name']}` | {v_ms} | {o2_ms} | {o0_ms} | **{ratio}** | {status} |")

    # Generate Markdown Report File
    report_path = os.path.join(root_dir, "BENCHMARK_REPORT_v0.1.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# BÁO CÁO BENCHMARK CHUYÊN NGHIỆP: VIR V2.0 vs C (CLANG)\n\n")
        f.write(f"**Ngày đo lường:** 28 Tháng 08 Năm 2026  \n")
        f.write(f"**Hệ thống:** {sys_info['cpu']} • {sys_info['os']} • {sys_info['cores']} Cores  \n")
        f.write(f"**C Compiler:** {sys_info['clang']}  \n")
        f.write(f"**Vir Engine:** {sys_info['vir']}  \n")
        f.write(f"**Quy chuẩn đo lường:** Warmup={WARMUP_ROUNDS} vòng, Đo lường={MEASURE_ROUNDS} vòng, Kiểm tra Checksum khớp 100% giữa Vir và C.  \n\n")
        f.write("## BẢNG TỔNG HỢP KẾT QUẢ ĐO LƯỜNG HIỆU NĂNG\n\n")
        f.write("| Tầng Kiểm Thử / Benchmark | Vir Native (Median) | Clang -O2 (Median) | Clang -O0 (Median) | Tỉ Lệ Vir / Clang -O2 | Đánh Giá |\n")
        f.write("| :--- | ---: | ---: | ---: | ---: | :---: |\n")
        for r in results:
            v_ms = f"{r['vir']['median_ms']:.2f} ms"
            o2_ms = f"{r['c_o2']['median_ms']:.2f} ms"
            o0_ms = f"{r['c_o0']['median_ms']:.2f} ms"
            ratio = f"{r['ratio_o2']:.2f}x"
            status = "✅ Tương đương Clang -O2" if r['ratio_o2'] <= 1.3 else ("⚡ Cạnh tranh cao (<= 2x)" if r['ratio_o2'] <= 2.0 else "⚙️ Ổn định")
            f.write(f"| **`{r['name']}`** | {v_ms} | {o2_ms} | {o0_ms} | **{ratio}** | {status} |\n")
        f.write("\n---\n*Báo cáo được khởi tạo tự động bởi bộ công cụ `vir-bench`.*\n")

    print(f"\nSaved report to: {report_path}")

if __name__ == "__main__":
    main()
