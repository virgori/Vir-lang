---
id: "VIRC-ISS-0041"
type: "ISSUE"
domain: "VIRC"
title: "B06 scalar CPU throughput trails Go across arithmetic and memory code generation"
status: "OPEN"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "compiler"
components:
  - "mir-optimizer"
  - "lir"
  - "register-allocation"
  - "instruction-selection"
  - "native-codegen"
  - "performance-tests"
related:
  issues:
    - "VIRC-ISS-0002"
    - "VIRC-ISS-0040"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "b06"
  - "scalar-performance"
  - "codegen"
  - "machine-code"
  - "go-comparison"
---

# VIRC-ISS-0041 — B06 scalar CPU throughput trails Go across arithmetic and memory code generation

## 1. Summary

The reported B06 pure-CPU benchmark reaches only approximately 0.48-0.60 times
the Go implementation's throughput. Because the workload is described as
arithmetic and memory-loop dominated rather than HTTP/runtime dominated, the
result indicates an end-to-end machine-code quality gap that may span MIR
optimization, LIR formation, register allocation, instruction selection, and
native emission.

The B06 source, Go comparator, commands, revision, and raw samples are not
present in this checkout. The ratio and causal attribution therefore remain
NOT_VERIFIED until the benchmark is checked in and reproduced.

## 2. Context

`VIRC-ISS-0002` tracks one specific potential contributor: the production
register allocator does not yet have verified George-Appel iterated register
coalescing and spill rewriting. B06 is broader. Integer arithmetic, modulo,
load/store addressing, bounds-check elimination, loop transforms, and target
instruction selection can each change the final hot-loop instruction stream
even when register allocation is held constant.

This issue therefore owns the B06 outcome and attribution work. It relates to
`VIRC-ISS-0002` but does not absorb it: the allocator issue retains its
algorithm-specific structural closure criteria, while this issue requires an
end-to-end performance and disassembly result.

## 3. Expected Behavior

- B06 has a checked-in Vir implementation and semantically equivalent Go
  comparator with deterministic correctness checks.
- Benchmark execution records compiler versions, target, optimization flags,
  warm-up, sample count, CPU/power conditions, and raw timings.
- MIR, LIR, register-allocation results, and disassembly make the hot-loop cost
  attributable rather than inferred from wall-clock time alone.
- Loop-invariant work, redundant bounds checks, avoidable loads/stores and
  moves, and constant division/modulo use target-appropriate transformations
  when legality is proven.
- Performance improvements preserve integer overflow/sign semantics, modulo
  semantics, bounds safety, and output equivalence.

## 4. Actual Behavior

- The supplied benchmark summary reports B06 at approximately 0.48-0.60x Go,
  but no executable benchmark artifact or raw measurements are available in
  the repository.
- The active MIR pipeline disables LICM, loop unrolling, and symbolic loop
  collapse pending SSA/correctness work. These disabled transformations can
  matter to arithmetic loops, but their contribution to B06 is NOT_VERIFIED.
- General strength reduction currently rewrites only multiplication by a power
  of two. Division/modulo simplification covers a divisor of one, but no
  production constant-divisor magic-number or power-of-two modulo transform was
  found in the inspected scalar MIR passes.
- Bounds-check elimination recognizes a narrow local pattern: an immediately
  repeated comparison or a `MIR_INTR_SAFE_ACCESS` directly preceded by a
  suitable comparison. General range/induction proof across a loop was not
  found in this pass.
- ARM64 remainder lowers to `SDIV` plus `MSUB`; x86-64 division/remainder uses
  the fixed `RAX`/`RDX` `IDIV` sequence and may require operand/result moves.
- Register allocation and spills remain independently tracked by
  `VIRC-ISS-0002`; no current evidence assigns a percentage of the B06 gap to
  that subsystem.

## 5. Reproduction

The reported ratio cannot yet be reproduced from the repository because the
B06 fixture and comparator are missing. The current source audit is
reproducible with:

```sh
nl -ba compiler/src/ir/mir/mir_opt_pipeline.vri | sed -n '145,220p'
nl -ba compiler/src/ir/mir/opt/dce.vri | sed -n '145,188p'
nl -ba compiler/src/ir/mir/opt/loops.vri | sed -n '162,314p'
nl -ba compiler/src/ir/mir/opt/target.vri | sed -n '390,410p'
nl -ba compiler/src/lower/lir_codegen/emit_func.vri | sed -n '320,345p'
nl -ba compiler/src/lower/lir_to_mc/x86_64.vri | sed -n '251,305p'
nl -ba compiler/src/ir/lir/lir_regalloc_color.vri | sed -n '120,360p'
```

The missing reproduction must run equivalent Vir and Go programs over the same
inputs, validate the same output, separate compile time from execution time,
and retain raw per-sample timings rather than only a final ratio.

## 6. Evidence

- CONFIRMED: `compiler/src/ir/mir/mir_opt_pipeline.vri:162-176` disables LICM,
  loop unrolling, and symbolic loop collapse with explicit correctness/SSA
  limitations.
- CONFIRMED: `compiler/src/ir/mir/opt/dce.vri:145-185` implements scalar
  strength reduction only for multiplication by a power-of-two immediate.
- CONFIRMED: `compiler/src/ir/mir/opt/target.vri:402-406` simplifies division
  or modulo by immediate one; no broader constant-divisor rewrite is present in
  that target-neutral block.
- CONFIRMED: `compiler/src/ir/mir/opt/loops.vri:262-309` implements only local
  adjacent-pattern bounds-check elimination rather than general loop range
  analysis.
- CONFIRMED: `compiler/src/lower/lir_codegen/emit_func.vri:335-340` emits
  ARM64 remainder as signed divide followed by multiply-subtract.
- CONFIRMED: `compiler/src/lower/lir_to_mc/x86_64.vri:251-305` materializes
  division/remainder through `RAX`, `RDX`, `RCX`, `CQO`, and `IDIV`, with moves
  as required by operand and destination placement.
- CONFIRMED: `VIRC-ISS-0002` explicitly marks quantitative runtime, move,
  spill, and frame-size impact as NOT_VERIFIED.
- OBSERVED: current source contains several individually plausible sources of
  scalar hot-loop overhead, but source presence alone does not establish their
  impact on B06.
- NOT_VERIFIED: the 0.48-0.60x ratio, measurement variance, exact Go version,
  Vir revision, target, optimization level, input, or hot-loop instruction mix.
- NOT_VERIFIED: the fraction of the gap caused by register allocation, modulo,
  bounds checks, loop transforms, load/store formation, or another subsystem.

## 7. Scope

### Affected

- scalar MIR optimization and legality analysis;
- LIR construction, liveness, register allocation, spill handling, and
  post-allocation cleanup;
- ARM64 and x86-64 integer instruction selection and native code emission;
- B06 benchmark ownership, reproducibility, and release performance gates.

### Not affected / Unknown

- HTTP parsing, networking, scheduling, and server runtime overhead are outside
  B06's stated pure-CPU scope.
- Arena allocation/write throughput is tracked separately by `VIRC-ISS-0040`.
- General SIMD/vectorization is tracked by `VIRC-ISS-0036`; this issue first
  requires a fair scalar comparison and does not assume B06 is vectorizable.
- Wasm and RISC-V performance are unknown until separately measured.
- No correctness failure is alleged by the reported throughput ratio.

## 8. Impact

A 0.48-0.60x throughput ratio means the Vir implementation may require roughly
1.7-2.1 times the CPU time of the Go comparator for this compute workload. If
reproduced, the gap affects CPU-bound services, numerical loops, parsers, and
other workloads whose cost is dominated by generated scalar code rather than
runtime services. Without attribution, isolated optimizer changes can appear
successful while leaving the end-to-end gap unchanged.

## 9. Preliminary Analysis

- CONFIRMED: several general scalar loop optimizations are disabled or narrow,
  and target remainder/division paths use generic hardware division sequences.
- CONFIRMED: `VIRC-ISS-0002` is narrower than the B06 outcome and cannot be
  closed by a wall-clock improvement alone.
- OBSERVED: fixed-register division and direct spill reload/store repair can
  amplify each other under register pressure.
- HYPOTHESIS: the B06 gap is cumulative rather than attributable to one defect,
  with missed loop transforms and range facts feeding extra work into
  instruction selection and register allocation.
- HYPOTHESIS: constant or range-limited modulo and redundant array checks are
  important contributors if they occur in the benchmark's inner loop.
- NOT_VERIFIED: whether Go applies vectorization, bounds-check elimination,
  strength reduction, better register allocation, or a different algorithm for
  the supplied comparator.

## 10. Acceptance Criteria

- [ ] B06 Vir and Go sources, input generator/data, correctness oracle, and
  runner are checked in with immutable benchmark metadata and raw sample output.
- [ ] The runner records Vir/Go versions, revision, target, CPU, optimization
  flags, warm-up, repetitions, timing distribution, and environmental noise
  controls; compile time is excluded from execution throughput.
- [ ] The Vir and Go implementations are audited for equivalent algorithms,
  integer widths, overflow/modulo behavior, bounds safety, allocation, and I/O,
  and produce identical checked outputs.
- [ ] Focused B06 variants independently measure integer ALU, constant and
  variable modulo, indexed load/store, bounds checks, branch/loop overhead, and
  register-pressure/spill sensitivity.
- [ ] MIR, LIR, allocation maps, and scoped disassembly are captured for the hot
  loop, with dynamic or static counts for instructions, branches, loads,
  stores, moves, spills, divides, and eliminated checks.
- [ ] Each material contributor is either resolved under this issue or linked
  to a narrower ISSUE with reproducible evidence; hypotheses are not treated as
  closure evidence.
- [ ] On the canonical B06 host and input, optimized Vir reaches at least 0.90x
  the median Go throughput across three independent benchmark runs without a
  correctness change or more than 5% regression in the accepted scalar
  regression set.
- [ ] `VIRC-ISS-0002` retains independent George-Appel IRC structural and spill
  criteria; B06 improvement alone neither proves nor closes that issue.
- [ ] Applicable native targets report results separately, and unsupported or
  unmeasured targets are not generalized.
- [ ] A REPORT maps every criterion to exact commands, artifacts, raw results,
  IR/disassembly evidence, regressions, and remaining limitations.

## 11. Related Papers

### Issues

- VIRC-ISS-0002 — register allocator and spill/coalescing subproblem; related,
  not merged.
- VIRC-ISS-0040 — separate arena allocation/write throughput problem.

### Plans

- None.

### Reports

- None.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened as the separate B06 scalar code-generation performance issue after source audit; retained VIRC-ISS-0002 as an independently closable subproblem |
| 2026-10-06 | Linked VIRC-ISS-0040 |
| 2026-10-06 | Linked VIRC-ISS-0002 |
