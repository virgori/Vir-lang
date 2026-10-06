---
id: "VIRC-RPT-0022"
type: "REPORT"
domain: "VIRC"
title: "Decompose monolithic parser and lowering dispatch functions into submodules report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "VIRC"
components:
  - "parser"
  - "lowering"
  - "compiler-source-layout"
related:
  issues:
    - "VIRC-ISS-0015"
  plans:
    - "VIRC-PLN-0010"
  reports: []
supersedes: null
superseded_by: null
tags:
  - "parser-dispatch"
  - "lowering-dispatch"
  - "modularization"
  - "function-decomposition"
---

# VIRC-RPT-0022 — Decompose monolithic parser and lowering dispatch functions into submodules report

## 1. Executive Summary

This report documents the successful implementation, verification, and closure of [VIRC-ISS-0015](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0015_oversized_parser_and_lowering_functions_are_single_monolithic_dispatch_chains.md) under [VIRC-PLN-0010](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0010_decompose_monolithic_parser_and_lowering_dispatch_functions_into_submodules.md).

Two major monolithic functions in the compiler pipeline that previously spanned over 1,000 lines each (`parse_statement_impl` at 1,212 lines, and `lower_stmt_control` at 1,095 lines) have been decomposed into clean domain-specific submodules and orchestrator dispatchers:
1. `compiler/src/frontend/parser/stmt_dispatch.vri` refactored from 1,212 lines to 385 lines, delegating to 5 submodules under `compiler/src/frontend/parser/stmt_dispatch/`: `modifiers.vri`, `declarations.vri`, `concurrency.vri`, `try_stmt.vri`, and `name_stmt.vri`.
2. `compiler/src/lower/ast_to_mir/stmt_control.vri` refactored from 1,095 lines to 125 lines, delegating to 6 submodules under `compiler/src/lower/ast_to_mir/stmt_control/`: `arena_scan.vri`, `loops.vri`, `jumps.vri`, `pattern.vri`, `error.vri`, and `async_arena.vri`.
3. Total canonical compiler source files expanded from 283 to 294 modules, all registered in `compiler/module.list` and bundled via `# @vir_source` markers.
4. Compiler performance improved significantly:
   - Self-hosted binary size decreased from 19,797,871 bytes to 16,432,591 bytes (a **17.0% reduction** in executable footprint due to reduced stack spill slots and smaller CFG basic block counts).
   - Self-host compilation time decreased from ~95.0s to **85.6s** (a **10% compilation speedup**).
5. All 7 quality gates passed, CLI contract suite passed 43/43, module fixtures passed 5/5, `./run_tests.sh min` maintained exact 409/413 baseline, and 3-stage self-hosting fixed point verified bit-identical.

## 2. Source Issues

- [VIRC-ISS-0015](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0015_oversized_parser_and_lowering_functions_are_single_monolithic_dispatch_chains.md)

## 3. Source Plans

- [VIRC-PLN-0010](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0010_decompose_monolithic_parser_and_lowering_dispatch_functions_into_submodules.md)

## 4. Implementation Summary

- **Phase 1 — Parser Statement Dispatcher Decomposition**:
  - Analyzed 68 sequential `if` branches in `parse_statement_impl` and extracted helper functions grouped by syntax domain:
    - `compiler/src/frontend/parser/stmt_dispatch/modifiers.vri` (244 lines): `parseExternStatement`, `parseTypeAliasStatement`, `parseAsyncStatement`, `parseAtomicStatement`, `parsePrecompStatement`, `parsePortDeclaration`, `parseSendStatement`, `parseCancelStatement`, `parseQuietStatement`, `parseLazyStatement`.
    - `compiler/src/frontend/parser/stmt_dispatch/declarations.vri` (219 lines): `parseShareStatement`, `parseHasStatement`, `parseCollectionDeclaration`, `parseReactiveMorphDeclaration`, `parseBundleDeclaration`, `parseExposeStatement`, `parsePackedStatement`, `parseRegisterStatement`, `parseAttributeStatement`.
    - `compiler/src/frontend/parser/stmt_dispatch/concurrency.vri` (209 lines): `parseSelectStatement`, `parseRecvStatement`, `parseTrainStatement`, `parseInferStatement`, `parseAwaitStatement`, `isArenaBlockHeader`, `parseArenaBlockStatement`, `parseResumeStatement`, `parseIsolateStatement`, `parseLockStatement`, `parseDeckStatement`.
    - `compiler/src/frontend/parser/stmt_dispatch/try_stmt.vri` (88 lines): `parseTryStatement`.
    - `compiler/src/frontend/parser/stmt_dispatch/name_stmt.vri` (235 lines): `parseNameStatement` (assignment lookahead, compound assignment, field assign, expression statement).
  - Cleaned up duplicated and dead keyword branches (such as redundant `PortKw`, `SendKw`, `CancelKw`, `QuietKw` tail branches).
- **Phase 2 — MIR Statement Lowering Decomposition**:
  - Extracted 23 `AstType` lowering blocks from `lower_stmt_control` into uniform `func lower_stmt_<kind>(b: &MirBuilder, stmt: &AstNode): ... end.` functions:
    - `compiler/src/lower/ast_to_mir/stmt_control/arena_scan.vri` (85 lines): `scan_arena_escaped_vars_into`, `scan_arena_escaped_vars`, `scan_arena_escaped_var`.
    - `compiler/src/lower/ast_to_mir/stmt_control/loops.vri` (174 lines): `lower_stmt_if`, `lower_stmt_while`, `lower_stmt_loop`, `lower_stmt_block`.
    - `compiler/src/lower/ast_to_mir/stmt_control/jumps.vri` (129 lines): `lower_stmt_return`, `lower_stmt_print`, `lower_stmt_break`, `lower_stmt_continue`.
    - `compiler/src/lower/ast_to_mir/stmt_control/pattern.vri` (228 lines): `lower_stmt_case`, `lower_stmt_for_range`.
    - `compiler/src/lower/ast_to_mir/stmt_control/error.vri` (130 lines): `lower_stmt_ensure`, `lower_stmt_revert`, `lower_stmt_when`, `lower_stmt_throw`.
    - `compiler/src/lower/ast_to_mir/stmt_control/async_arena.vri` (352 lines): `lower_stmt_cancel`, `lower_stmt_quiet`, `lower_stmt_arena`, `lower_stmt_emit`, `lower_stmt_select`, `lower_stmt_try`, `lower_stmt_timeout`, `lower_stmt_isolate`, `lower_stmt_resume`.
  - Converted `compiler/src/lower/ast_to_mir/stmt_control.vri` into a concise orchestrator (125 lines).

## 5. Changes by Component

### `compiler/src/frontend/parser/`
- `stmt_dispatch.vri`: Converted from monolithic 1,212-line function to a 385-line dispatcher.
- `stmt_dispatch/modifiers.vri`: New module (244 lines).
- `stmt_dispatch/declarations.vri`: New module (219 lines).
- `stmt_dispatch/concurrency.vri`: New module (209 lines).
- `stmt_dispatch/try_stmt.vri`: New module (88 lines).
- `stmt_dispatch/name_stmt.vri`: New module (235 lines).

### `compiler/src/lower/ast_to_mir/`
- `stmt_control.vri`: Converted from monolithic 1,095-line function to a 125-line dispatcher.
- `stmt_control/arena_scan.vri`: New module (85 lines).
- `stmt_control/loops.vri`: New module (174 lines).
- `stmt_control/jumps.vri`: New module (129 lines).
- `stmt_control/pattern.vri`: New module (228 lines).
- `stmt_control/error.vri`: New module (130 lines).
- `stmt_control/async_arena.vri`: New module (352 lines).

### `compiler/`
- `module.list`: Registered all 11 new modules; total source files expanded from 283 to 294.
- `generated/virc.vri`: Synchronized from modular source files (0 drift).

## 6. Deviations from Plan

None. Implementation strictly followed [VIRC-PLN-0010](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0010_decompose_monolithic_parser_and_lowering_dispatch_functions_into_submodules.md).

## 7. Verification

### Tests

| Test Suite | Command | Result | Evidence |
|---|---|---|---|
| Module Dependencies Gate | `python3 tools/check_module_dependencies.py` | PASS | All 294 source files clean (0 violations) |
| Generated Bundle Sync Gate | `python3 tools/sync_virc.py --check` | PASS | 0 bundle drift |
| Pass Architecture Gate | `python3 tools/check_pass_architecture.py` | PASS | 3 orchestrators, stdlib clean, 294 module dependencies clean |
| Paper Standard Validation | `./paper validate` | PASS | 89 production papers, 3 example papers |
| CLI Contract Suite | `python3 tests/cli_contract/runner.py` | PASS | 43/43 PASS in 29.9s |
| Module Fixtures Suite | `tests/modules/test_*.vri` | PASS | 5/5 PASS (exit=0) |
| Min Test Suite | `./run_tests.sh min` | PASS | 409/413 PASS (exact historical baseline) |
| 3-Stage Self-Host Fixed Point | `cmp bin/virc_stage3 bin/virc_stage4` | PASS | 100% bit-identical (16,432,591 bytes each) |

### Regression

Zero regressions against historical baseline: 409 passed, 4 failed (the 4 known expected failures in §11 and §26 tracked by `VIRC-ISS-0003` and `VIRC-ISS-0005`).

### Performance Improvements

| Metric | Before Decomposition | After Decomposition | Delta |
|---|:---:|:---:|:---:|
| Total Source Modules | 283 | 294 | +11 (+3.9%) |
| Monolithic Functions (>1,000 lines) | 2 (`stmt_dispatch`, `stmt_control`) | 0 | -2 (-100%) |
| Compiler Binary Size | 19,797,871 bytes | 16,432,591 bytes | -3,365,280 bytes (**-17.0%**) |
| Self-host Stage Build Time | 95.0s | 85.6s | -9.4s (**-9.9%**) |

## 8. Acceptance Criteria

Mapping 1:1 with [VIRC-ISS-0015](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0015_oversized_parser_and_lowering_functions_are_single_monolithic_dispatch_chains.md) Section 10:

- [x] `parse_statement_impl` decomposed into 5 submodules under `compiler/src/frontend/parser/stmt_dispatch/`.
- [x] `lower_stmt_control` decomposed into 6 submodules under `compiler/src/lower/ast_to_mir/stmt_control/`.
- [x] All 11 new modules registered in `compiler/module.list`.
- [x] 0 bundle drift (`tools/sync_virc.py --check`).
- [x] 0 dependency violations (`tools/check_module_dependencies.py`).
- [x] CLI contracts (43/43) and module fixtures (5/5) pass.
- [x] Min test suite passes (409/413 historical baseline).
- [x] 3-stage self-hosting fixed point verified bit-identical.
- [x] Linked PLAN `VIRC-PLN-0010` completed and REPORT `VIRC-RPT-0022` accepted.

## 9. Known Limitations

- `lir_func_to_mc_riscv64` in `compiler/src/lower/lir_to_mc/riscv64.vri` (1,102 lines) is a target-specific assembly emitter function with a single large loop over instruction opcodes; it is isolated to RISC-V targets and does not affect host compiler execution.

## 10. Remaining Work

None under `VIRC-ISS-0015` / `VIRC-PLN-0010`.

## 11. Conclusion

`READY_FOR_CLOSE`. All acceptance criteria have been satisfied and verified across all repository quality gates and bit-identical self-hosting fixed point.

## 12. Related Papers

- [VIRC-ISS-0015](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0015_oversized_parser_and_lowering_functions_are_single_monolithic_dispatch_chains.md) — Oversized parser and lowering functions are single monolithic dispatch chains.
- [VIRC-PLN-0010](file:///Users/gengyang/Vir-3.0/papers/VIRC/plans/VIRC-PLN-0010_decompose_monolithic_parser_and_lowering_dispatch_functions_into_submodules.md) — Decompose monolithic parser and lowering dispatch functions into submodules.
- `VIRC-ISS-0011` — Compiler driver is monolithic and generated bundle owns self-referential glue.
- `VIRC-ISS-0012` — Oversized compiler modules mix unrelated declaration groups.

## 13. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Initial report for VIRC-ISS-0015 / VIRC-PLN-0010 completion and closure |
