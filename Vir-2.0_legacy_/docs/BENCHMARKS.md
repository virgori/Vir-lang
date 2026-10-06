# Benchmark methodology

The maintained entry point is
[`bench/live_suite/run_benchmarks.py`](../bench/live_suite/run_benchmarks.py).
Inspect workload source files in that directory for actual sizes and repetitions;
harness labels and historical prose are not authoritative workload definitions.

## What the harness measures today

- Compilation happens before timing and is excluded. It builds C at O2 and
  O3 (O3 uses fast-math and LTO), Rust at O2 and O3/LTO, Go, and Vir using the
  checked-in compiler. These flags are not semantically equivalent, especially
  for floating-point workloads.
- Each command runs five times; the reported value is median elapsed wall time
  from Python `time.perf_counter`, in milliseconds.
- There is **no explicit warm-up**. Earlier executions may warm filesystem and
  CPU caches; this is not a controlled cold-start measurement.
- Timing includes `subprocess.run(shell=True)`, shell and process launch,
  execution, stdout/stderr capture, and process completion. No baseline is
  subtracted. It is not kernel-only time or a standalone startup measurement.
- Nonzero exit status fails the run. The harness retains only the last sample's
  stripped stdout and prints a truncated preview. It does **not** assert an
  expected output or cross-language equality. Output verification is therefore
  **not established** by this harness.
- Compiler versions, machine identity, thermal conditions and raw sample times
  are not automatically archived. A hardcoded banner is not environment evidence.

## Publishing a result

Record commit SHA, compiler versions and flags, OS/CPU, workload inputs,
warm-up policy, every measured sample and aggregation. Verify every sample
against an explicit expected result; define tolerances for floating-point
results before measurement. Report whether subprocess overhead is included.
Keep warm-up, correctness verification and compilation outside timing when
reporting execution-only measurements, and explain any departure.

[Historical results](benchmark_results.json) and
[comprehensive snapshot](benchmark_comprehensive_results.json) are retained
for provenance. They do not certify today's compiler performance. README
performance and startup comparisons were removed because the current harness
does not substantiate their versions, scope and claimed output verification.
