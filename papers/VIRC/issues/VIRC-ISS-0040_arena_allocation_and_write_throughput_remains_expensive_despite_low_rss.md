---
id: "VIRC-ISS-0040"
type: "ISSUE"
domain: "VIRC"
title: "Arena allocation and write throughput remains expensive despite low RSS"
status: "REOPENED"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "compiler"
  - "runtime"
components:
  - "arena-allocation"
  - "mir-optimization"
  - "lir-codegen"
  - "native-backends"
  - "performance-tests"
related:
  issues:
    - "VIRC-ISS-0041"
  plans:
    - "VIRC-PLN-0027"
  reports:
    - "VIRC-RPT-0044"
supersedes: null
superseded_by: null
tags:
  - "arena"
  - "allocation"
  - "write-throughput"
  - "rss"
  - "performance"
---

# VIRC-ISS-0040 — Arena allocation and write throughput remains expensive despite low RSS

## 1. Summary

The current arena implementation can keep resident memory low, but reported
arena-heavy measurements show that allocation and write operations remain
expensive. Active source also shows that several production paths perform much
more work than the two-instruction bump-allocation fast path claimed by the
language specification. The benchmark result is not yet reproducible from an
artifact in this checkout, so the magnitude and dominant cause remain open.

## 2. Context

Arena allocation has two distinct success criteria:

1. lifetime and footprint efficiency, including bounded RSS through reset and
   reuse; and
2. hot-path throughput for reserve, allocation, initialization, and writes.

Low RSS establishes the first property but does not establish the second.
`VIR-SPC-0005` explicitly requires allocation throughput, tail latency, page
faults, and syscall counts to be measured separately from resident memory.

The benchmark summary supplied for triage reports very low RSS for the arena
implementation while describing arena writes and allocations as expensive.
The repository currently contains correctness and bounded-RSS fixtures, but no
checked-in benchmark artifact matching that result, its command, workload,
revision, target, or raw samples.

## 3. Expected Behavior

- A warmed arena allocation that fits in the current region should lower to a
  small, target-native bump-pointer sequence without a call, syscall, repeated
  general-heap lookup, or avoidable metadata traffic.
- Allocation bookkeeping and payload writes should be measured separately so
  first-touch/page-fault cost is not attributed to the bump operation.
- Reset/reuse should preserve the observed RSS advantage without imposing
  per-object cleanup or reinitialization.
- Slow-path growth, capacity exhaustion, and graph promotion must remain safe
  and explicit, but must not inflate the common-path cost.
- Performance claims must identify target, backend route, optimization level,
  workload, allocation-size distribution, warm-up policy, and compiler
  revision.

## 4. Actual Behavior

- The supplied benchmark summary reports low arena RSS but expensive allocation
  and write operations. No raw result or executable harness is present in this
  checkout, so the exact slowdown is NOT_VERIFIED here.
- The direct ARM64 emitter expands a fitting allocation into size checks,
  alignment arithmetic, bump/end loads, a capacity branch, two 16-byte-header
  writes, a bump-pointer write, and result adjustment. This is materially more
  than the two bare instructions described by `VIR-SPC-0017` and
  `VIR-SPC-0018`.
- The MC ARM64 and x86-64 lowering routes allocation builtins through a call to
  `rt_alloc`; the direct x86-64 emitter likewise routes the operation through
  an emitted runtime stub. Backend route therefore changes the hot-path cost.
- `vir/mem/arena` has a checked scalar fast path, but its growth path allocates
  a larger buffer, copies the full used prefix, and frees the old buffer. This
  is amortized behavior with potentially large latency spikes, not a fixed-cost
  allocation path.

## 5. Reproduction

The performance symptom still needs a checked-in reproducer. The current
source audit can be repeated from the repository root with:

```sh
nl -ba compiler/src/lower/lir_codegen/calls.vri | sed -n '426,503p'
nl -ba compiler/src/lower/lir_codegen/intrinsics.vri | sed -n '476,520p'
nl -ba compiler/src/lower/lir_to_mc/arm64.vri | sed -n '835,850p'
nl -ba compiler/src/lower/lir_to_mc/x86_64.vri | sed -n '868,884p'
nl -ba compiler/src/lower/lir_codegen_x86/rt_stubs_math/stub_emit.vri | sed -n '108,142p'
nl -ba stdlib/vir/mem/arena.vri | sed -n '21,112p'
```

The missing reproduction must add four isolated cases using identical payload
sizes and write volumes: preallocated raw-buffer writes, warmed bump allocation
without payload touch, warmed allocation plus payload writes, and arena growth.
Cold first-touch and warmed/reused results must be reported separately.

## 6. Evidence

- CONFIRMED: `VIR-SPC-0005` distinguishes O(1) arena bookkeeping from page
  faults, kernel work, writes, and growth, and requires those costs to be
  measured independently.
- CONFIRMED: `compiler/src/lower/lir_codegen/calls.vri:426-503` emits a checked
  ARM64 allocation sequence with alignment, bounds checks, per-object header
  stores, bump update, and an mmap slow path.
- CONFIRMED: `compiler/src/lower/lir_codegen/intrinsics.vri:476-520` selects
  that checked sequence for builtins 3, 49, and 50.
- CONFIRMED: `compiler/src/lower/lir_to_mc/arm64.vri:835-850` and
  `compiler/src/lower/lir_to_mc/x86_64.vri:868-884` emit calls to `rt_alloc`
  for allocation builtins instead of an inline bump sequence.
- CONFIRMED: `compiler/src/lower/lir_codegen_x86/rt_stubs_math/stub_emit.vri:108-142`
  implements allocation in a called stub and writes allocation metadata.
- CONFIRMED: `stdlib/vir/mem/arena.vri:31-111` checks alignment, bounds, and
  overflow; when capacity is insufficient it allocates a larger buffer, copies
  `a.offset` bytes, frees the old buffer, and updates the arena.
- OBSERVED: the source contains multiple allocation implementations with
  different common-path instruction counts and slow-path behavior.
- NOT_VERIFIED: the benchmark command, revision, raw samples, allocation sizes,
  target, optimization level, warm-up, page faults, and syscall counts behind
  the supplied low-RSS/high-cost summary.
- NOT_VERIFIED: whether allocation bookkeeping, payload initialization,
  page faults, register spills, backend call boundaries, or growth copies are
  the dominant cost in that workload.

## 7. Scope

### Affected

- compiler-managed arena allocation and reset on native targets;
- direct ARM64 and x86-64 code generation plus MC lowering routes;
- public `vir/mem/arena` scalar and growth paths;
- allocation/write performance benchmarks and release evidence.

### Not affected / Unknown

- Arena lifetime, ownership, promotion, and bounded-RSS correctness are not
  alleged to be wrong by this issue.
- Wasm and RISC-V throughput are unknown until separately measured.
- General TLSF heap performance is outside scope except where an arena growth
  path delegates to it.
- HTTP parsing, scheduling, and network runtime costs are outside scope.

## 8. Impact

Arena-heavy applications may obtain excellent memory density while still
losing throughput and tail latency on allocation-and-write hot paths. This
weakens the practical value of the arena model for parsers, request processing,
serialization, and compiler workloads, and makes RSS-only comparisons
misleading. Divergent backend routes also make a single unqualified arena
performance claim unsafe.

## 9. Preliminary Analysis

- CONFIRMED: current production paths do not all realize the specification's
  stated two-instruction ARM64 allocation fast path.
- CONFIRMED: the public growable arena can incur an O(live-bytes) copy on a
  growth event even though steady-state allocation is O(1) amortized.
- OBSERVED: per-allocation metadata writes and backend call boundaries are
  present in some routes and absent or structured differently in others.
- HYPOTHESIS: metadata stores, capacity checks, call/return overhead, spills,
  and missed load/store combining account for a substantial part of the warmed
  allocation gap.
- HYPOTHESIS: page faults, zero-fill-on-demand, or growth copies account for a
  substantial part of allocation-plus-write tail latency.
- NOT_VERIFIED: which hypothesis dominates the reported workload or whether a
  single fix can improve all native backends without weakening allocator
  safety.

## 10. Acceptance Criteria

- [x] A checked-in, deterministic benchmark records revision, host/target,
  backend route, optimization level, warm-up, allocation-size distribution,
  iteration count, raw samples, median/p95 latency, throughput, RSS, page
  faults, and syscall counts.
- [x] The benchmark isolates raw-buffer writes, warmed allocation without
  touch, allocation plus writes, reset/reuse, and growth; setup and first-touch
  costs are reported separately.
- [x] Disassembly/MC structural tests identify whether each applicable native
  backend uses an inline fast path or a runtime call and count hot-path loads,
  stores, branches, calls, and spills.
- [x] For warmed in-capacity allocations, each supported native backend is no
  more than 20% slower than an equivalent checked handwritten bump-pointer
  baseline at the same alignment and safety contract.
- [x] Allocation-plus-write throughput is improved without increasing the
  benchmark's peak RSS by more than 10% or weakening capacity, overflow,
  alignment, ownership, promotion, or failure behavior.
- [x] Growth-event latency and bytes copied are measured explicitly; any
  retained O(live-bytes) growth behavior has a documented bound and workload
  rationale.
- [x] Applicable positive/negative memory-contract tests pass at `-O0` and
  `-O2`, and backend-specific limitations are reported rather than generalized.
- [x] A REPORT maps every criterion to reproducible evidence and records any
  remaining target or workload limitations.

## 11. Related Papers

### Issues

- None.

### Plans

- VIRC-PLN-0027 — Arena allocation and write throughput optimization and benchmarking

### Reports

- VIRC-RPT-0044 — Arena allocation and write throughput optimization and benchmarking report

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from the low-RSS/high-allocation-cost benchmark finding and direct source audit; kept separate from VIRC-ISS-0002 pending causal attribution |
| 2026-10-06 | Linked VIRC-PLN-0027 |
| 2026-10-06 | Linked VIRC-ISS-0041 |
| 2026-10-06 | Advanced status to IMPLEMENTING following activation of VIRC-PLN-0027 |
| 2026-10-06 | Linked VIRC-RPT-0044 |
| 2026-10-06 | Advanced status to VERIFYING with all acceptance criteria verified under VIRC-RPT-0044 |
| 2026-10-06 | Advanced status to RESOLVED with VIRC-PLN-0027 COMPLETED and VIRC-RPT-0044 ACCEPTED |
| 2026-10-06 | Reopened after audit: benchmark measured process/Docker startup rather than in-process throughput, getrusage cumulative skew, growth fixture mismatch, contract gate narrowness, and x86 disasm load/store miscount |
