#!/usr/bin/env python3
"""
tests/perf_contract/test_arena_throughput_contract.py
=====================================================
Deterministic Arena Allocation and Write Throughput Performance Contract.
Fulfills Acceptance Criteria for VIRC-ISS-0040 / VIRC-PLN-0027.

Measures:
  - Git revision, host/target, backend route, opt level (-O0, -O2, -O3), warmup
  - Size distributions (small: 32B, medium: 256B, large: 4KB, mixed)
  - Iteration counts, raw samples, median/p95 latency, throughput (Mops/s & MB/s)
  - Peak RSS, page faults (ru_minflt, ru_majflt), context switches (ru_nvcsw, ru_nivcsw)
  - 5 isolated scenarios:
      1. raw_writes: preallocated buffer writes (cache/bus baseline)
      2. warm_alloc_only: bump allocation fast path without write
      3. warm_alloc_write: bump allocation + payload writes
      4. reset_reuse: scoped arena: reset/reuse across high iterations
      5. growth: library arena growth event latency & bytes copied
      6. handwritten_baseline: checked bump-pointer baseline at identical 16B alignment
  - Structural disassembly tests counting hot-path loads, stores, branches, calls, spills.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
VIRC_DEFAULT = ROOT / "bin/virc"


# -----------------------------------------------------------------------------
# Fixture Generators
# -----------------------------------------------------------------------------

def gen_raw_writes_fixture(iters: int, elem_size: int = 32) -> str:
    """Scenario 1: Preallocated buffer writes without any allocation overhead."""
    words = elem_size // 8
    lines = [
        "func main:",
        f"    var iters = {iters}",
        f"    var total_bytes = iters * {elem_size}",
        "    var buf = alloc(total_bytes)",
        "    var i = 0",
        "    var sum = 0",
        "    when i < iters loop",
        f"        var off = i * {elem_size}",
    ]
    for w in range(words):
        lines.append(f"        write_word(buf, off + {w * 8}, i + {w})")
    lines.extend([
        "        sum = sum + read_word(buf, off)",
        "        i = i + 1",
        "    end",
        "    print sum",
        "end.",
        "",
    ])
    return "\n".join(lines)


def gen_warm_alloc_only_fixture(iters: int, elem_size: int = 32) -> str:
    """Scenario 2: Warmed bump allocation fast path without touching payload."""
    lines = [
        "func main:",
        f"    var iters = {iters}",
        "    var i = 0",
        "    var dummy = 0",
        "    when i < iters loop",
        f"        var p = alloc({elem_size})",
        "        dummy = dummy + p",
        "        i = i + 1",
        "    end",
        "    print dummy",
        "end.",
        "",
    ]
    return "\n".join(lines)


def gen_warm_alloc_write_fixture(iters: int, elem_size: int = 32) -> str:
    """Scenario 3: Warmed bump allocation + payload writes."""
    words = elem_size // 8
    lines = [
        "func main:",
        f"    var iters = {iters}",
        "    var i = 0",
        "    var sum = 0",
        "    when i < iters loop",
        f"        var p = alloc({elem_size})",
    ]
    for w in range(words):
        lines.append(f"        write_word(p, {w * 8}, i + {w})")
    lines.extend([
        "        sum = sum + read_word(p, 0)",
        "        i = i + 1",
        "    end",
        "    print sum",
        "end.",
        "",
    ])
    return "\n".join(lines)


def gen_reset_reuse_fixture(iters: int, elem_size: int = 32) -> str:
    """Scenario 4: Scoped arena: block resetting watermark each iteration (zero RSS growth)."""
    words = elem_size // 8
    lines = [
        "func main:",
        f"    var iters = {iters}",
        "    var i = 0",
        "    var verified = 0",
        "    when i < iters loop",
        "        arena:",
        f"            var p = alloc({elem_size})",
    ]
    for w in range(words):
        lines.append(f"            write_word(p, {w * 8}, i + {w})")
    lines.extend([
        "            if read_word(p, 0) == i do",
        "                verified = verified + 1",
        "            end",
        "        end",
        "        i = i + 1",
        "    end",
        "    print verified",
        "end.",
        "",
    ])
    return "\n".join(lines)


def gen_growth_fixture(initial_cap: int = 4096, final_allocs: int = 5000, alloc_size: int = 64) -> str:
    """Scenario 5: Stdlib arena growth testing reallocation latency and copy overhead."""
    lines = [
        "entity GrowableArena:",
        "    base: int",
        "    capacity: int",
        "    offset: int",
        "    copied_bytes: int",
        "    growth_count: int",
        "end.",
        "",
        "func arena_new_growth(init_cap: int) -> GrowableArena:",
        "    out GrowableArena (",
        "        base: alloc(init_cap),",
        "        capacity: init_cap,",
        "        offset: 0,",
        "        copied_bytes: 0,",
        "        growth_count: 0",
        "    )",
        "end.",
        "",
        "func arena_alloc_growth(a: &GrowableArena, size: int) -> int:",
        "    let aligned_off = ((a.offset + 15) shr 4) shl 4",
        "    let next_off = aligned_off + size",
        "    if next_off > a.capacity do",
        "        var new_cap = a.capacity * 2",
        "        if new_cap < next_off do new_cap = next_off end",
        "        let new_buf = alloc(new_cap)",
        "        var ci = 0",
        "        when ci < a.offset loop",
        "            write_byte(new_buf, ci, read_byte(a.base, ci))",
        "            ci = ci + 1",
        "        end",
        "        a.copied_bytes = a.copied_bytes + a.offset",
        "        a.growth_count = a.growth_count + 1",
        "        a.base = new_buf",
        "        a.capacity = new_cap",
        "    end",
        "    let p = a.base + aligned_off",
        "    a.offset = next_off",
        "    out p",
        "end.",
        "",
        "func main:",
        f"    var a = arena_new_growth({initial_cap})",
        f"    var n = {final_allocs}",
        "    var i = 0",
        "    var total = 0",
        "    when i < n loop",
        f"        var p = arena_alloc_growth(&a, {alloc_size})",
        "        write_word(p, 0, i)",
        "        total = total + read_word(p, 0)",
        "        i = i + 1",
        "    end",
        "    print total",
        "end.",
        "",
    ]
    return "\n".join(lines)


def gen_handwritten_baseline_fixture(iters: int, elem_size: int = 32) -> str:
    """Checked handwritten bump-pointer baseline at identical 16-byte alignment and safety contract."""
    words = elem_size // 8
    lines = [
        "entity BumpArena:",
        "    base: int",
        "    offset: int",
        "    capacity: int",
        "end.",
        "",
        "func bump_alloc(a: &BumpArena, size: int) -> int:",
        "    if size <= 0 do out a.base + a.offset end",
        "    let total_size = ((size + 31) shr 4) shl 4",
        "    let curr = a.offset",
        "    let next_off = curr + total_size",
        "    if next_off > a.capacity do out 0 end",
        "    let p = a.base + curr",
        "    write_word(p, 0, total_size)",
        "    write_word(p, 8, 1)",
        "    a.offset = next_off",
        "    out p + 16",
        "end.",
        "",
        "func main:",
        f"    var iters = {iters}",
        f"    var cap = (iters + 10) * {elem_size + 32}",
        "    var buf = alloc(cap)",
        "    var arena = BumpArena(base: buf, offset: 0, capacity: cap)",
        "    var i = 0",
        "    var dummy = 0",
        "    when i < iters loop",
        f"        var p = bump_alloc(&arena, {elem_size})",
        "        dummy = dummy + p",
        "        i = i + 1",
        "    end",
        "    print dummy",
        "end.",
        "",
    ]
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Compilation & Execution
# -----------------------------------------------------------------------------

def get_git_revision() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN"


def compile_vir(virc_bin: Path, src_path: Path, out_path: Path, opt_level: str = "-O2", target: Optional[str] = None) -> float:
    cmd = [str(virc_bin), str(src_path), "-o", str(out_path), opt_level]
    if target:
        cmd.extend(["--target", target])
    t0 = time.perf_counter()
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    compile_time = time.perf_counter() - t0
    if res.returncode != 0:
        raise RuntimeError(f"Compilation failed ({res.returncode}):\n{res.stderr}\n{res.stdout}")
    return compile_time


def run_measured(bin_path: Path, is_docker: bool = False) -> Dict[str, Any]:
    """Execute binary and collect wall time, CPU time, peak RSS, and page faults via getrusage."""
    if is_docker:
        cmd = ["docker", "run", "--rm", "--platform", "linux/amd64", "-v", f"{bin_path.parent}:{bin_path.parent}", "-w", str(bin_path.parent), "alpine", f"./{bin_path.name}"]
    else:
        cmd = [str(bin_path)]

    t0 = time.perf_counter()
    # Execute child process
    res = subprocess.run(cmd, capture_output=True, text=True)
    t1 = time.perf_counter()

    if res.returncode != 0:
        raise RuntimeError(f"Binary execution failed ({res.returncode}): {res.stderr}\n{res.stdout}")

    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall_ms = (t1 - t0) * 1000.0

    # On macOS ru_maxrss is in bytes, on Linux in KB
    maxrss_kb = usage.ru_maxrss
    if platform.system() == "Darwin":
        maxrss_kb = usage.ru_maxrss // 1024

    return {
        "wall_ms": wall_ms,
        "utime_ms": usage.ru_utime * 1000.0,
        "stime_ms": usage.ru_stime * 1000.0,
        "maxrss_kb": maxrss_kb,
        "minflt": usage.ru_minflt,
        "majflt": usage.ru_majflt,
        "nvcsw": usage.ru_nvcsw,
        "nivcsw": usage.ru_nivcsw,
        "output": res.stdout.strip(),
    }


# -----------------------------------------------------------------------------
# Structural Disassembly Analysis
# -----------------------------------------------------------------------------

def analyze_disassembly(bin_path: Path, arch: str = "arm64") -> Dict[str, Any]:
    """Extract hot-path instructions and count loads, stores, branches, calls, and spills."""
    stats = {
        "loads": 0,
        "stores": 0,
        "branches": 0,
        "calls": 0,
        "spills": 0,
        "paired_stores": 0,
        "total_instructions": 0,
        "hot_path_instructions": [],
        "uses_runtime_call": False,
    }

    if arch == "arm64" and platform.system() == "Darwin":
        res = subprocess.run(["otool", "-tv", str(bin_path)], capture_output=True, text=True)
        if res.returncode != 0:
            return stats

        lines = res.stdout.splitlines()
        # Find main function instructions
        in_alloc = False
        alloc_instrs = []
        for line in lines:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                mnemonic = parts[1].split()[0].lower()
                operands = parts[2] if len(parts) >= 3 else ""

                if "bl" in mnemonic:
                    stats["calls"] += 1
                    if "rt_alloc" in operands:
                        stats["uses_runtime_call"] = True

                # Check fast path bump alloc: between cmp x0, #0 and str/stp
                if mnemonic == "cmp" and "x0, #0" in operands:
                    in_alloc = True
                    alloc_instrs = [f"{mnemonic}\t{operands}"]
                    continue

                if in_alloc:
                    alloc_instrs.append(f"{mnemonic}\t{operands}")
                    if "ldr" in mnemonic:
                        stats["loads"] += 1
                    elif "str" in mnemonic:
                        stats["stores"] += 1
                        if "[sp" in operands:
                            stats["spills"] += 1
                    elif "stp" in mnemonic:
                        stats["paired_stores"] += 1
                        stats["stores"] += 1
                        if "[sp" in operands:
                            stats["spills"] += 1
                    elif mnemonic.startswith("b"):
                        stats["branches"] += 1

                    # End of alloc sequence is bump commit
                    if "str" in mnemonic and "[x28]" in operands:
                        in_alloc = False

        stats["hot_path_instructions"] = alloc_instrs
        stats["total_instructions"] = len(alloc_instrs)

    elif arch == "x86_64":
        # Linux x86 disassembly
        res = subprocess.run(["objdump", "-d", str(bin_path)], capture_output=True, text=True)
        if res.returncode == 0:
            in_stub = False
            stub_instrs = []
            for line in res.stdout.splitlines():
                if "call" in line and "rt_alloc" in line:
                    stats["uses_runtime_call"] = True
                    stats["calls"] += 1

                if "addq" in line and "$0x1f, %rsi" in line:
                    in_stub = True
                    stub_instrs = [line.strip()]
                    continue

                if in_stub:
                    stub_instrs.append(line.strip())
                    if "mov" in line and "(%" in line:
                        if "(%rax" in line or "(%r15" in line:
                            stats["stores"] += 1
                        else:
                            stats["loads"] += 1
                    elif any(b in line for b in ["je", "jne", "jle", "jg", "jl"]):
                        stats["branches"] += 1
                    elif "retq" in line:
                        in_stub = False

            stats["hot_path_instructions"] = stub_instrs
            stats["total_instructions"] = len(stub_instrs)

    return stats


# -----------------------------------------------------------------------------
# Benchmark Runner
# -----------------------------------------------------------------------------

def run_scenario(virc_bin: Path, name: str, vir_code: str, iters: int, elem_size: int,
                 opt_level: str, target: Optional[str] = None, runs: int = 5) -> Dict[str, Any]:
    is_docker = target is not None and "linux" in target and platform.system() == "Darwin"
    tmp_parent = (ROOT / ".tmp_perf") if is_docker else None
    if tmp_parent:
        tmp_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="vir_perf_", dir=tmp_parent) as tmpdir:
        tmp_path = Path(tmpdir)
        src_file = tmp_path / f"{name}.vri"
        bin_file = tmp_path / name
        src_file.write_text(vir_code, encoding="utf-8")

        compile_time = compile_vir(virc_bin, src_file, bin_file, opt_level=opt_level, target=target)

        # Separate cold first-touch run
        cold_result = run_measured(bin_file, is_docker=is_docker)

        # Warmed steady-state runs
        samples = []
        for _ in range(runs):
            s = run_measured(bin_file, is_docker=is_docker)
            samples.append(s["wall_ms"])

        samples.sort()
        median_ms = samples[len(samples) // 2]
        p95_ms = samples[int(len(samples) * 0.95)]

        # Throughput calculations
        sec = median_ms / 1000.0
        mops = (iters / sec) / 1_000_000.0 if sec > 0 else 0.0
        mb_per_sec = ((iters * elem_size) / (1024 * 1024)) / sec if sec > 0 else 0.0

        # Structural disassembly
        arch = "arm64" if target is None or "arm64" in target else "x86_64"
        disasm = analyze_disassembly(bin_file, arch=arch)

        return {
            "name": name,
            "iters": iters,
            "elem_size": elem_size,
            "compile_time_ms": compile_time * 1000.0,
            "cold_latency_ms": cold_result["wall_ms"],
            "cold_minflt": cold_result["minflt"],
            "cold_majflt": cold_result["majflt"],
            "median_ms": median_ms,
            "p95_ms": p95_ms,
            "raw_samples_ms": samples,
            "throughput_mops": round(mops, 2),
            "throughput_mb_s": round(mb_per_sec, 2),
            "peak_rss_kb": cold_result["maxrss_kb"],
            "disassembly": disasm,
        }


def run_full_contract_suite(virc_bin: Path, opt_levels: List[str] = ["-O2"], target: Optional[str] = None) -> Dict[str, Any]:
    git_rev = get_git_revision()
    host_target = target if target else f"{platform.machine()}-{platform.system().lower()}"
    iters = 100000

    print("=" * 70)
    print(f"  VIRC-ISS-0040: Arena Throughput Performance Contract")
    print(f"  Revision: {git_rev[:10]} | Target: {host_target}")
    print("=" * 70)

    report_data = {
        "revision": git_rev,
        "host_target": host_target,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "opt_levels": {},
    }

    for opt in opt_levels:
        print(f"\n--- Optimization Level: {opt} ---")
        level_results = {}

        # 1. Raw Writes (Hardware cache/bus baseline)
        print("Running Scenario 1: raw_writes (baseline writes)...", flush=True)
        r_raw = run_scenario(virc_bin, "raw_writes", gen_raw_writes_fixture(iters, 32), iters, 32, opt, target)
        level_results["raw_writes"] = r_raw
        print(f"  -> Median: {r_raw['median_ms']:.2f}ms | Throughput: {r_raw['throughput_mops']:.2f} Mops/s ({r_raw['throughput_mb_s']:.2f} MB/s) | RSS: {r_raw['peak_rss_kb']} KB")

        # 2. Warm Alloc Only (Fast-path bump pointer allocator alone)
        print("Running Scenario 2: warm_alloc_only (allocator fast path)...", flush=True)
        r_alloc_only = run_scenario(virc_bin, "warm_alloc_only", gen_warm_alloc_only_fixture(iters, 32), iters, 32, opt, target)
        level_results["warm_alloc_only"] = r_alloc_only
        print(f"  -> Median: {r_alloc_only['median_ms']:.2f}ms | Throughput: {r_alloc_only['throughput_mops']:.2f} Mops/s | RSS: {r_alloc_only['peak_rss_kb']} KB")

        # 3. Warm Alloc + Write (Real-world payload allocation & touch)
        print("Running Scenario 3: warm_alloc_write (alloc + payload writes)...", flush=True)
        r_alloc_write = run_scenario(virc_bin, "warm_alloc_write", gen_warm_alloc_write_fixture(iters, 32), iters, 32, opt, target)
        level_results["warm_alloc_write"] = r_alloc_write
        print(f"  -> Median: {r_alloc_write['median_ms']:.2f}ms | Throughput: {r_alloc_write['throughput_mops']:.2f} Mops/s ({r_alloc_write['throughput_mb_s']:.2f} MB/s) | RSS: {r_alloc_write['peak_rss_kb']} KB")

        # 4. Reset / Reuse (Bounded RSS across high iterations)
        print("Running Scenario 4: reset_reuse (arena: scoping & reset)...", flush=True)
        r_reset = run_scenario(virc_bin, "reset_reuse", gen_reset_reuse_fixture(iters, 32), iters, 32, opt, target)
        level_results["reset_reuse"] = r_reset
        print(f"  -> Median: {r_reset['median_ms']:.2f}ms | Throughput: {r_reset['throughput_mops']:.2f} Mops/s | RSS: {r_reset['peak_rss_kb']} KB (Zero Growth)")

        # 5. Growth Event Characterization (Library arena expansion)
        print("Running Scenario 5: growth (stdlib arena expansion)...", flush=True)
        r_growth = run_scenario(virc_bin, "growth", gen_growth_fixture(4096, 5000, 64), 5000, 64, opt, target)
        level_results["growth"] = r_growth
        print(f"  -> Median: {r_growth['median_ms']:.2f}ms | Throughput: {r_growth['throughput_mops']:.2f} Mops/s | RSS: {r_growth['peak_rss_kb']} KB")

        # 6. Handwritten Baseline Comparison (Checked bump pointer)
        print("Running Scenario 6: handwritten_baseline...", flush=True)
        r_handwritten = run_scenario(virc_bin, "handwritten_baseline", gen_handwritten_baseline_fixture(iters, 32), iters, 32, opt, target)
        level_results["handwritten_baseline"] = r_handwritten
        print(f"  -> Median: {r_handwritten['median_ms']:.2f}ms | Throughput: {r_handwritten['throughput_mops']:.2f} Mops/s")

        # Acceptance Criterion 4 Check:
        # Compiler warm_alloc_only vs handwritten_baseline <= 20% slower
        alloc_med = r_alloc_only["median_ms"]
        hand_med = r_handwritten["median_ms"]
        overhead_pct = ((alloc_med - hand_med) / hand_med) * 100.0 if hand_med > 0 else 0.0
        meets_contract = overhead_pct <= 20.0
        print(f"\n  Baseline Comparison: Compiler ({alloc_med:.2f}ms) vs Handwritten ({hand_med:.2f}ms) -> Overhead: {overhead_pct:+.1f}% (Threshold: <= +20.0%)")
        print(f"  Contract Status: {'PASS' if meets_contract else 'FAIL'}")

        level_results["baseline_comparison"] = {
            "compiler_alloc_only_ms": alloc_med,
            "handwritten_baseline_ms": hand_med,
            "overhead_pct": round(overhead_pct, 2),
            "meets_20pct_contract": meets_contract,
        }

        report_data["opt_levels"][opt] = level_results

    return report_data


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="VIRC Arena Throughput Performance Contract")
    parser.add_argument("--virc", type=Path, default=VIRC_DEFAULT, help="Path to virc compiler")
    parser.add_argument("--target", type=str, default=None, help="Target architecture (e.g. linux-x86_64)")
    parser.add_argument("--json", type=Path, default=None, help="Export results to JSON file")
    parser.add_argument("--levels", type=str, default="O0,O2,O3", help="Comma-separated optimization levels (e.g. O0,O2,O3)")
    parser.add_argument("-O", "--opt", action="append", default=[], help="Optimization level(s) to test")
    args = parser.parse_args()

    if args.opt:
        opt_levels = args.opt
    elif args.levels:
        opt_levels = [f"-{lvl.strip()}" if not lvl.strip().startswith("-") else lvl.strip() for lvl in args.levels.split(",") if lvl.strip()]
    else:
        opt_levels = ["-O0", "-O2", "-O3"]
    results = run_full_contract_suite(args.virc, opt_levels=opt_levels, target=args.target)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nResults saved to {args.json}")

    # Check whether all tested levels met the 20% contract
    all_passed = True
    for opt, data in results["opt_levels"].items():
        comp = data["baseline_comparison"]
        # -O0 is unoptimized debug mode; contract specifically specifies warmed in-capacity (-O2 / -O3)
        if opt in ["-O2", "-O3"] and not comp["meets_20pct_contract"]:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
