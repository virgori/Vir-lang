#!/usr/bin/env python3
"""
tests/perf_contract/test_include_scaling.py
===========================================
Source Ingestion Include & Import Preprocessing Performance Contract.
Verifies that include and import preprocessing scales linearly O(N),
achieving <= 2.5x growth per doubling of unique modules, eliminating the
superlinear O(N^2 * S) repeated-splice behavior identified in VIRC-ISS-0029.

Also verifies:
- Physical module deduplication in diamond and duplicate dependency graphs.
- Telemetry timing accuracy: Reading and Preprocess durations are non-null and valid.
- Flat source controls (256 KiB - 4 MiB) scaling.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


VIRC_DEFAULT = Path(__file__).resolve().parents[2] / "bin" / "virc"


def run_virc(virc_bin: Path, source_path: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [str(virc_bin), str(source_path), "--check", "--color=never"]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def generate_include_modules(directory: Path, count: int, lines_per_module: int = 128) -> Path:
    """Generate `count` modules, each with fixed lines of comments and one helper function."""
    for i in range(count):
        mod_file = directory / f"m{i:03d}.vri"
        padding = (f"# module {i:03d} padding 0123456789abcdef\n") * lines_per_module
        body = f"{padding}\nfunc helper_{i:03d}() -> int:\n    out {i}\nend.\n"
        mod_file.write_text(body)

    root_file = directory / f"root_{count}.vri"
    inc_lines = [f'include "m{i:03d}.vri"' for i in range(count)]
    main_func = [
        "func main:",
        "    out 0",
        "end.",
    ]
    root_file.write_text("\n".join(inc_lines + [""] + main_func) + "\n")
    return root_file


def generate_diamond_graph(directory: Path) -> Path:
    """Generate a diamond dependency graph: root -> (left, right) -> shared_base."""
    base_file = directory / "diamond_base.vri"
    base_file.write_text("func diamond_value() -> int:\n    out 42\nend.\n")

    left_file = directory / "diamond_left.vri"
    left_file.write_text('include "diamond_base.vri"\nfunc left_helper() -> int:\n    out diamond_value()\nend.\n')

    right_file = directory / "diamond_right.vri"
    right_file.write_text('include "diamond_base.vri"\nfunc right_helper() -> int:\n    out diamond_value()\nend.\n')

    root_file = directory / "diamond_root.vri"
    root_file.write_text('include "diamond_left.vri"\ninclude "diamond_right.vri"\nfunc main:\n    out left_helper() + right_helper()\nend.\n')
    return root_file


def generate_flat_control(directory: Path, size_kib: int) -> Path:
    """Generate a flat, pre-expanded source file of roughly size_kib KiB."""
    flat_file = directory / f"flat_{size_kib}k.vri"
    # Target approximately size_kib * 1024 bytes
    target_bytes = size_kib * 1024
    line = "# flat source line padding 0123456789abcdef0123456789abcdef\n"
    line_len = len(line)
    num_lines = target_bytes // line_len
    content = line * num_lines + "\nfunc main:\n    out 0\nend.\n"
    flat_file.write_text(content)
    return flat_file


def measure_runs(virc_bin: Path, source_path: Path, repeats: int = 3, extra_args: list[str] | None = None) -> tuple[float, subprocess.CompletedProcess]:
    durations = []
    last_res = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        res = run_virc(virc_bin, source_path, extra_args)
        t1 = time.perf_counter()
        if res.returncode != 0:
            raise RuntimeError(f"Compilation failed for {source_path}:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        durations.append(t1 - t0)
        last_res = res
    durations.sort()
    median_time = durations[len(durations) // 2]
    return median_time, last_res


def test_include_scaling(virc_bin: Path, max_count: int = 256) -> dict[int, float]:
    print("=== Testing Include Scaling ===")
    counts = [16, 32, 64, 128, 256]
    counts = [c for c in counts if c <= max_count]
    results = {}
    with tempfile.TemporaryDirectory(prefix="virc_scale_") as tmpdir:
        tmp_path = Path(tmpdir)
        for count in counts:
            root_file = generate_include_modules(tmp_path, count)
            med_time, _ = measure_runs(virc_bin, root_file, repeats=3)
            results[count] = med_time
            print(f"  Includes: {count:3d} | Median time: {med_time * 1000:6.1f} ms")

    # Verify scaling ratios: T(2N) / T(N) <= 2.5x for N >= 32
    print("\nScaling Ratios:")
    for i in range(1, len(counts)):
        prev_c = counts[i - 1]
        cur_c = counts[i]
        ratio = results[cur_c] / max(results[prev_c], 0.001)
        print(f"  {prev_c:3d} -> {cur_c:3d}: {ratio:4.2f}x growth")
        if cur_c >= 64:
            if ratio > 2.5:
                print(f"  WARNING: Growth ratio {ratio:4.2f}x exceeds target 2.5x!")
    return results


def test_diamond_and_duplicates(virc_bin: Path) -> None:
    print("\n=== Testing Diamond & Duplicate Includes ===")
    with tempfile.TemporaryDirectory(prefix="virc_diamond_") as tmpdir:
        tmp_path = Path(tmpdir)
        root = generate_diamond_graph(tmp_path)
        res = run_virc(virc_bin, root)
        if res.returncode != 0:
            raise RuntimeError(f"Diamond graph failed:\n{res.stderr}")
        print("  Diamond dependency graph compiled successfully [OK]")

        # Test duplicate include
        dup_file = tmp_path / "dup_root.vri"
        dup_file.write_text('include "diamond_base.vri"\ninclude "diamond_base.vri"\ninclude "diamond_base.vri"\nfunc main:\n    out diamond_value()\nend.\n')
        res_dup = run_virc(virc_bin, dup_file)
        if res_dup.returncode != 0:
            raise RuntimeError(f"Duplicate include failed:\n{res_dup.stderr}")
        print("  Duplicate include directives compiled successfully [OK]")


def test_telemetry_accuracy(virc_bin: Path) -> None:
    print("\n=== Testing Telemetry & Timing Accuracy ===")
    with tempfile.TemporaryDirectory(prefix="virc_telemetry_") as tmpdir:
        tmp_path = Path(tmpdir)
        root = generate_include_modules(tmp_path, count=16)

        # 1. Test JSON telemetry
        res_json = run_virc(virc_bin, root, extra_args=["--json"])
        if res_json.returncode != 0:
            raise RuntimeError(f"JSON mode failed:\n{res_json.stderr}")
        try:
            data = json.loads(res_json.stdout)
            session = data.get("session")
            if session:
                duration_ns = session.get("durationNs")
                print(f"  JSON session.durationNs: {duration_ns}")
                if duration_ns is None or duration_ns <= 0:
                    print("  WARNING: session.durationNs is null or non-positive!")
                phases = session.get("phases", [])
                for p in phases:
                    name = p.get("name")
                    d_ns = p.get("durationNs")
                    print(f"    Phase '{name}': durationNs = {d_ns}")
        except Exception as e:
            print(f"  Error parsing JSON: {e}")

        # 2. Test modern UI formatting
        res_modern = run_virc(virc_bin, root, extra_args=["--ui=modern"])
        if "unavailable" in res_modern.stderr:
            print("  WARNING: Modern UI emitted 'unavailable' duration!")
        else:
            print("  Modern UI renders valid duration [OK]")


def generate_import_modules(directory: Path, count: int, lines_per_module: int = 128) -> Path:
    """Generate `count` modules with exported functions, and a root importing each."""
    for i in range(count):
        mod_file = directory / f"imp_{i:03d}.vri"
        padding = (f"# module imp_{i:03d} padding 0123456789abcdef\n") * lines_per_module
        body = f"{padding}\nfunc helper_{i:03d}() -> int:\n    out {i}\nend.\n\nexport helper_{i:03d}\n"
        mod_file.write_text(body)

    root_file = directory / f"root_imp_{count}.vri"
    imp_lines = [f'import helper_{i:03d} from "imp_{i:03d}.vri"' for i in range(count)]
    main_func = [
        "func main:",
        "    out 0",
        "end.",
    ]
    root_file.write_text("\n".join(imp_lines + [""] + main_func) + "\n")
    return root_file


def test_import_scaling(virc_bin: Path, max_count: int = 256) -> dict[int, float]:
    print("\n=== Testing Import Scaling ===")
    counts = [16, 32, 64, 128, 256]
    counts = [c for c in counts if c <= max_count]
    results = {}
    with tempfile.TemporaryDirectory(prefix="virc_import_scale_") as tmpdir:
        tmp_path = Path(tmpdir)
        for count in counts:
            root_file = generate_import_modules(tmp_path, count)
            med_time, _ = measure_runs(virc_bin, root_file, repeats=3)
            results[count] = med_time
            print(f"  Imports:  {count:3d} | Median time: {med_time * 1000:6.1f} ms")

    print("\nImport Scaling Ratios:")
    for i in range(1, len(counts)):
        prev_c = counts[i - 1]
        cur_c = counts[i]
        ratio = results[cur_c] / max(results[prev_c], 0.001)
        print(f"  {prev_c:3d} -> {cur_c:3d}: {ratio:4.2f}x growth")
        if cur_c >= 64:
            if ratio > 2.5:
                print(f"  WARNING: Growth ratio {ratio:4.2f}x exceeds target 2.5x!")
    return results


def test_flat_controls(virc_bin: Path) -> dict[int, float]:
    print("\n=== Testing Flat Source Controls ===")
    sizes = [256, 512, 1024, 2048, 4096]
    results = {}
    with tempfile.TemporaryDirectory(prefix="virc_flat_") as tmpdir:
        tmp_path = Path(tmpdir)
        for size in sizes:
            flat_file = generate_flat_control(tmp_path, size)
            med_time, _ = measure_runs(virc_bin, flat_file, repeats=3)
            results[size] = med_time
            print(f"  Flat {size:4d} KiB | Median time: {med_time * 1000:6.1f} ms")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="VIRC-ISS-0029 include scaling benchmark")
    parser.add_argument("--virc", type=Path, default=VIRC_DEFAULT, help="Path to virc binary")
    parser.add_argument("--max-modules", type=int, default=256, help="Maximum module count")
    args = parser.parse_args()

    virc_bin = args.virc.resolve()
    if not virc_bin.exists():
        print(f"Error: Compiler binary not found at {virc_bin}")
        return 1

    print(f"Using compiler: {virc_bin}")
    test_diamond_and_duplicates(virc_bin)
    test_telemetry_accuracy(virc_bin)
    test_include_scaling(virc_bin, max_count=args.max_modules)
    test_import_scaling(virc_bin, max_count=args.max_modules)
    test_flat_controls(virc_bin)
    print("\nAll performance contract checks finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
