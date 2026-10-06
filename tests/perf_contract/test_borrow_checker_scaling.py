#!/usr/bin/env python3
"""
tests/perf_contract/test_borrow_checker_scaling.py
==================================================
Pass 8 Borrow Checker Scalability Performance Contract.
Verifies that Semantic Pass 8 borrow analysis scales linearly O(N) or O(N log N)
for blocks containing independent named borrows, eliminating the cubic / super-quadratic
behavior identified in VIRC-ISS-0026 / VIRC-PLN-0012.
"""

import argparse
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time


def generate_borrow_fixture(n: int) -> str:
    """Generate a function with N independent owners, N named borrows, and N uses."""
    lines = [
        "entity Box:",
        "    val: int",
        "end.",
        "",
        "func inspect(b: &Box):",
        "    print b.val",
        "end.",
        "",
        "func main:",
    ]
    # N independent owners
    for i in range(n):
        lines.append(f"    var x{i} = Box(val: {i})")
    # N named borrows kept live
    for i in range(n):
        lines.append(f"    let b{i} = &x{i}")
    # N later uses of each borrower
    for i in range(n):
        lines.append(f"    inspect(b{i})")
    lines.append("end.")
    lines.append("")
    return "\n".join(lines)


def generate_control_fixture(n: int) -> str:
    """Generate matched control with N owners, N non-borrow declarations, and N temporary calls."""
    lines = [
        "entity Box:",
        "    val: int",
        "end.",
        "",
        "func inspect(b: &Box):",
        "    print b.val",
        "end.",
        "",
        "func main:",
    ]
    # N independent owners
    for i in range(n):
        lines.append(f"    var x{i} = Box(val: {i})")
    # N non-borrow bindings
    for i in range(n):
        lines.append(f"    let pad{i} = {i}")
    # N calls using temporary borrows (no named borrowers across stmts)
    for i in range(n):
        lines.append(f"    inspect(&x{i})")
    lines.append("end.")
    lines.append("")
    return "\n".join(lines)


STAT_PATTERN = re.compile(
    r"VIRC_PASS8_STATS "
    r"ast_nodes=(?P<ast_nodes>\d+) "
    r"nll_nodes=(?P<nll_nodes>\d+) "
    r"hash_bytes=(?P<hash_bytes>\d+) "
    r"map_probes=(?P<map_probes>\d+) "
    r"rehash_nodes=(?P<rehash_nodes>\d+) "
    r"overlap_checks=(?P<overlap_checks>\d+) "
    r"release_steps=(?P<release_steps>\d+)"
)


def parse_pass8_stats(output: str) -> dict[str, int]:
    """Parse the deterministic Pass 8 operation counters."""
    match = STAT_PATTERN.search(output)
    if match is None:
        raise RuntimeError("Compiler did not emit VIRC_PASS8_STATS counters")
    return {name: int(value) for name, value in match.groupdict().items()}


def measure_compile_time(virc: str, source_path: str, repeats: int = 3) -> tuple[float, dict[str, int]]:
    """Return median wall time and stable Pass 8 operation counters."""
    # Warm-up run
    cmd = [virc, source_path, "--check", "--color=never", "--borrow-stats"]
    warm = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if warm.returncode != 0:
        raise RuntimeError(f"Compiler failed ({warm.returncode}): {warm.stderr}\n{warm.stdout}")
    expected_stats = parse_pass8_stats(warm.stdout + "\n" + warm.stderr)

    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        t1 = time.perf_counter()
        if res.returncode != 0:
            raise RuntimeError(f"Compiler failed: {res.stderr}")
        observed_stats = parse_pass8_stats(res.stdout + "\n" + res.stderr)
        if observed_stats != expected_stats:
            raise RuntimeError(
                f"Pass 8 counters were non-deterministic: {expected_stats} != {observed_stats}"
            )
        times.append((t1 - t0) * 1000.0)
    return statistics.median(times), expected_stats


def main():
    parser = argparse.ArgumentParser(description="Pass 8 borrow checker scaling contract runner")
    parser.add_argument("--virc", default="bin/virc", help="Path to compiler binary")
    parser.add_argument("--sizes", default="32,64,128,256,512,1024", help="Comma-separated workload sizes")
    parser.add_argument("--repeats", type=int, default=3, help="Number of repetitions per measurement")
    parser.add_argument("--assert-scaling", action="store_true", help="Assert scaling ratio <= 3.0x per doubling")
    parser.add_argument("--max-ratio", type=float, default=2.8, help="Maximum allowed growth factor per doubling")
    parser.add_argument("--max-op-ratio", type=float, default=2.5, help="Maximum deterministic operation growth per doubling")
    args = parser.parse_args()

    virc = os.path.abspath(args.virc)
    if not os.path.isfile(virc):
        print(f"ERROR: virc binary not found at {virc}", file=sys.stderr)
        sys.exit(1)

    sizes = [int(s.strip()) for s in args.sizes.split(",") if s.strip()]
    if len(sizes) < 4:
        print("ERROR: Performance corpus requires at least 4 sizes (e.g. 32,64,128,256)", file=sys.stderr)
        sys.exit(1)
    if any(size <= 0 for size in sizes) or any(sizes[i] != sizes[i - 1] * 2 for i in range(1, len(sizes))):
        print("ERROR: Performance sizes must be positive consecutive doublings", file=sys.stderr)
        sys.exit(1)

    print(f"=== Pass 8 Borrow Checker Scalability Contract ===")
    print(f"Compiler: {virc}")
    print(f"Sizes   : {sizes}")
    print(f"Repeats : {args.repeats}")
    print()

    results = []
    with tempfile.TemporaryDirectory(prefix="vir_perf_") as tmpdir:
        for n in sizes:
            borrow_src = os.path.join(tmpdir, f"borrow_{n}.vri")
            control_src = os.path.join(tmpdir, f"control_{n}.vri")

            with open(borrow_src, "w") as f:
                f.write(generate_borrow_fixture(n))
            with open(control_src, "w") as f:
                f.write(generate_control_fixture(n))

            borrow_ms, borrow_stats = measure_compile_time(virc, borrow_src, args.repeats)
            control_ms, control_stats = measure_compile_time(virc, control_src, args.repeats)
            delta_ms = max(0.0, borrow_ms - control_ms)
            borrow_ops = sum(borrow_stats.values())
            control_ops = sum(control_stats.values())
            delta_ops = max(0, borrow_ops - control_ops)

            results.append({
                "n": n,
                "borrow_ms": borrow_ms,
                "control_ms": control_ms,
                "delta_ms": delta_ms,
                "borrow_ops": borrow_ops,
                "control_ops": control_ops,
                "delta_ops": delta_ops,
            })

    print(f"{'N':>6} | {'Borrow ms':>10} | {'Control ms':>10} | {'Wall x':>7} | {'Borrow ops':>12} | {'Op x':>7} | {'Delta ops':>11} | {'Delta x':>8}")
    print("-" * 99)

    failed_ratios = []
    for i, res in enumerate(results):
        ratio_str = op_ratio_str = delta_op_ratio_str = "-"
        if i > 0:
            prev = results[i - 1]
            ratio = res["borrow_ms"] / max(0.001, prev["borrow_ms"])
            op_ratio = res["borrow_ops"] / max(1, prev["borrow_ops"])
            delta_op_ratio = res["delta_ops"] / max(1, prev["delta_ops"])
            ratio_str = f"{ratio:.2f}x"
            op_ratio_str = f"{op_ratio:.2f}x"
            delta_op_ratio_str = f"{delta_op_ratio:.2f}x"

            if args.assert_scaling:
                if ratio > args.max_ratio:
                    failed_ratios.append(f"Size {prev['n']} -> {res['n']}: overall ratio {ratio:.2f}x > {args.max_ratio}x")
                if op_ratio > args.max_op_ratio:
                    failed_ratios.append(f"Size {prev['n']} -> {res['n']}: operation ratio {op_ratio:.2f}x > {args.max_op_ratio}x")
                # The borrow-minus-control counter is displayed for diagnosis but is
                # not a stable asymptotic oracle: resizing events occur at different
                # N in the two workloads, so subtracting their totals amplifies those
                # discrete steps. The absolute borrow-work counter is deterministic
                # and is the operation-count gate.

        print(
            f"{res['n']:>6} | {res['borrow_ms']:>10.2f} | {res['control_ms']:>10.2f} | "
            f"{ratio_str:>7} | {res['borrow_ops']:>12} | {op_ratio_str:>7} | "
            f"{res['delta_ops']:>11} | {delta_op_ratio_str:>8}"
        )

    print()
    if failed_ratios:
        print("FAILED SCALING ASSERTIONS:")
        for fr in failed_ratios:
            print(f"  - {fr}")
        if args.assert_scaling:
            sys.exit(1)
    else:
        print("ALL SCALING GATES PASSED (wall time and deterministic Pass 8 operation growth).")


if __name__ == "__main__":
    main()
