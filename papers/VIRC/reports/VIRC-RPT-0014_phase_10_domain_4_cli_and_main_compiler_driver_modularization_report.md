---
id: "VIRC-RPT-0014"
type: "REPORT"
domain: "VIRC"
title: "Phase 10 Domain 4 CLI and main compiler driver modularization report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "driver"
components:
  - "main-driver"
  - "include-expander"
  - "import-expander"
  - "module-resolver"
  - "path-util"
  - "legacy-macho"
  - "pass-architecture"
  - "module-list"
related:
  issues:
    - "VIRC-ISS-0006"
  plans:
    - "VIRC-PLN-0004"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "driver"
  - "cli"
  - "preprocessing"
  - "modularization"
  - "phase10"
---

# VIRC-RPT-0014 — Phase 10 Domain 4 CLI and main compiler driver modularization report

## 1. Executive Summary

In accordance with `VIRC-PLN-0004` Phase 10 Domain 4 and `VIRC-ISS-0006`, the monolithic compiler driver (`compiler/src/main.vri`, 4,248 raw lines, 3,733 logical lines) has been decomposed into **5 cohesive leaf submodules** and **1 thin orchestrator** under `compiler/src/main/`. The orchestrator `compiler/src/main.vri` has been reduced from 3,733 to **171 logical lines** (268 raw lines, −93.7%), satisfying all orchestrator and leaf LOC constraints (≤ 1,200 logical lines per non-orchestrator file). The self-hosting compiler compiles cleanly, codesigns, passes all 43 CLI contract tests, preserves the exact 409/413 regression test baseline, and verifies architecture boundaries.

## 2. Source Issues

- **VIRC-ISS-0006** — Compiler sources are coupled to stdlib and oversized pass files (mandates non-generated canonical source files ≤ 1,200 logical lines).

## 3. Source Plans

- **VIRC-PLN-0004** Phase 10: Split remaining large compiler domains in order: parser (Domain 1) → AST-to-MIR lowering (Domain 2) → LIR/codegen (Domain 3) → CLI/main (Domain 4) → diagnostics (Domain 5) → IDE/tool JSON (Domain 6).

## 4. Implementation Summary

The original monolithic `compiler/src/main.vri` was decomposed along functional and data ownership boundaries:

| Submodule | Raw Lines | Logical Lines | Responsibility |
|---|---|---|---|
| `compiler/src/main/legacy_macho.vri` | 905 | 654 | Legacy Q-IR ARM64 emitter, Mach-O executable builder, header generation, fixup layout |
| `compiler/src/main/path_util.vri` | 520 | 430 | Global include/registry state, path normalization, file search helpers, error reporting |
| `compiler/src/main/module_resolver.vri` | 669 | 620 | Project registry parsing (`virc_registry_load`), target module resolution (`resolve_include_target`), source loader |
| `compiler/src/main/include_expander.vri` | 980 | 843 | Include cycle detection (`check_active_cycle`), source wrapping, string sanitization, text-level include splice |
| `compiler/src/main/import_expander.vri` | 999 | 926 | Import statement parsing, enum variant extraction, function chunk renaming, selective export splicing |
| `compiler/src/main.vri` (orchestrator) | 268 | 171 | Thin pipeline orchestrator, AST program merging, legacy `compile` entrypoint, IDE module capture, public exports |

All 5 leaf submodules satisfy the **≤ 1,200 logical lines** hard constraint.

New module names registered in `compiler/module.list` (lines 13–18):
`main_legacy_macho`, `main_path_util`, `main_module_resolver`, `main_include_expander`, `main_import_expander`, `main`.

## 5. Changes by Component

- **`compiler/src/main/`** (new directory):
  - 5 leaf submodules created carrying exact functional logic extracted from `main.vri`.
- **`compiler/src/main.vri`**:
  - Reduced from 4,248 to 268 raw lines (171 logical lines).
  - Orchestrates submodule includes and exposes compiler exports.
- **`compiler/module.list`**:
  - Registered 5 submodules in proper topological dependency sequence before `main`.
- **`tools/sync_virc.py`**:
  - Enhanced `--before` anchor to support explicit marker line numbers (e.g. `compiler/src/main.vri:28`).
- **`compiler/generated/virc.vri`**:
  - Synchronized with zero bundle drift (`python3 tools/sync_virc.py --check` passes).

## 6. Deviations from Plan

No material deviations from the approved plan.

## 7. Verification

All quality gates passed at commit `6adf7bd`:

| Gate | Result | Evidence |
|---|---|---|
| `python3 tools/sync_virc.py --check` | ✅ PASS | Zero bundle drift reported across all submodules |
| Self-compile `/Users/gengyang/Vir/bin/virc compiler/generated/virc.vri -o bin/virc` | ✅ PASS | 2,450 functions lowered and compiled into executable |
| `codesign -s - -f bin/virc` | ✅ PASS | Valid ad-hoc signature applied on macOS |
| `python3 tests/cli_contract/runner.py` | ✅ **43/43 PASS** | All CLI contract tests passed in 34.2s |
| `./run_tests.sh min` | ✅ **409/413 PASS** | Exact match with historical baseline (4 expected failures) |
| `python3 tools/check_pass_architecture.py` | ✅ PASS | Clean module boundaries and no architecture violations |
| `python3 tools/paper.py validate` | ✅ PASS | 70 production papers valid |

## 8. Acceptance Criteria

- [x] All Domain 4 canonical source files comply with ≤ 1,200 logical lines limit.
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
3. ~~LIR & native codegen~~ — **DONE** (`VIRC-RPT-0013`)
4. ~~CLI/main~~ — **DONE** (this report)
5. **Diagnostics**
6. **IDE/tool JSON**

## 11. Conclusion

REQUIRES_FOLLOWUP

Phase 10 Domain 4 (CLI and main compiler driver modularization) is complete and verified. Followup is required for Domain 5 (Diagnostics modularization) in accordance with VIRC-PLN-0004.

## 12. Related Papers

- `VIRC-ISS-0006` — Monolithic compiler pass files
- `VIRC-PLN-0004` — Overarching modularization plan (Phase 10)
- `VIRC-RPT-0011` — Phase 10 Domain 1: Parser modularization report
- `VIRC-RPT-0012` — Phase 10 Domain 2: AST-to-MIR lowering modularization report
- `VIRC-RPT-0013` — Phase 10 Domain 3: LIR and native codegen modularization report

## 13. Revision History

| Rev | Date       | Author    | Change                  |
|-----|------------|-----------|-------------------------|
| 1.0 | 2026-10-03 | compiler  | Initial accepted report |
