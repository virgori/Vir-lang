---
id: "VIRC-RPT-0013"
type: "REPORT"
domain: "VIRC"
title: "Phase 10 Domain 3 LIR and native codegen modularization report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "codegen"
components:
  - "lir-codegen"
  - "lir-to-mc"
  - "lir-codegen-x86"
  - "lir-codegen-wasm"
  - "pass-architecture"
  - "module-list"
related:
  issues:
    - "VIRC-ISS-0006"
    - "VIRC-ISS-0009"
  plans:
    - "VIRC-PLN-0004"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "codegen"
  - "lir"
  - "native-backend"
  - "modularization"
  - "phase10"
  - "cross-target"
---

# VIRC-RPT-0013 — Phase 10 Domain 3 LIR and native codegen modularization report

## 1. Executive Summary

In accordance with `VIRC-PLN-0004` Phase 10 Domain 3, `VIRC-ISS-0006`, and `VIRC-ISS-0009`, all four monolithic files in Domain 3 (LIR lowering, target machine code emitters, and codegen backends) have been successfully decomposed into cohesive leaf submodules and thin orchestrators. Every non-generated source file in Domain 3 now satisfies the hard constraint of **≤ 1,200 logical lines** (all files ≤ 1,175 raw lines / ≤ 1,060 logical lines). The self-hosting compiler compiles cleanly, codesigns, passes all 43 CLI contract tests, preserves the exact 409/413 regression test baseline, and verifies architecture boundaries.

## 2. Source Issues

- **VIRC-ISS-0006** — Compiler sources are coupled to stdlib and oversized pass files (mandates file LOC ≤ 1,200 logical lines).
- **VIRC-ISS-0009** — Native codegen conflates architecture OS ABI and object format (requires architectural modularization of codegen backends).

## 3. Source Plans

- **VIRC-PLN-0004** Phase 10: Split remaining large compiler domains in order: parser (Domain 1) → AST-to-MIR lowering (Domain 2) → LIR/codegen (Domain 3) → CLI/main (Domain 4) → diagnostics (Domain 5) → IDE/tool JSON (Domain 6).

## 4. Implementation Summary

Domain 3 decomposed four major monolithic compiler components:

### 4.1 ARM64 Codegen (`compiler/src/lower/lir_codegen/`)
Original `compiler/src/lower/lir_codegen.vri` (~4,800 lines) decomposed into 7 leaf submodules and 1 thin orchestrator:
- `lir_codegen/types.vri` (634 lines, 551 logical): Calling conventions, ABI frames, relocations, fixups, constants.
- `lir_codegen/intrinsics.vri` (966 lines, 916 logical): Vector and scalar intrinsic instruction lowering.
- `lir_codegen/calls.vri` (637 lines, 520 logical): Direct/indirect function calls, FFI dispatch, basic print stubs.
- `lir_codegen/rt_stubs_base.vri` (798 lines, 657 logical): String concatenation, memory allocation, bump pointer helpers.
- `lir_codegen/rt_stubs_math.vri` (1,175 lines, 908 logical): Tensor math, quantized kernels, ML runtime stubs.
- `lir_codegen/emit_vector.vri` (329 lines, 324 logical): Vector load/store, shuffle, and SIMD instruction emission.
- `lir_codegen/emit_func.vri` (950 lines, 924 logical): Function prologue, epilogue, register saving, basic block iteration.
- `lir_codegen.vri` (305 lines, 261 logical): Thin orchestrator coordinating module compilation.

### 4.2 Machine Code Lowering (`compiler/src/lower/lir_to_mc/`)
Original `compiler/src/lower/lir_to_mc.vri` (~3,000 lines) decomposed into 4 leaf submodules and 1 thin orchestrator:
- `lir_to_mc/common.vri` (115 lines, 94 logical): Target-independent instruction encoding definitions.
- `lir_to_mc/arm64.vri` (909 lines, 878 logical): ARM64 instruction encoding emitters.
- `lir_to_mc/x86_64.vri` (927 lines, 889 logical): x86-64 instruction encoding emitters.
- `lir_to_mc/riscv64.vri` (1,101 lines, 1054 logical): RISC-V 64 instruction encoding emitters.
- `lir_to_mc.vri` (27 lines, 21 logical): Thin orchestrator dispatching to architecture emitters.

### 4.3 x86-64 Codegen (`compiler/src/lower/lir_codegen_x86/`)
Original `compiler/src/lower/lir_codegen_x86.vri` (~3,500 lines) decomposed into 6 leaf submodules and 1 thin orchestrator:
- `lir_codegen_x86/types.vri` (300 lines, 250 logical): x86-64 ABI registers, scratch definitions, fixup tables.
- `lir_codegen_x86/intrinsics.vri` (633 lines, 600 logical): x86-64 intrinsic instructions.
- `lir_codegen_x86/calls.vri` (138 lines, 132 logical): SysV / Win64 calling conventions and calls.
- `lir_codegen_x86/rt_stubs_base.vri` (344 lines, 261 logical): String and heap allocation stubs for x86-64.
- `lir_codegen_x86/rt_stubs_math.vri` (1,070 lines, 916 logical): Tensor and matrix math stubs for x86-64.
- `lir_codegen_x86/emit_func.vri` (887 lines, 869 logical): Function emission and block linearization for x86-64.
- `lir_codegen_x86.vri` (205 lines, 182 logical): Thin orchestrator.

### 4.4 WebAssembly / WASI Codegen (`compiler/src/lower/lir_codegen_wasm/`)
Original `compiler/src/lower/lir_codegen_wasm.vri` (1,465 lines, 1,313 logical lines) decomposed into:
- `lir_codegen_wasm/rt_stubs.vri` (498 lines, 452 logical): WASM opcode constants, LEB128/section encoders, runtime helpers, unsupported diagnostic handler.
- `lir_codegen_wasm.vri` (986 lines, 861 logical): Supported instruction validation, WASI module structure, function body emission.

All modules are registered in `compiler/module.list` and bundled without drift into `compiler/generated/virc.vri`.

## 5. Changes by Component

- **`compiler/src/lower/lir_codegen/`**: Directory created with 7 leaf submodules; `lir_codegen.vri` converted to thin orchestrator.
- **`compiler/src/lower/lir_to_mc/`**: Directory created with 4 leaf submodules; `lir_to_mc.vri` converted to thin orchestrator.
- **`compiler/src/lower/lir_codegen_x86/`**: Directory created with 6 leaf submodules; `lir_codegen_x86.vri` converted to thin orchestrator.
- **`compiler/src/lower/lir_codegen_wasm/`**: Directory created with `rt_stubs.vri`; `lir_codegen_wasm.vri` reduced to 986 lines.
- **`compiler/module.list`**: 18 new submodules registered in proper topological dependency order.
- **`compiler/generated/virc.vri`**: Resynchronized with zero drift (`python3 tools/sync_virc.py --check` passes).

## 6. Deviations from Plan

| Deviation | Description | Resolution |
|-----------|-------------|------------|
| `emit_lir_arm64_vector` instruction fields | Instruction fields `ins_typ`, `ins_dst`, `ins_src1`, `ins_src2` were read outside the function in the monolithic version. | Explicitly read from `ins` at function entry in `emit_vector.vri`. |
| `sync_virc.py` append flag syntax | `sync_virc.py` requires `--add-module <path>` and `--before <anchor>` flags to insert new module markers before synchronizing. | Used precise flags for all 18 submodules. |

## 7. Verification

All quality gates passed after each component decomposition:

| Gate | Result | Evidence |
|------|--------|----------|
| `python3 tools/sync_virc.py --check` | ✅ PASS | Zero bundle drift reported across all submodules |
| Self-compile `/Users/gengyang/Vir/bin/virc compiler/generated/virc.vri -o bin/virc` | ✅ PASS | 2,450 functions lowered and compiled into executable |
| `codesign -s - -f bin/virc` | ✅ PASS | Valid ad-hoc signature applied on macOS |
| `python3 tests/cli_contract/runner.py` | ✅ **43/43 PASS** | All CLI contract tests passed in 41.4s |
| `./run_tests.sh min` | ✅ **409/413 PASS** | Exact match with historical baseline (4 expected failures) |
| `python3 tools/check_pass_architecture.py` | ✅ PASS | Clean module boundaries and no architecture violations |
| `python3 tools/paper.py validate` | ✅ PASS | 69 production papers valid |

## 8. Acceptance Criteria

- [x] All Domain 3 canonical source files comply with ≤ 1,200 logical lines limit.
- [x] Submodules registered in `compiler/module.list`.
- [x] Zero bundle drift between `compiler/src/` and `compiler/generated/virc.vri`.
- [x] Complete self-host compile and codesign succeed.
- [x] All 43 CLI contract tests pass.
- [x] Min test suite preserves the historical 409/413 baseline.
- [x] Architecture validation passes.
- [x] Reciprocal paper backlinks and registry updated.

## 9. Known Limitations

- No regressions introduced. The 4 pre-existing test failures in `./run_tests.sh min` remain unchanged from the baseline.

## 10. Remaining Work

Per `VIRC-PLN-0004` Phase 10 ordering:
1. ~~Parser~~ — **DONE** (`VIRC-RPT-0011`)
2. ~~AST-to-MIR lowering~~ — **DONE** (`VIRC-RPT-0012`)
3. ~~LIR & native codegen~~ — **DONE** (this report)
4. **CLI/main** (`compiler/src/main.vri`: 3,733 logical lines) — NEXT
5. **Diagnostics**
6. **IDE/tool JSON**

## 11. Conclusion

REQUIRES_FOLLOWUP

Phase 10 Domain 3 (LIR and native codegen modularization) is complete and verified. Followup is required for Domain 4 (CLI/main modularization) in accordance with VIRC-PLN-0004.

## 12. Related Papers

- `VIRC-ISS-0006` — Monolithic compiler pass files
- `VIRC-ISS-0009` — Native codegen architecture conflation
- `VIRC-PLN-0004` — Overarching modularization plan (Phase 10)
- `VIRC-RPT-0011` — Phase 10 Domain 1: Parser modularization report
- `VIRC-RPT-0012` — Phase 10 Domain 2: AST-to-MIR lowering modularization report

## 13. Revision History

| Rev | Date       | Author    | Change                  |
|-----|------------|-----------|-------------------------|
| 1.0 | 2026-10-03 | compiler  | Initial accepted report |
