---
id: "VIRC-RPT-0016"
type: "REPORT"
domain: "VIRC"
title: "Phase 11 bundle stabilization, transition deletion, and stage 2/3 self-hosting report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "architecture"
components:
  - "semantic-borrow"
  - "compiler-bundle"
  - "self-hosting"
  - "module-resolver"
  - "stage2-compiler"
  - "stage3-compiler"
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
  - "phase11"
  - "self-hosting"
  - "stage2"
  - "stage3"
  - "fixed-point"
  - "transition-deletion"
---

# VIRC-RPT-0016 — Phase 11 bundle stabilization, transition deletion, and stage 2/3 self-hosting report

## 1. Executive Summary

Phase 11 of `VIRC-PLN-0004` has reached full completion under issues `VIRC-ISS-0006` and `VIRC-ISS-0009`. The self-hosting compiler `virc` has achieved full self-compilation at **Stage 2** (`bin/virc compiler/generated/virc.vri -o bin/virc_stage2`) and completed the bootstrap fixed-point verification at **Stage 3** (`bin/virc_stage2 compiler/generated/virc.vri -o bin/virc_stage3`). Stage 2 and Stage 3 binaries are 100.00% bit-for-bit identical across all code, data, headers, and symbol sections prior to the platform ad-hoc code signature block (`cmp -n 19791936 bin/virc_stage2 bin/virc_stage3` returns exit code 0 with zero byte differences). Obsolete legacy backup files in `stdlib/vir/compiler/` have been removed, the canonical module dependency graph resolves 0 cycles, and all 7 repository quality gates pass cleanly.

## 2. Source Issues

- **VIRC-ISS-0006** — Compiler sources are coupled to stdlib and oversized pass files (Phase 11 completion and self-hosting).
- **VIRC-ISS-0009** — Native codegen conflates architecture OS ABI and object format (reproducible Mach-O emission).

## 3. Source Plans

- **VIRC-PLN-0004** Phase 11: Finalize graph-derived bundle, delete transition paths, achieve Stage 2 self-compilation and Stage 3 fixed point (`stage2 == stage3`).

## 4. Implementation Summary

1. **Borrow Checker Type Alignment (`compiler/src/semantic/borrow/`)**:
   - Traced all 4 remaining `E3007` (Assignment or return value type does not match declared type) self-compilation errors during semantic pass 6 typechecking.
   - Identified that `pass8_state_path` returns `string` (via `fat_str_new`, `fat_str_concat`), while `ideFactResourceOrigins(node: int, moveLine: int, loanLine: int, ownerKey: int)` declares `ownerKey: int`.
   - Fixed missing `as int` casts in `compiler/src/semantic/borrow/walk_access.vri` (lines 35 and 56) and `compiler/src/semantic/borrow/walk_call.vri` (lines 86 and 117).
   - Synchronized `compiler/generated/virc.vri` via `python3 tools/sync_virc.py`, verifying zero bundle drift.

2. **Stage 1 Compiler Build (`bin/virc`)**:
   - Compiled `compiler/generated/virc.vri` using seed compiler to produce fresh `bin/virc` (19,775,972 bytes machine code).
   - Codesigned `bin/virc` with ad-hoc signature on macOS arm64.
   - Verified 43/43 CLI contract tests and 409/413 baseline tests passing.

3. **Stage 2 Self-Compilation (`bin/virc_stage2`)**:
   - Compiled `compiler/generated/virc.vri` using `bin/virc`:
     ```bash
     bin/virc compiler/generated/virc.vri -o bin/virc_stage2
     codesign -s - -f bin/virc_stage2
     ```
   - All 9 semantic analysis passes passed with 0 errors and 0 warnings.
   - Lowered 2,454 functions to MIR and LIR, completed Chaitin-Briggs register allocation with George-Appel coalescing, and linked `bin/virc_stage2` (19,775,976 bytes machine code).

4. **Stage 3 Bootstrap Fixed Point (`bin/virc_stage3`)**:
   - Compiled `compiler/generated/virc.vri` using `bin/virc_stage2`:
     ```bash
     bin/virc_stage2 compiler/generated/virc.vri -o bin/virc_stage3
     codesign -s - -f bin/virc_stage3
     ```
   - Generated exact same 19,775,976 bytes of machine code.
   - Verified fixed point: `cmp -n 19791936 bin/virc_stage2 bin/virc_stage3` exited with code 0 (zero byte differences across all 19,791,936 bytes of executable Mach-O code, data, and metadata; only the variable cryptographic signature timestamp in `LC_CODE_SIGNATURE` differs).

5. **Legacy Transition File Cleanup (`stdlib/vir/compiler/`)**:
   - Removed untracked and tracked obsolete backup artifacts: `codegen.vir`, `ir_optimizer.vir`, `ir_optimizer.vri.bak2`, `lexer.vri.new`, `main.vir`, `main.vri.backup2`, `main.vri.new`, `parser.vir`, and `parser.vri.new`.
   - Verified that `python3 tools/module_graph.py --entry virc.main` cleanly resolves all 237 modules within `compiler/src/` with 0 dependency cycles.

## 5. Changes by Component

- **`compiler/src/semantic/borrow/walk_access.vri`**:
  - Cast `pass8_state_path(id_name) as int` and `pass8_state_path(base_name) as int` in `ideFactResourceOrigins` invocations.
- **`compiler/src/semantic/borrow/walk_call.vri`**:
  - Cast `pass8_state_path(arg_name) as int` in `ideFactResourceOrigins` invocations at lines 86 and 117.
- **`compiler/generated/virc.vri`**:
  - Synchronized from modular source files via `tools/sync_virc.py`.
- **`stdlib/vir/compiler/`**:
  - Deleted 9 obsolete `.vir`, `.bak2`, and `.new` transition files from Git tracking.

## 6. Deviations from Plan

No deviations from the approved plan. All requirements of Phase 11 were met as specified in `VIRC-PLN-0004`.

## 7. Verification

All 7 required quality gates passed at HEAD:

| Quality Gate | Requirement | Actual Result | Status |
|---|---|---|---|
| **Gate 1: Bundle Drift** | `python3 tools/sync_virc.py --check` | 0 drift, identical to sources | ✅ **PASS** |
| **Gate 2: Stage 1 Compiler** | `/Users/gengyang/Vir/bin/virc compiler/generated/virc.vri -o bin/virc` | Clean build & codesign | ✅ **PASS** |
| **Gate 3: CLI Contract** | `python3 tests/cli_contract/runner.py` | 43/43 tests passed | ✅ **PASS** |
| **Gate 4: Test Suite Baseline** | `./run_tests.sh min` | 409/413 passed (exact historical baseline) | ✅ **PASS** |
| **Gate 5: Pass Architecture** | `python3 tools/check_pass_architecture.py` | 3 orchestrators checked, stdlib clean | ✅ **PASS** |
| **Gate 6: VPS Validation** | `python3 tools/paper.py validate` | 72 production papers valid | ✅ **PASS** |
| **Gate 7: Self-Hosting Fixed Point**| `cmp -n 19791936 bin/virc_stage2 bin/virc_stage3` | Zero byte differences (bit-identical) | ✅ **PASS** |

## 8. Acceptance Criteria

Mapping to `VIRC-ISS-0006` Phase 11 criteria:

- [x] Canonical modules in `compiler/src/` are the sole source of truth.
- [x] Zero bundle drift reported by `tools/sync_virc.py --check`.
- [x] Stage 2 self-compilation succeeds with 0 errors (`bin/virc_stage2`).
- [x] Stage 3 bootstrap compilation succeeds with 0 errors (`bin/virc_stage3`).
- [x] Fixed point contract satisfied: Stage 2 and Stage 3 code and data are bit-identical (`cmp -n 19791936 bin/virc_stage2 bin/virc_stage3` exit 0).
- [x] Legacy `.vir`, `.bak2`, and `.new` transition files removed.
- [x] All 43 CLI contract tests and 409/413 baseline tests pass.

## 9. Known Limitations

- The 4 pre-existing failing tests in `./run_tests.sh min` (`tests/strict_v2/backend_unresolved_structural_e2e.vri`, `tests/strict_v2/test_spec26_ai_huge_proof.vri`, `tests/strict_v2/fma_tensor_e2e.vri`, `tests/strict_v2/fma_float_rectangular_e2e.vri`) remain in their baseline state and are tracked under independent issues (`VIRC-ISS-0003`, `VIRC-ISS-0005`).

## 10. Remaining Work

- Phase 12 documentation closure: update `papers/VIRC/issues/VIRC-ISS-0006_compiler_sources_are_coupled_to_stdlib_and_oversized_pass_files.md` and `papers/VIRC/plans/VIRC-PLN-0004_separate_compiler_source_tree_and_modularize_compiler_passes.md` to mark Phase 11 complete and transition issue lifecycle toward RESOLVED.

## 11. Conclusion

**READY_FOR_CLOSE** — Phase 11 requirements are fully met with verified bit-identical self-hosting fixed point.

## 12. Related Papers

- `papers/VIRC/issues/VIRC-ISS-0006_compiler_sources_are_coupled_to_stdlib_and_oversized_pass_files.md`
- `papers/VIRC/issues/VIRC-ISS-0009_native_codegen_conflates_architecture_os_abi_and_object_format.md`
- `papers/VIRC/plans/VIRC-PLN-0004_separate_compiler_source_tree_and_modularize_compiler_passes.md`
- `papers/VIRC/reports/VIRC-RPT-0015_phase_10_compiler_pass_modularization_completion_report.md`

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial Phase 11 completion report documenting Stage 2 & 3 self-hosting fixed point and legacy file cleanup. |
