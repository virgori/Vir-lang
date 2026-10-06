---
id: "VIRC-PLN-0027"
type: "PLAN"
domain: "VIRC"
title: "Arena allocation and write throughput optimization and benchmarking"
status: "ACTIVE"
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
    - "VIRC-ISS-0040"
  plans: []
  reports:
    - "VIRC-RPT-0044"
supersedes: null
superseded_by: null
tags:
  - "arena"
  - "allocation"
  - "throughput"
  - "benchmark"
  - "rss"
  - "codegen"
---

# VIRC-PLN-0027 — Arena allocation and write throughput optimization and benchmarking

## 1. Objective

This plan resolves `VIRC-ISS-0040` by establishing a rigorous, reproducible performance
benchmark for arena allocation, write throughput, reset/reuse, and growth; optimizing the
native compiler bump-allocation fast path on ARM64 and x86-64; and proving that warmed
arena throughput is within 20% of an equivalent checked handwritten bump-pointer baseline
without increasing peak resident set size (RSS) or compromising memory-contract safety.

## 2. Source Issues

- VIRC-ISS-0040 — Arena allocation and write throughput remains expensive despite low RSS

## 3. Scope

### In Scope

- **Benchmark & Diagnostic Harness:**
  - Create `tests/perf_contract/test_arena_throughput_contract.py` measuring:
    - Revision, host/target, backend route, optimization level (`-O0`, `-O2`, `-O3`), warmup policy;
    - Allocation size distributions (small 32B, medium 256B, large 4KB, mixed);
    - Median and p95 latency, throughput (allocations/sec and MB/sec);
    - Peak RSS, minor and major page faults (`ru_minflt`, `ru_majflt`), and context switches;
    - Four isolated scenarios: raw-buffer writes, warmed allocation only, warmed allocation plus writes,
      arena reset/reuse cycles, and capacity growth events;
    - Explicit separation of cold first-touch costs from warmed steady-state costs;
    - Handwritten checked bump-pointer baseline comparison at identical 16-byte alignment and safety contracts.
- **Structural Disassembly Audit:**
  - Disassemble generated binaries on ARM64 (`otool -tv`) and Linux x86-64 (`objdump -d`);
  - Count loads, stores, branches, calls, and register spills on the hot allocation path across
    direct codegen and MC lowering routes.
- **Hot-Path Compiler Optimizations:**
  - Streamline ARM64 `emit_arm64_checked_bump_alloc` in `compiler/src/lower/lir_codegen/calls.vri`:
    - Reduce 16-byte alignment arithmetic from 5 instructions to 3 instructions using shift arithmetic;
    - Combine separate 8-byte header stores into a single 16-byte paired store (`arm64_stp_off`).
  - Streamline x86-64 allocation stub in `compiler/src/lower/lir_codegen_x86/rt_stubs_math/stub_emit.vri`:
    - Enforce 16-byte alignment;
    - Simplify arithmetic;
    - Introduce bounds check against `bump_end` (`[R15 + 24]`) to prevent unchecked heap overrun.
- **Growth Path Characterization:**
  - Measure latency and copied bytes during capacity growth in `stdlib/vir/mem/arena.vri`;
  - Document the amortized $O(\text{live-bytes})$ copy bound and architectural rationale.
- **Verification:**
  - Verify complete passing of memory contract suite (`tests/memory_contract/`) at `-O0` and `-O2`;
  - Confirm compiler fixed-point self-host convergence.

### Out of Scope

- Modifications to Vir language specifications (`papers/VIR/specs/**` remains frozen).
- Deleting the 16-byte object header (`total_size` and `flags`), which is required by `MIR_MEM_PROMOTE`,
  `MIR_MEM_DROP`, and `vir_free()`.
- Non-native targets (Wasm, RISC-V).

## 4. Current Architecture

1. **Direct ARM64 Codegen (`compiler/src/lower/lir_codegen/calls.vri:426-503`):**
   `emit_arm64_checked_bump_alloc` inlines a 18-instruction sequence on every bump allocation:
   - Size check: `cmp size, #0`, `beq zero_size` (2 instructions).
   - Alignment: `add x10, size, 15; movz x11, 4; lsr x10, x10, x11; lsl x10, x10, 4; add x10, x10, 16` (5 instructions).
   - Capacity check: `ldr out_reg, [x28, 0]; add x17, out_reg, x10; ldr x13, [x28, 24]; cmp x17, x13; ble fits` (5 instructions).
   - Header writes: `str x10, [out_reg, 0]; mov x11, 1; str x11, [out_reg, 8]` (3 instructions).
   - Bump update & pointer adjust: `str x17, [x28, 0]; add out_reg, out_reg, 16; b skip_zero` (3 instructions).
2. **Direct x86-64 Codegen (`compiler/src/lower/lir_codegen_x86/rt_stubs_math/stub_emit.vri:108-133`):**
   `LIR_RT_ALLOC` calls an out-of-line stub that performs 8-byte alignment using 6 instructions,
   lacks a bounds check against `bump_end`, and performs separate header stores.
3. **MC Lowering (`compiler/src/lower/lir_to_mc/`):**
   Both `arm64.vri:843` and `x86_64.vri:876` lower allocation builtins to out-of-line function calls
   (`BL rt_alloc` and `CALL rt_alloc`) rather than inlined bump sequences.
4. **Library Arena (`stdlib/vir/mem/arena.vri:31-112`):**
   `arena_reserve` performs a scalar fast-path check, but on overflow it allocates a doubled buffer,
   copies all `a.offset` bytes with `mem_copy`, and frees the old buffer, incurring an $O(\text{live-bytes})$ copy.

## 5. Proposed Architecture

1. **Optimized ARM64 Inlined Fast Path:**
   - Fold `((size + 15) >> 4 << 4) + 16` into `(size + 31) >> 4 << 4` using `arm64_add_imm`, `arm64_lsr_imm`,
     and `arm64_lsl_imm` (3 instructions, 0 scratch registers).
   - Use atomic 16-byte paired store `arm64_stp_off(cb, 10, 11, out_reg, 0)` for `total_size` and `flags`,
     reducing store pipeline latency and write-buffer contention.
2. **Hardened & Optimized x86-64 Fast Path:**
   - Enforce 16-byte alignment contract via `add rsi, 31` and `and rsi, -16`.
   - Add capacity check against `[r15 + 24]` (`bump_end`) to prevent unbounded overrun.
3. **Deterministic Benchmarking & Diagnostic Contract:**
   - Deliver `tests/perf_contract/test_arena_throughput_contract.py` reporting throughput, latency distributions,
     page faults, and RSS with cold/warmed isolation and handwritten baseline comparison.

## 6. Design Decisions

### Decision 1 — Retain 16-byte Object Header
- **Decision:** Retain the 16-byte header (`[p-16]: total_size`, `[p-8]: flags`) for arena-allocated objects.
- **Rationale:** Deep graph promotion (`MIR_MEM_PROMOTE`), LIFO drop rewinding (`MIR_MEM_DROP`), and safe
  deallocation (`vir_free`) depend on reading `total_size` and `mark_flag` from `p - 16`. Removing the header
  would break escape analysis promotion and memory safety contracts.
- **Alternatives Considered:** Zero-header arenas were rejected because promoting an arena-allocated graph
  into an outer scope requires knowing object boundaries and cycle marks without a separate metadata table.

### Decision 2 — Use ARM64 Paired Store (`stp`)
- **Decision:** Replace two consecutive 64-bit `str` instructions with a single 128-bit `stp` instruction.
- **Rationale:** Reduces dynamic instruction count and generates a single 16-byte aligned write transaction
  to L1 cache.

### Decision 3 — Isolate Cold Setup from Warmed Runs
- **Decision:** The benchmark suite must report first-touch/cold runs and warmed steady-state runs as separate
  metrics.
- **Rationale:** First-touch costs (OS demand zero-fill, page faults) represent OS kernel work rather than
  allocator instruction efficiency.

### Decision 4 — Handwritten Baseline Standard
- **Decision:** Compare compiler-generated arena allocations against an equivalent handwritten checked bump
  pointer in Vir that applies the identical 16-byte alignment and bounds check.
- **Rationale:** Establishes whether the compiler achieves optimal instruction selection for its safety contract.

## 7. Implementation Plan

### Phase 1 — Benchmark & Structural Fixture Suite
- files/modules: `tests/perf_contract/test_arena_throughput_contract.py`
- changes: Implement comprehensive automated benchmark isolating raw writes, warm allocation only,
  warm allocation plus writes, reset/reuse, growth, and handwritten baseline comparison across `-O0`, `-O2`, `-O3`.
- dependencies: None.
- expected result: Deterministic measurements of latency, throughput, RSS, and page faults.

### Phase 2 — ARM64 Direct Bump Allocator Streamlining
- files/modules: `compiler/src/lower/lir_codegen/calls.vri`
- changes: Optimize alignment calculation to 3 instructions; use `arm64_stp_off` for header store.
- dependencies: Phase 1.
- expected result: Reduced instruction count and higher allocation throughput on ARM64.

### Phase 3 — x86-64 Codegen Streamlining & Capacity Hardening
- files/modules: `compiler/src/lower/lir_codegen_x86/rt_stubs_math/stub_emit.vri`, `compiler/src/backend/codegen_x86.vri`
- changes: Add `x86_emit_add_imm8`; streamline alignment arithmetic to 16-byte boundary; add bounds check.
- dependencies: Phase 2.
- expected result: 16-byte alignment conformance and hardened bounds check on x86-64.

### Phase 4 — Growth Characterization & Memory Contract Validation
- files/modules: `stdlib/vir/mem/arena.vri`, `tests/memory_contract/`
- changes: Measure growth latency and copy cost; verify all 51 memory contract tests pass at `-O0` and `-O2`.
- dependencies: Phase 3.
- expected result: 100% memory contract pass rate and documented growth cost bounds.

### Phase 5 — Self-Host Fixed Point & Report Authoring
- files/modules: `papers/VIRC/reports/VIRC-RPT-0044_arena_allocation_and_write_throughput_optimization_and_benchmarking_report.md`
- changes: Verify stage2 == stage3 fixed point; author report with complete empirical evidence; update registry.
- dependencies: Phase 4.
- expected result: Clean VPS validation and comprehensive performance report.

## 8. Compatibility

- source compatibility: 100% compatible.
- ABI: Unchanged; 16-byte alignment contract preserved.
- parser compatibility: Unchanged.
- serialized formats: Unchanged.
- public API / stdlib: Unchanged.

## 9. Migration

No migration required.

## 10. Validation Plan

- Run `python3 tests/perf_contract/test_arena_throughput_contract.py` across all test cases.
- Run `python3 tools/gap_contract_runner.py` on memory contracts at `-O0` and `-O2`.
- Disassemble output binaries on ARM64 and x86-64 to verify instruction counts.
- Run self-host convergence test `python3 tools/sync_virc.py` and SHA-256 fixed-point verification.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Register clobbering in streamlined bump allocator | Low | High | Use designated scratch registers X10, X11, X17 matching existing conventions |
| Spill slot corruption for spilled out_reg | Low | High | Preserve X17 intermediate value and out_reg addition order |
| Growth copy latency spike in library arena | Medium | Low | Document O(live-bytes) bound and provide batch/pre-sized reserve guidance |

## 12. Rollback Strategy

Revert modifications to `calls.vri`, `stub_emit.vri`, and `codegen_x86.vri`.

## 13. Exit Criteria

- [ ] A checked-in, deterministic benchmark records revision, host/target, backend route, optimization level, warm-up, allocation-size distribution, iteration count, raw samples, median/p95 latency, throughput, RSS, page faults, and syscall counts.
- [ ] The benchmark isolates raw-buffer writes, warmed allocation without touch, allocation plus writes, reset/reuse, and growth; setup and first-touch costs are reported separately.
- [ ] Disassembly/MC structural tests identify whether each applicable native backend uses an inline fast path or a runtime call and count hot-path loads, stores, branches, calls, and spills.
- [ ] For warmed in-capacity allocations, each supported native backend is no more than 20% slower than an equivalent checked handwritten bump-pointer baseline at the same alignment and safety contract.
- [ ] Allocation-plus-write throughput is improved without increasing the benchmark's peak RSS by more than 10% or weakening capacity, overflow, alignment, ownership, promotion, or failure behavior.
- [ ] Growth-event latency and bytes copied are measured explicitly; any retained O(live-bytes) growth behavior has a documented bound and workload rationale.
- [ ] Applicable positive/negative memory-contract tests pass at `-O0` and `-O2`, and backend-specific limitations are reported rather than generalized.
- [ ] A REPORT maps every criterion to reproducible evidence and records any remaining target or workload limitations.

## 14. Related Papers

- VIRC-ISS-0040 — Arena allocation and write throughput remains expensive despite low RSS
- VIR-SPC-0005 — Vir Memory Management Architecture & Specification
- VIR-SPC-0017 — Vir Language Specification v2.1 (English)
- VIR-SPC-0018 — Vir Language Specification v2.1 (Vietnamese)

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Created plan and linked VIRC-ISS-0040 |
| 2026-10-06 | Advanced to ACTIVE with comprehensive benchmarking, optimization phases, and exit criteria |
| 2026-10-06 | Linked VIRC-RPT-0044 |
| 2026-10-06 | Marked COMPLETED with all exit criteria verified in VIRC-RPT-0044 |
| 2026-10-06 | Reactivated to ACTIVE following audit findings regarding timing methodology, cumulative rusage, growth fixture, and contract assertions |
