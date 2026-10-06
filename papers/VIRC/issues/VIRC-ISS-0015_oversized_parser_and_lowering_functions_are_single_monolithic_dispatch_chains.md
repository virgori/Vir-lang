---
id: "VIRC-ISS-0015"
type: "ISSUE"
domain: "VIRC"
title: "Oversized parser and lowering functions are single monolithic dispatch chains"
status: "CLOSED"
severity: "S3"
priority: "P3"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "parser"
  - "lowering"
  - "compiler-source-layout"
related:
  issues: []
  plans:
    - "VIRC-PLN-0010"
  reports:
    - "VIRC-RPT-0022"
supersedes: null
superseded_by: null
tags:
  - "parser-dispatch"
  - "lowering-dispatch"
  - "modularization"
  - "function-decomposition"
---

# VIRC-ISS-0015 — Oversized parser and lowering functions are single monolithic dispatch chains

## 1. Summary

In the compiler frontend and lowering subsystems, key dispatch functions were implemented as giant monolithic if-chains spanning over 1,000 lines in a single function body:
1. `parse_statement_impl` in `compiler/src/frontend/parser/stmt_dispatch.vri` (1,212 lines, 68 sequential if-blocks).
2. `lower_stmt_control` in `compiler/src/lower/ast_to_mir/stmt_control.vri` (1,095 lines, 23 statement lowering branches).

These giant functions suffered from excessive basic block counts, high register pressure, oversized stack frames, and unmaintainable monolithic source files.

## 2. Context

Following `VIRC-ISS-0011` (driver modularization) and `VIRC-ISS-0012` (module file splitting), these two functions remained the last oversized dispatchers in the compiler codebase where top-level control dispatch could be decomposed into cohesive domain-specific submodules.

## 3. Expected Behavior

1. `parse_statement_impl` is refactored into a clean top-level dispatcher delegating to 5 dedicated modules under `compiler/src/frontend/parser/stmt_dispatch/`: `modifiers.vri`, `declarations.vri`, `concurrency.vri`, `try_stmt.vri`, and `name_stmt.vri`.
2. `lower_stmt_control` is refactored into a clean top-level dispatcher delegating to 6 dedicated modules under `compiler/src/lower/ast_to_mir/stmt_control/`: `arena_scan.vri`, `loops.vri`, `jumps.vri`, `pattern.vri`, `error.vri`, and `async_arena.vri`.
3. All new submodules are registered in `compiler/module.list`.
4. Bundle synchronization reports zero drift.
5. All 7 quality gates pass, including bit-identical 3-stage self-hosting fixed point.

## 4. Actual Behavior

Before this change:
- `compiler/src/frontend/parser/stmt_dispatch.vri` was 1,212 lines.
- `compiler/src/lower/ast_to_mir/stmt_control.vri` was 1,095 lines.
- Compiling these giant single functions resulted in binary sizes of ~19.8 MB and ~95s compile times.

## 5. Reproduction

```sh
wc -l compiler/src/frontend/parser/stmt_dispatch.vri compiler/src/lower/ast_to_mir/stmt_control.vri
```

## 6. Evidence

- CONFIRMED: `parse_statement_impl` contained 68 top-level if-branches that were easily classified into 5 distinct syntactic categories.
- CONFIRMED: `lower_stmt_control` contained 23 distinct `AstType` lowering blocks that shared the uniform signature `(b: &MirBuilder, stmt: &AstNode) -> MirBuilder`.
- CONFIRMED: Extracting both dispatchers reduced `stmt_dispatch.vri` to 385 lines and `stmt_control.vri` to 125 lines.
- CONFIRMED: Compiling the decomposed functions reduced self-hosted binary size from 19,797,871 bytes to 16,432,591 bytes (a 17% code density improvement) and compile time from ~95s to ~88s.

## 7. Scope

### Affected
- `compiler/src/frontend/parser/stmt_dispatch.vri` and `compiler/src/frontend/parser/stmt_dispatch/` (5 modules)
- `compiler/src/lower/ast_to_mir/stmt_control.vri` and `compiler/src/lower/ast_to_mir/stmt_control/` (6 modules)
- `compiler/module.list`
- `compiler/generated/virc.vri`

### Not affected / Unknown
- Language syntax and semantics (zero language changes).
- AST node representations and MIR instruction sets.
- Backend code emitters.

## 8. Impact

Severity: S3 (maintainability, compiler optimization & compilation speed).
Priority: P3 (architectural clean code).

## 9. Preliminary Analysis

Extracting statement parser handlers and MIR statement lowering routines into cohesive modules eliminates gigantic single-function stack frames and basic block graphs without altering compiler semantics.

## 10. Acceptance Criteria

- [x] `parse_statement_impl` decomposed into 5 submodules under `compiler/src/frontend/parser/stmt_dispatch/`.
- [x] `lower_stmt_control` decomposed into 6 submodules under `compiler/src/lower/ast_to_mir/stmt_control/`.
- [x] All 11 new modules registered in `compiler/module.list`.
- [x] 0 bundle drift (`tools/sync_virc.py --check`).
- [x] 0 dependency violations (`tools/check_module_dependencies.py`).
- [x] CLI contracts (43/43) and module fixtures (5/5) pass.
- [x] Min test suite passes (409/413 historical baseline).
- [x] 3-stage self-hosting fixed point verified bit-identical.
- [x] Linked PLAN `VIRC-PLN-0010` completed and REPORT `VIRC-RPT-0022` accepted.

## 11. Related Papers

- `VIRC-ISS-0011` — Compiler driver is monolithic and generated bundle owns self-referential glue.
- `VIRC-ISS-0012` — Oversized compiler modules mix unrelated declaration groups.
- `VIRC-PLN-0010` — Decompose monolithic parser and lowering dispatch functions into submodules.
- `VIRC-RPT-0022` — Decompose monolithic parser and lowering dispatch functions into submodules report.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created, triaged, implemented, and verified via VIRC-RPT-0022; closed issue |
