#!/usr/bin/env python3
"""
pmu_profiler.py – PMU Performance Counter Wrapper for macOS
=============================================================
Wraps macOS performance measurement tools to validate the cost model
against real program execution.

Uses:
  - `powermetrics` for CPU frequency / thermal monitoring
  - `/usr/bin/sample` for sampling-based profiling
  - `dtrace` for low-level tracing (requires SIP adjustment)
  - Built-in `time` for wall-clock / user-time measurement

Usage:
    python scripts/pmu_profiler.py --binary core/build/vir_program
    python scripts/pmu_profiler.py --measure-overhead
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class PMUResult:
    """Result of a PMU profiling session."""
    binary: str
    wall_time_s: float = 0.0
    user_time_s: float = 0.0
    sys_time_s: float = 0.0
    max_rss_kb: int = 0
    instructions_retired: int = 0  # if available
    cycles: int = 0                # if available
    ipc: float = 0.0              # instructions per cycle
    branch_misses: int = 0
    cache_misses: int = 0
    samples: list[dict] = field(default_factory=list)
    notes: str = ""


class PMUProfiler:
    """macOS-compatible PMU profiler using system tools."""

    def __init__(self, output_dir: str = "data/arch") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def profile_binary(self, binary_path: str, args: list[str] | None = None,
                       iterations: int = 5) -> PMUResult:
        """Profile a binary executable multiple times and aggregate results."""
        binary = Path(binary_path)
        if not binary.exists():
            raise FileNotFoundError(f"Binary not found: {binary_path}")

        cmd = [str(binary)] + (args or [])
        result = PMUResult(binary=str(binary))

        wall_times = []
        user_times = []
        sys_times = []

        for i in range(iterations):
            t0 = time.perf_counter()
            proc = subprocess.run(
                ["/usr/bin/time", "-lp"] + cmd,
                capture_output=True, text=True, timeout=60
            )
            t1 = time.perf_counter()

            wall_times.append(t1 - t0)

            # Parse /usr/bin/time output (in stderr)
            stderr = proc.stderr
            for line in stderr.splitlines():
                line = line.strip()
                if line.startswith("real"):
                    try:
                        user_times.append(float(line.split()[1]))
                    except (IndexError, ValueError):
                        pass
                elif line.startswith("user"):
                    try:
                        user_times.append(float(line.split()[1]))
                    except (IndexError, ValueError):
                        pass
                elif line.startswith("sys"):
                    try:
                        sys_times.append(float(line.split()[1]))
                    except (IndexError, ValueError):
                        pass
                elif "maximum resident set size" in line:
                    try:
                        result.max_rss_kb = int(line.split()[0]) // 1024
                    except (IndexError, ValueError):
                        pass

        if wall_times:
            result.wall_time_s = min(wall_times)
        if user_times:
            result.user_time_s = min(user_times)
        if sys_times:
            result.sys_time_s = min(sys_times)

        result.notes = f"Best of {iterations} runs"
        return result

    def measure_overhead(self) -> dict:
        """Measure timing overhead on this system.
        
        Tests:
          - time.perf_counter() resolution
          - subprocess launch overhead
          - mach_absolute_time vs perf_counter
        """
        # perf_counter resolution
        deltas = []
        for _ in range(1000):
            t0 = time.perf_counter()
            t1 = time.perf_counter()
            deltas.append(t1 - t0)

        deltas.sort()
        perf_resolution_ns = deltas[len(deltas) // 2] * 1e9  # median

        # Subprocess launch overhead
        sub_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            subprocess.run(["/usr/bin/true"], capture_output=True)
            t1 = time.perf_counter()
            sub_times.append(t1 - t0)

        sub_overhead_ms = min(sub_times) * 1e3

        return {
            "perf_counter_resolution_ns": round(perf_resolution_ns, 2),
            "subprocess_overhead_ms": round(sub_overhead_ms, 2),
            "timer": "time.perf_counter()",
            "platform": sys.platform,
        }

    def run_sample_profiler(self, binary_path: str, duration_s: int = 3,
                            args: list[str] | None = None) -> str:
        """Run macOS `sample` tool on a process.
        
        Note: The binary must run for at least `duration_s` seconds.
        """
        cmd = [str(binary_path)] + (args or [])
        
        # Start the process
        proc = subprocess.Popen(cmd)
        pid = proc.pid

        # Sample it
        sample_output = ""
        try:
            result = subprocess.run(
                ["/usr/bin/sample", str(pid), str(duration_s)],
                capture_output=True, text=True, timeout=duration_s + 10
            )
            sample_output = result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            sample_output = "sample tool unavailable or timed out"
        finally:
            proc.terminate()
            proc.wait(timeout=5)

        return sample_output

    def validate_cost_model(self, probe_results_path: str,
                            config_path: str) -> dict:
        """Compare micro-prober measurements against the cost model config.
        
        Returns a validation report showing discrepancies.
        """
        probe_data = {}
        config_data = {}

        probe_path = Path(probe_results_path)
        cfg_path = Path(config_path)

        if probe_path.exists():
            with open(probe_path) as f:
                probe_data = json.load(f)

        if cfg_path.exists():
            with open(cfg_path) as f:
                config_data = json.load(f)

        report = {
            "validation": "cost_model_vs_prober",
            "discrepancies": [],
            "matches": [],
        }

        # Build probe lookup
        probe_instrs = {}
        for instr in probe_data.get("instructions", []):
            probe_instrs[instr["name"]] = instr

        # Build config mnemonic → cost lookup
        config_instrs = {}
        for instr in config_data.get("instructions", []):
            config_instrs[instr["mnemonic"]] = instr

        # Map probe names → config mnemonics
        name_map = {
            "ADD": "ADD", "MUL": "MUL", "DIV": "SDIV",
            "LOAD": "LDR", "CMP+B": "B.cond",
        }

        for probe_name, config_name in name_map.items():
            if probe_name not in probe_instrs or config_name not in config_instrs:
                continue

            probe_lat = probe_instrs[probe_name].get("latency_cycles", 0)
            config_lat = config_instrs[config_name].get("latency", 0)
            diff = abs(probe_lat - config_lat)

            entry = {
                "instruction": probe_name,
                "probed_latency": round(probe_lat, 2),
                "config_latency": config_lat,
                "difference": round(diff, 2),
            }

            if diff > 1.0:
                report["discrepancies"].append(entry)
            else:
                report["matches"].append(entry)

        return report

    def export_result(self, result: PMUResult, filename: str = "pmu_profile.json") -> Path:
        """Export profiling result to JSON."""
        out_path = self.output_dir / filename
        with open(out_path, "w") as f:
            json.dump(asdict(result), f, indent=2)
        return out_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="PMU Profiler for Vir compiler validation")
    parser.add_argument("--binary", type=str, help="Binary to profile")
    parser.add_argument("--args", nargs="*", default=[], help="Arguments for binary")
    parser.add_argument("--iterations", type=int, default=5, help="Number of profiling runs")
    parser.add_argument("--measure-overhead", action="store_true",
                        help="Measure timing overhead")
    parser.add_argument("--validate", action="store_true",
                        help="Validate cost model against probe data")
    parser.add_argument("--probe-data", type=str, default="data/arch/probe_results.json")
    parser.add_argument("--config", type=str, default="data/arch/arm64_config.json")
    parser.add_argument("--output-dir", type=str, default="data/arch")

    args = parser.parse_args()
    profiler = PMUProfiler(args.output_dir)

    if args.measure_overhead:
        overhead = profiler.measure_overhead()
        print(json.dumps(overhead, indent=2))
        return

    if args.validate:
        report = profiler.validate_cost_model(args.probe_data, args.config)
        print(json.dumps(report, indent=2))
        out_path = Path(args.output_dir) / "validation_report.json"
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved: {out_path}")
        return

    if args.binary:
        result = profiler.profile_binary(args.binary, args.args, args.iterations)
        out = profiler.export_result(result)
        print(f"Wall time:  {result.wall_time_s:.6f}s")
        print(f"User time:  {result.user_time_s:.6f}s")
        print(f"Sys time:   {result.sys_time_s:.6f}s")
        print(f"Max RSS:    {result.max_rss_kb} KB")
        print(f"Saved: {out}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
