---
id: "VIRC-RPT-0012"
type: "REPORT"
domain: "VIRC"
title: "Phase 10 Domain 2 AST-to-MIR lowering modularization report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "lowering"
components:
  - "lowering-ast-to-mir"
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
  - "lowering"
  - "ast-to-mir"
  - "modularization"
  - "phase10"
---

# VIRC-RPT-0012 — Phase 10 Domain 2 AST-to-MIR lowering modularization report

## 1. Executive Summary

In accordance with `VIRC-PLN-0004` Phase 10 Domain 2 and `VIRC-ISS-0006`, the monolithic AST-to-MIR lowering implementation (`compiler/src/lower/ast_to_mir.vri`, 6,776 logical lines, 7,314 raw lines) has been decomposed into **9 cohesive leaf submodules** and **1 thin orchestrator** under `compiler/src/lower/ast_to_mir/`. The orchestrator `ast_to_mir.vri` has been reduced from 6,776 to **132 logical lines** (−98.1%), satisfying all orchestrator and leaf LOC constraints (≤ 1,200 logical lines per non-orchestrator file).

## 2. Source Issues

- **VIRC-ISS-0006** — Monolithic compiler pass files exceed 1,200 logical lines and must be split.

## 3. Source Plans

- **VIRC-PLN-0004** Phase 10: Split remaining large compiler domains in order: parser → AST-to-MIR lowering → LIR/codegen → CLI/main → diagnostics → IDE/tool JSON.

## 4. Implementation Summary

The original `compiler/src/lower/ast_to_mir.vri` (6,776 logical lines) was partitioned along natural functional boundaries into:

| Submodule               | Logical Lines | Responsibility                                       |
|-------------------------|---------------|------------------------------------------------------|
| `ast_to_mir/context.vri`      | 835           | Lowering context, globals, `VarMap`, `LoopTarget`, var types, name hash, `eval_const_expr`, `set_global_prog_ast` |
| `ast_to_mir/layout.vri`       | 1,098         | Enum layouts, variant queries, scoped fields/methods, generics substitution, `infer_expr_type_name`, packed/register layout |
| `ast_to_mir/builder.vri`      | 769           | `MirBuilder` primitives, vreg allocation, block management, low-level emitters (`emit_jump`, `emit_store`, `emit_load`), aggregates, AST query helpers |
| `ast_to_mir/calls.vri`        | 678           | Call args, interpolation segments, error check/prep, ref params, `lower_expr_calls` (`Call`, `BuiltinCall`, `MethodCall`) |
| `ast_to_mir/expr_ops.vri`     | 419           | Binary & unary operations, comparisons, swizzle, task, wait, quantize (`lower_expr_ops`) |
| `ast_to_mir/expr.vri`         | 888           | Literals, identifiers, pattern/exist/map/bundle expressions, array/dict/tuple/entity literals, indexing, field access, `lower_expr_impl`, `lower_expr` |
| `ast_to_mir/stmt_control.vri` | 999           | Control flow & error blocks: `IfStmt`, `WhileStmt`, `LoopStmt`, `Block`, `ReturnStmt`, `BreakStmt`, `ContinueStmt`, `CaseExpr`, `ForRange`, `EnsureBlock`, `RevertBlock`, `WhenStmt`, `ThrowStmt`, `CancelStmt`, `QuietStmt`, `ArenaBlock`, `EmitStmt`, `SelectStmt`, `TryStmt`, `TimeoutClause`, `IsolateClause`, `ResumeStmt`, arena escape scanning |
| `ast_to_mir/stmt.vri`         | 687           | Variable declarations (`VarDeclGroup`, `VarDecl`), assignments (`Assign`, `IndexAssign`, `SwizzleAssign`, `FieldAssign`), `PrintStmt`, miscellaneous statements, `lower_stmt_impl`, `lower_stmt` |
| `ast_to_mir/func.vri`         | 422           | `ast_build_global_init_func`, `ast_lower_func`, `lower_decl_marker`, generic AST cloning & substitution (`clone_ast_with_subst`) |
| `ast_to_mir.vri` (orch.)      | 132           | Thin orchestrator, includes all submodules in topological order, `ast_lower_program`, public exports |

All 9 leaf submodules satisfy the **≤ 1,200 logical lines** hard constraint.

New module names registered in `compiler/module.list` (lines 208–217):
`ast_to_mir_context`, `ast_to_mir_layout`, `ast_to_mir_builder`,
`ast_to_mir_calls`, `ast_to_mir_expr_ops`, `ast_to_mir_expr`,
`ast_to_mir_stmt_control`, `ast_to_mir_stmt`, `ast_to_mir_func`, `ast_to_mir`.

## 5. Changes by Component

**`compiler/src/lower/ast_to_mir/`** (new directory):
- 9 new leaf files created; functional logic extracted from original `ast_to_mir.vri`.
- Each submodule carries its dependencies cleanly.

**`compiler/src/lower/ast_to_mir.vri`** (modified):
- Reduced from 6,776 to 132 logical lines.
- Contains only: submodule `include` directives, `ast_lower_program`, and `export`.

**`compiler/module.list`**:
- Lines 208–217 updated to register the 9 submodules in topological sequence before `ast_to_mir`.

**`compiler/generated/virc.vri`**:
- Synchronized via `python3 tools/sync_virc.py`; zero drift confirmed by `--check`.

## 6. Deviations from Plan

| Deviation | Description | Resolution |
|-----------|-------------|------------|
| MirBuilder handle preservation in `lower_stmt` | In native self-host output, the large `lower_stmt_impl` CFG can occasionally leave a non-pointer integer in X0. The original code used `lowered_b = lower_stmt_impl(b, stmt); out b`. Initial extraction did `out lower_stmt_impl(b, stmt)` which caused SIGSEGV (-11) in two CLI contract tests. | Restored exact `lowered_b = lower_stmt_impl(b, stmt); out b` in `lower_stmt`, and in `lower_stmt_impl` when calling `lower_stmt_control`. Both tests immediately passed. |

## 7. Verification

All quality gates passed at commit `6af2a63`:

| Gate | Result |
|------|--------|
| `python3 tools/sync_virc.py --check` | ✅ PASS — zero drift |
| Self-compile `/Users/gengyang/Vir/bin/virc compiler/generated/virc.vri -o bin/virc` | ✅ PASS — 2,449 functions, 20,047,044 bytes |
| `codesign -s - -f bin/virc` | ✅ PASS |
| `python3 tests/cli_contract/runner.py` | ✅ **43/43 PASS** |
| `./run_tests.sh min` | ✅ **409/413 PASS** (matches historical baseline) |
| `python3 tools/check_pass_architecture.py` | ✅ PASS |
| `python3 tools/paper.py validate` | ✅ PASS (68 papers) |

## 8. Acceptance Criteria

All criteria from `VIRC-PLN-0004` Phase 10 are satisfied for Domain 2 (AST-to-MIR lowering):

- [x] No canonical non-generated source file exceeds 1,200 logical lines.
- [x] Submodules registered in `compiler/module.list`.
- [x] Bundle synced with zero drift (`sync_virc.py --check`).
- [x] Self-compile succeeds.
- [x] 43/43 contract tests pass.
- [x] 409/413 spec regression tests pass (historical baseline).
- [x] Architecture gate passes.
- [x] VPS paper validation passes.

## 9. Known Limitations

- None introduced by this change. The 4 pre-existing failures in `./run_tests.sh min` are unchanged.

## 10. Remaining Work

Remaining Phase 10 domains (per `VIRC-PLN-0004` ordering):

1. ~~Parser~~ — **DONE** (`VIRC-RPT-0011`)
2. ~~AST-to-MIR lowering~~ — **DONE** (this report)
3. **LIR/codegen** — next
4. **CLI/main**
5. **Diagnostics**
6. **IDE/tool JSON**

## 11. Conclusion

REQUIRES_FOLLOWUP

Phase 10 Domain 2 (AST-to-MIR lowering modularization) is complete. All quality gates pass. Followup is required for the remaining Phase 10 domains (LIR/codegen, CLI/main, diagnostics, IDE/tool JSON) per VIRC-PLN-0004.

## 12. Related Papers

- `VIRC-ISS-0006` — Source issue driving modularization
- `VIRC-PLN-0004` — Overarching modularization plan (Phase 10)
- `VIRC-RPT-0011` — Phase 10 Domain 1: Parser modularization report

## 13. Revision History

| Rev | Date       | Author    | Change                  |
|-----|------------|-----------|-------------------------|
| 1.0 | 2026-10-03 | compiler  | Initial accepted report |
