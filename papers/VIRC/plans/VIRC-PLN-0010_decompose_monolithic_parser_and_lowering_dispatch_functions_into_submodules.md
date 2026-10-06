---
id: "VIRC-PLN-0010"
type: "PLAN"
domain: "VIRC"
title: "Decompose monolithic parser and lowering dispatch functions into submodules"
status: "COMPLETED"
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
  plans: []
  reports:
    - "VIRC-RPT-0022"
supersedes: null
superseded_by: null
tags:
  - "parser-dispatch"
  - "lowering-dispatch"
  - "modularization"
---

# VIRC-PLN-0010 — Decompose monolithic parser and lowering dispatch functions into submodules

## 1. Objective

Refactor the two remaining monolithic dispatch functions (`parse_statement_impl` and `lower_stmt_control`) into modular sub-handlers grouped by language domains, register the new submodules in `compiler/module.list`, synchronize bundle markers, and verify self-hosting bit-identical fixed point.

## 2. Source Issues

- [VIRC-ISS-0015](file:///Users/gengyang/Vir-3.0/papers/VIRC/issues/VIRC-ISS-0015_oversized_parser_and_lowering_functions_are_single_monolithic_dispatch_chains.md)

## 3. Scope

### In Scope
1. **Parser Dispatcher (`compiler/src/frontend/parser/stmt_dispatch.vri`)**:
   - Extract handlers into 5 modules under `compiler/src/frontend/parser/stmt_dispatch/`:
     - `modifiers.vri` (extern, type, async, atomic, precomp, port, send, cancel, quiet, lazy)
     - `declarations.vri` (share, has, collections, reactive/morph, bundle, expose, packed, register, attributes)
     - `concurrency.vri` (select, recv, train, infer, await, arena, resume, isolate, lock, deck)
     - `try_stmt.vri` (try-revert-ensure error handling blocks)
     - `name_stmt.vri` (identifier assignments and expression statements)
2. **MIR Lowering Dispatcher (`compiler/src/lower/ast_to_mir/stmt_control.vri`)**:
   - Extract lowering routines into 6 modules under `compiler/src/lower/ast_to_mir/stmt_control/`:
     - `arena_scan.vri` (escaped variable analysis)
     - `loops.vri` (if, while, loop, block)
     - `jumps.vri` (return, print, break, continue)
     - `pattern.vri` (case, for-range)
     - `error.vri` (ensure, revert, when, throw)
     - `async_arena.vri` (cancel, quiet, arena, emit, select, try, timeout, isolate, resume)
3. **Registration & Bundling**:
   - Register all 11 modules in `compiler/module.list`.
   - Update bundle source markers in `compiler/generated/virc.vri`.
4. **Verification**:
   - All 7 gates passing, CLI contracts, baseline min tests, 3-stage bit-identical self-host fixed point.

### Out of Scope
- Altering parser grammar or error reporting messages.
- Changing MIR opcodes or lowering semantics.

## 4. Current Architecture

- `compiler/src/frontend/parser/stmt_dispatch.vri` contains a single 1,212-line function `parse_statement_impl` containing 68 sequential if-statements.
- `compiler/src/lower/ast_to_mir/stmt_control.vri` contains a single 1,095-line function `lower_stmt_control` containing 23 sequential `AstType` lowering blocks.

## 5. Proposed Architecture

Both dispatchers become thin orchestrators delegating to domain-specific handler functions. Each domain-specific handler function lives in its own submodule with cohesive dependencies and small function scopes.

## 6. Design Decisions

- **Uniform Signature for MIR Lowering**: Every statement lowering helper conforms to `func lower_stmt_<kind>(b: &MirBuilder, stmt: &AstNode): ... end.`, allowing direct delegation from the top-level dispatcher.
- **Syntactic Classification for Parser**: Statement parsers conform to `func parse<Kind>Statement(ref p: Parser, t: Token) -> (Parser, AstNode): ... end.`, preserving parsing state and token locations.

## 7. Implementation Plan

- **Phase 1**: Extract `stmt_dispatch` handlers into 5 submodules; update `module.list` and bundle; verify Stage X1 build and tests.
- **Phase 2**: Extract `stmt_control` lowering into 6 submodules; update `module.list` and bundle; verify Stage 2 build.
- **Phase 3**: Verify CLI contract (43/43), fixtures (5/5), min tests (409/413), and 3-stage self-host fixed point.
- **Phase 4**: Produce REPORT `VIRC-RPT-0022` and close issue.

## 8. Compatibility

Zero functional changes. Syntax, diagnostics, and output binaries remain 100% compatible.

## 9. Migration

Internal compiler source modularization only. No downstream user changes required.

## 10. Validation Plan

1. `python3 tools/sync_virc.py --check` -> 0 drift.
2. `python3 tools/check_module_dependencies.py` -> 0 violations.
3. `python3 tests/cli_contract/runner.py` -> 43/43 PASS.
4. `./run_tests.sh min` -> 409/413 PASS (matches baseline).
5. 3-stage self-host fixed point -> `cmp bin/virc_stage3 bin/virc_stage4` returns bit-identical.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Helper function scope variable leakage | Low | High | Pre-analyzed function-scope bindings and verified signature parity |
| Indentation or token stream discrepancy | Low | High | Full 43/43 contract test and 409-test min test suite validation |

## 12. Rollback Strategy

Restore files via Git and revert to prior checkpoint compiler binary.

## 13. Exit Criteria

- [x] `stmt_dispatch.vri` refactored into thin orchestrator + 5 submodules.
- [x] `stmt_control.vri` refactored into thin orchestrator + 6 submodules.
- [x] 11 new modules registered in `compiler/module.list`.
- [x] All 7 gates pass.
- [x] 3-stage self-host fixed point verified.
- [x] `VIRC-RPT-0022` accepted and `VIRC-ISS-0015` closed.

## 14. Related Papers

- `VIRC-ISS-0015` — Oversized parser and lowering functions are single monolithic dispatch chains.
- `VIRC-RPT-0022` — Decompose monolithic parser and lowering dispatch functions into submodules report.

## 15. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Plan drafted, implemented, and verified |
