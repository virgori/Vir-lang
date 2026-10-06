---
id: "VIRC-RPT-0017"
type: "REPORT"
domain: "VIRC"
title: "Eliminate redundant include and selective import pairs report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "module-resolution"
  - "compiler-source-layout"
  - "self-hosting"
related:
  issues:
    - "VIRC-ISS-0007"
    - "VIRC-ISS-0009"
  plans:
    - "VIRC-PLN-0005"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "include"
  - "import"
  - "dependency-cleanup"
  - "module-identity"
  - "architecture-check"
---

# VIRC-RPT-0017 — Eliminate redundant include and selective import pairs report

## 1. Executive Summary

This report documents the complete implementation, verification, and closure of [VIRC-ISS-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0007_compiler_sources_redundantly_combine_include_with_selective_import.md) under [VIRC-PLN-0005](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0005_eliminate_redundant_include_and_selective_import_pairs_across_compiler_sources.md).

All redundant same-module `include` and selective `import ... from` pairs across canonical compiler sources (`compiler/src/**/*.vri`) have been eliminated. Automated deterministic architecture checks (`tools/check_module_dependencies.py` integrated into `tools/check_pass_architecture.py`) now enforce the single-declaration invariant across all 252 compiler source files. Generated bundle synchronizer markers in `compiler/generated/virc.vri` were synchronized with zero drift. Full CLI contract tests (43/43), standard test suite (409/413 baseline), and 3-stage self-hosting bit-identical fixed point (`cmp -n 19791936 bin/virc_stage2 bin/virc_stage3` exit code 0) were verified.

## 2. Source Issues

- [VIRC-ISS-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0007_compiler_sources_redundantly_combine_include_with_selective_import.md) — Compiler sources redundantly combine include with selective import.

## 3. Source Plans

- [VIRC-PLN-0005](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0005_eliminate_redundant_include_and_selective_import_pairs_across_compiler_sources.md) — Eliminate redundant include and selective import pairs across compiler sources.

## 4. Implementation Summary

1. **Automated Dependency Checker**:
   - `tools/check_module_dependencies.py` was created to scan all `.vri` files in `compiler/src/`, extract `include` and `import ... from` targets, and detect duplicate declarations of canonical Module IDs.
   - Integrated dependency validation directly into `tools/check_pass_architecture.py` to prevent regression.

2. **Source Cleanup**:
   - Systematically eliminated redundant `include` and redundant `import` statements across 53 affected files in `compiler/src/` (semantic, frontend, ir, lower, cli, diagnostic, ide, main).
   - In `compiler/src/main.vri`, removed redundant imports for `binary`, `rt.alloc`, `rt.string_rt`, `rt.vec_rt`, and `rt.io` whose declarations are fully provided by their respective includes.
   - Removed redundant imports in newly modularized pass orchestrators (`compiler/src/semantic/passTypecheck.vri`, `compiler/src/semantic/passBorrow.vri`).

3. **Bundle & Marker Synchronization**:
   - Updated `# @vir_source <file> <line>` markers in `compiler/generated/virc.vri` to precisely track source line shifts in multi-section source units (`opt_backend.vri`, `lexer.vri`, `target_spec.vri`, `pipeline.vri`, `mir_opt_pipeline.vri`, `main.vri`).
   - Verified zero drift with `python3 tools/sync_virc.py --check`.

4. **Self-Hosting Compiler Fixes**:
   - Added `as int` casts to `pass8_state_path(...)` in `compiler/src/semantic/borrow/walk_access.vri` and `compiler/src/semantic/borrow/walk_call.vri` to ensure clean type conformance in IDE fact generation.
   - Corrected integer cast for `rt_itoa(environment) as int` in `vircResolveUi` (`compiler/generated/virc.vri:80633`).

## 5. Changes by Component

### `tools/`
- `tools/check_module_dependencies.py`: Canonical dependency parser and duplicate checker.
- `tools/check_pass_architecture.py`: Linked `check_module_dependencies` into the pass architecture gate.

### `compiler/src/`
- `compiler/src/main.vri`: Eliminated redundant imports of `binary`, `rt.alloc`, `rt.string_rt`, `rt.vec_rt`, `rt.io`.
- `compiler/src/semantic/passTypecheck.vri`: Eliminated redundant imports for `symbol_table`, `scope_tree`, `context`, `parser`.
- `compiler/src/semantic/passBorrow.vri`: Eliminated redundant imports for `symbol_table`, `scope_tree`, `context`, `parser`.
- `compiler/src/semantic/borrow/walk_access.vri`: Added `as int` cast to `pass8_state_path(...)`.
- `compiler/src/semantic/borrow/walk_call.vri`: Added `as int` cast to `pass8_state_path(...)`.
- 50+ other compiler sources across frontend, ir, lower, backend, and diagnostics cleaned of redundant include/import pairs.

### `compiler/generated/`
- `compiler/generated/virc.vri`: Synchronized from modular sources; updated `# @vir_source` markers to track line deltas; fixed `rt_itoa` cast in `vircResolveUi`.

## 6. Deviations from Plan

None. Implementation strictly followed [VIRC-PLN-0005](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0005_eliminate_redundant_include_and_selective_import_pairs_across_compiler_sources.md).

## 7. Verification

### Tests

| Test Suite | Command | Result | Evidence |
|---|---|---|---|
| Module Dependency Hygiene | `python3 tools/check_module_dependencies.py` | PASS | 252 compiler source files clean (0 violations) |
| Pass Architecture | `python3 tools/check_pass_architecture.py` | PASS | 3 orchestrators, stdlib clean, 252 module dependencies clean |
| Generated Bundle Sync | `python3 tools/sync_virc.py --check` | PASS | 0 bundle drift |
| CLI Contract Suite | `python3 tests/cli_contract/runner.py` | PASS | 43/43 PASS in 32.9s |
| Module Fixtures Suite | `tests/modules/test_*.vri` | PASS | 5/5 fixtures compiled & executed clean from root, subdir, and /tmp |
| Full Test Suite | `./run_tests.sh min` | PASS | 409/413 PASS (exact historical baseline) |
| Self-Host 3-Stage Fixed Point | `cmp -n 19791936 bin/virc_stage2 bin/virc_stage3` | PASS | Bit-identical machine code (0 byte diff) |
| VPS Governance | `python3 tools/paper.py validate` | PASS | 72 production papers valid |

### Regression

Zero regression against historical test baseline:
- 409 passed, 4 failed (the 4 known expected failures in §11 and §26 tracked by VIRC-ISS-0003 and VIRC-ISS-0005).

### Conformance

- include-only fixtures verify whole-module load without selective import.
- import-only fixtures verify selective import without preceding include.
- Diamond dependencies deduplicate to single canonical Module ID.

## 8. Acceptance Criteria

Mapping 1:1 with [VIRC-ISS-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0007_compiler_sources_redundantly_combine_include_with_selective_import.md) Section 10:

- [x] A deterministic checker resolves canonical Module IDs and reports every compiler source that both includes and selectively imports the same module (`tools/check_module_dependencies.py`).
- [x] Compiler canonical sources contain no redundant same-module pair (0 violations across 252 files).
- [x] Include-only positive fixtures cover functions, entities/enums, constants, and nested dependencies (`tests/modules/test_include_only.vri`).
- [x] Import-only positive fixtures prove selective imports require no prior include and load each canonical module once (`tests/modules/test_import_only.vri`).
- [x] Diamond dependencies and repeated includes still deduplicate to one Module ID and retain useful cycle diagnostics (`tests/modules/test_diamond_dedup.vri`, `tests/modules/test_flat_diamond.vri`).
- [x] Modular and generated compiler sources are synchronized through the authoritative generation workflow (`python3 tools/sync_virc.py --check`).
- [x] Stage 1 -> stage 2 -> stage 3 self-hosting passes the repository fixed-point contract, with representative module tests run from repository root, a subdirectory, and an unrelated CWD (`cmp` exit code 0).

## 9. Known Limitations

- Empty-export selective imports fallback behavior is tracked separately under `VIRC-ISS-0008`.
- TargetSpec standardization and multi-target native codegen consolidation remain tracked under `VIRC-ISS-0009`.

## 10. Remaining Work

None under VIRC-ISS-0007 / VIRC-PLN-0005.

## 11. Conclusion

READY_FOR_CLOSE. All acceptance criteria for [VIRC-ISS-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0007_compiler_sources_redundantly_combine_include_with_selective_import.md) and milestones of [VIRC-PLN-0005](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0005_eliminate_redundant_include_and_selective_import_pairs_across_compiler_sources.md) have been satisfied and rigorously verified across all quality gates.

## 12. Related Papers

- [VIRC-ISS-0007](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0007_compiler_sources_redundantly_combine_include_with_selective_import.md) — Compiler sources redundantly combine include with selective import.
- [VIRC-PLN-0005](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0005_eliminate_redundant_include_and_selective_import_pairs_across_compiler_sources.md) — Eliminate redundant include and selective import pairs across compiler sources.
- [VIRC-ISS-0006](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0006_compiler_sources_are_coupled_to_stdlib_and_oversized_pass_files.md) — Compiler sources are coupled to stdlib and oversized pass files.
- [VIRC-ISS-0008](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0008_selective_imports_accept_symbols_that_are_not_exported.md) — Selective imports accept symbols that are not exported.
- [VIRC-ISS-0009](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0009_native_codegen_conflates_architecture_os_abi_and_object_format.md) — Native codegen conflates architecture OS ABI and object format.
- [VIRC-RPT-0016](file:///Users/gengyang/Vir-3.0/papers/VIRC/reports/VIRC-RPT-0016_phase_11_bundle_and_transition_deletion_report.md) — Phase 11 bundle and transition deletion report.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial report for VIRC-ISS-0007 / VIRC-PLN-0005 completion and closure |
| 2026-10-03 | Linked VIRC-ISS-0009 |
