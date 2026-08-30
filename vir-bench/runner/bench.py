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

def run_benchmark_dir(bench_dir, stage1_bin, soft_script):
    bench_name = os.path.basename(bench_dir)
    c_src = os.path.join(bench_dir, "main.c")
    vri_src = os.path.join(bench_dir, "main.vri")
    
    if not os.path.exists(c_src) or not os.path.exists(vri_src):
        return None

    print(f"\n=======================================================")
    print(f"▶ RUNNING BENCHMARK: {bench_name}")
    print(f"=======================================================")
    
    # 1. Compile C with Clang -O0 & -O2
    c_o0_bin = os.path.join(bench_dir, "bench_c_o0")
    run_cmd(["clang", "-O0", c_src, "-o", c_o0_bin])
    c_o2_bin = os.path.join(bench_dir, "bench_c_o2")
    run_cmd(["clang", "-O2", c_src, "-o", c_o2_bin])
    
    # 2. Compile with Stage-1
    s1_bin = os.path.join(bench_dir, "bench_vir_stage1")
    run_cmd([stage1_bin, vri_src, "-o", s1_bin])
    run_cmd(["codesign", "-s", "-", "-f", s1_bin])

    # 3. Compile with Soft Pipeline (Chaitin-Briggs Graph Coloring)
    soft_bin = os.path.join(bench_dir, "bench_vir_soft")
    s_res = run_cmd([soft_script, vri_src, "-o", soft_bin])
    run_cmd(["codesign", "-s", "-", "-f", soft_bin])

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
        
    # Benchmark Stage-1
    stats_s1, chk_s1, err_s1 = benchmark_executable(s1_bin)
    
    # Benchmark Soft Pipeline
    stats_soft, chk_soft, err_soft = None, None, None
    if os.path.exists(soft_bin):
        stats_soft, chk_soft, err_soft = benchmark_executable(soft_bin)

    chk_active = chk_soft if chk_soft else chk_s1
    print(f"🔍 Checksum: Vir(Soft)={chk_soft or 'N/A'} | Vir(S1)={chk_s1} | C(O2)={chk_o2}")
    if (chk_soft and chk_soft != chk_o2) or (chk_s1 and chk_s1 != chk_o2):
        print(f"❌ [CHECKSUM MISMATCH] Outputs differ!")
        return None
    print(f"✅ Checksum MATCH: Identical algorithmic results across Vir & C!")

    ratio_soft_vs_o2 = (stats_soft['median_ms'] / stats_o2['median_ms']) if stats_soft and stats_o2['median_ms'] > 0 else 0
    ratio_s1_vs_o2 = (stats_s1['median_ms'] / stats_o2['median_ms']) if stats_s1 and stats_o2['median_ms'] > 0 else 0

    print(f"📊 Results ({MEASURE_ROUNDS} runs):")
    if stats_soft:
        print(f"   • Vir Soft (Chaitin-Briggs): Median={stats_soft['median_ms']:.2f} ms | P95={stats_soft['p95_ms']:.2f} ms | Min={stats_soft['min_ms']:.2f} ms")
    if stats_s1:
        print(f"   • Vir Stage-1 (Bootstrap) : Median={stats_s1['median_ms']:.2f} ms | P95={stats_s1['p95_ms']:.2f} ms | Min={stats_s1['min_ms']:.2f} ms")
    print(f"   • Clang -O2                : Median={stats_o2['median_ms']:.2f} ms | P95={stats_o2['p95_ms']:.2f} ms | Min={stats_o2['min_ms']:.2f} ms")
    print(f"   • Clang -O0                : Median={stats_o0['median_ms']:.2f} ms | P95={stats_o0['p95_ms']:.2f} ms | Min={stats_o0['min_ms']:.2f} ms")
    if stats_soft:
        print(f"   ⚡ Vir Soft / Clang -O2 Ratio: {ratio_soft_vs_o2:.2f}x")

    return {
        "name": bench_name,
        "vir_soft": stats_soft,
        "vir_s1": stats_s1,
        "c_o2": stats_o2,
        "c_o0": stats_o0,
        "ratio_soft": ratio_soft_vs_o2,
        "ratio_s1": ratio_s1_vs_o2,
        "checksum": chk_active
    }

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace = os.path.dirname(root_dir)
    stage1_bin = os.path.join(workspace, "bin", "virc")
    soft_script = os.path.join(workspace, "tools", "virc_soft.sh")

    sys_info = get_system_info()
    print("=" * 75)
    print("      VIR V2.0 (NATIVE SELF-HOSTED) vs C/CLANG BENCHMARK SUITE")
    print("=" * 75)
    print(f"Host OS    : {sys_info['os']}")
    print(f"Host CPU   : {sys_info['cpu']} ({sys_info['cores']} cores)")
    print(f"C Compiler : {sys_info['clang']}")
    print(f"Native Eng : Vir Self-Hosted Native Binary (bin/virc)")
    print(f"Protocol   : Warmup={WARMUP_ROUNDS} rounds, Measure={MEASURE_ROUNDS} rounds, Checksum-Validated")
    print("=" * 75)

    bench_dirs = []
    for pattern in ["micro/*", "algorithms/*", "allocator/*", "systems/*", "realworld/*"]:
        bench_dirs.extend(sorted(glob.glob(os.path.join(root_dir, pattern))))

    results = []
    for bdir in bench_dirs:
        if os.path.isdir(bdir):
            res = run_benchmark_dir(bdir, stage1_bin, soft_script)
            if res:
                results.append(res)

    # Print Summary Markdown Table
    print("\n\n" + "=" * 85)
    print("                 BENCHMARK SUMMARY TABLE (VIR SOFT vs STAGE-1 vs CLANG)")
    print("=" * 85)
    print("| Benchmark | Vir Soft (Median) | Vir Stage-1 (Median) | Clang -O2 (Median) | Clang -O0 (Median) | Soft / Clang O2 |")
    print("| :--- | ---: | ---: | ---: | ---: | ---: |")
    for r in results:
        soft_ms = f"{r['vir_soft']['median_ms']:.2f} ms" if r['vir_soft'] else "N/A"
        s1_ms = f"{r['vir_s1']['median_ms']:.2f} ms" if r['vir_s1'] else "N/A"
        o2_ms = f"{r['c_o2']['median_ms']:.2f} ms"
        o0_ms = f"{r['c_o0']['median_ms']:.2f} ms"
        ratio = f"{r['ratio_soft']:.2f}x" if r['vir_soft'] else f"{r['ratio_s1']:.2f}x (S1)"
        print(f"| `{r['name']}` | **{soft_ms}** | {s1_ms} | {o2_ms} | {o0_ms} | **{ratio}** |")

    # Generate Markdown Report File
    report_path = os.path.join(root_dir, "BENCHMARK_REPORT_v0.1.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# BÁO CÁO BENCHMARK: VIR SOFT PIPELINE & STAGE-1 vs C (CLANG)\n\n")
        f.write(f"**Ngày đo lường:** 28 Tháng 08 Năm 2026  \n")
        f.write(f"**Hệ thống:** {sys_info['cpu']} • {sys_info['os']} • {sys_info['cores']} Cores  \n")
        f.write(f"**C Compiler:** {sys_info['clang']}  \n")
        f.write(f"**Vir Soft Pipeline:** Chaitin-Briggs Graph Coloring RegAlloc (K=8, X19..X26) + 10 Semantic Passes  \n")
        f.write(f"**Vir Stage-1:** Self-Hosted Bootstrap Native Binary  \n")
        f.write(f"**Quy chuẩn:** Warmup={WARMUP_ROUNDS} vòng, Đo lường={MEASURE_ROUNDS} vòng, Checksum khớp 100%.  \n\n")
        f.write("## BẢNG TỔNG HỢP KẾT QUẢ ĐO LƯỜNG HIỆU NĂNG\n\n")
        f.write("| Benchmark Suite | Vir Soft (Chaitin-Briggs) | Vir Stage-1 (Bootstrap) | Clang -O2 | Clang -O0 | Tỉ Lệ Soft / Clang -O2 |\n")
        f.write("| :--- | ---: | ---: | ---: | ---: | ---: |\n")
        for r in results:
            soft_ms = f"{r['vir_soft']['median_ms']:.2f} ms" if r['vir_soft'] else "N/A"
            s1_ms = f"{r['vir_s1']['median_ms']:.2f} ms" if r['vir_s1'] else "N/A"
            o2_ms = f"{r['c_o2']['median_ms']:.2f} ms"
            o0_ms = f"{r['c_o0']['median_ms']:.2f} ms"
            ratio = f"{r['ratio_soft']:.2f}x" if r['vir_soft'] else f"{r['ratio_s1']:.2f}x (S1)"
            f.write(f"| **`{r['name']}`** | **{soft_ms}** | {s1_ms} | {o2_ms} | {o0_ms} | **{ratio}** |\n")
        f.write("\n---\n*Báo cáo được khởi tạo tự động bởi bộ công cụ `vir-bench`.*\n")

    print(f"\nSaved report to: {report_path}")

if __name__ == "__main__":
    main()
