---
id: "VIRC-RPT-0011"
type: "REPORT"
domain: "VIRC"
title: "Phase 10 Domain 1 parser modularization report"
status: "ACCEPTED"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "parser"
  - "frontend"
components:
  - "frontend-parser"
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
  - "parser"
  - "frontend"
  - "modularization"
  - "phase10"
---

# VIRC-RPT-0011 — Phase 10 Domain 1 parser modularization report

## 1. Executive Summary

In accordance with `VIRC-PLN-0004` Phase 10 Domain 1 and `VIRC-ISS-0006`, the monolithic recursive-descent parser (`compiler/src/frontend/parser.vri`, 5,472 logical lines, 6,131 raw lines) has been decomposed into **9 cohesive leaf submodules** and **1 thin orchestrator** under `compiler/src/frontend/parser/`. The orchestrator `parser.vri` has been reduced to **58 logical lines** (−98.9%), satisfying all orchestrator and leaf LOC constraints (≤ 1,200 logical lines per non-orchestrator file).

## 2. Source Issues

- **VIRC-ISS-0006** — Monolithic compiler pass files exceed 1,200 logical lines and must be split.

## 3. Source Plans

- **VIRC-PLN-0004** Phase 10: Split remaining large compiler domains in order: parser → AST-to-MIR lowering → LIR/codegen → CLI/main → diagnostics → IDE/tool JSON.

## 4. Implementation Summary

The original `compiler/src/frontend/parser.vri` (5,472 logical lines) was partitioned along natural semantic boundaries into:

| Submodule               | Logical Lines | Responsibility                                       |
|-------------------------|---------------|------------------------------------------------------|
| `parser/ast.vri`        | 311           | `AstType`, `ParamMode`, `OpType`, `AstNode`, bump arena, node constructors |
| `parser/builtins.vri`   | 294           | `BuiltinId`, `BuiltinEntry`, hash bucket lookup table |
| `parser/state.vri`      | 420           | `Parser` entity, globals, token navigation, check/match helpers |
| `parser/diagnostics.vri`| 133           | `parserErrorEntry*`, `parse_error_code*`             |
| `parser/expr.vri`       | 1,189         | Expression Pratt parser, unary, binary, postfix, primary, entity literals |
| `parser/stmt_control.vri`| 728          | Blocks, var/const decls, conditionals, loops, return, print |
| `parser/stmt_decl.vri`  | 1,071         | Functions, types, interfaces, entities, molds, enums, for-range |
| `parser/stmt_module.vri`| 259           | `parse_module_or_directive_stmt` (import/get/from/module/export/include/check_cpu/patch) |
| `parser/stmt_dispatch.vri`| 1,082       | Statement dispatcher, assignment detection, `parse_statement`, `parse_statement_impl` |
| `parser.vri` (orch.)    | 58            | Public orchestrator, `parse_program` entry point     |

All 9 leaf submodules satisfy the **≤ 1,200 logical lines** hard constraint.

New module names registered in `compiler/module.list` (lines 25–34):
`parser_ast`, `parser_builtins`, `parser_state`, `parser_diagnostics`,
`parser_expr`, `parser_stmt_control`, `parser_stmt_decl`, `parser_stmt_module`,
`parser_stmt_dispatch`.

## 5. Changes by Component

**`compiler/src/frontend/parser/`** (new directory):
- 9 new leaf files created; content extracted verbatim from original `parser.vri`.
- Each file carries its own `include` / `import` dependencies.

**`compiler/src/frontend/parser.vri`** (modified):
- Reduced from 5,472 to 58 logical lines.
- Now contains only: `include` directives for submodules and `parse_program` entry point.

**`compiler/module.list`**:
- Lines 25–34 added registering 9 new canonical module names.

**`compiler/generated/virc.vri`**:
- Regenerated via `python3 tools/sync_virc.py`; zero drift confirmed by `--check`.
- Bundle size increased by ~644 bytes (due to additional `# @vir_source` markers and `import` lines for submodule boundaries).

## 6. Deviations from Plan

| Deviation | Description | Resolution |
|-----------|-------------|------------|
| `parse_program` truncated | The orchestrator `parser.vri` was written with `else` branch of `parse_program` incomplete (file ended after `else` keyword) | Added complete `else` body and `end.` |
| Stale code in `diagnostics.vri` | Misplaced `parse_program` snippet was prepended to `diagnostics.vri` during extraction (lines 13–35) | Removed spurious lines |
| Duplicate `import` directives | Each submodule header carried redundant `import ideFactTypeUse...` causing duplicate symbol registration | Consolidated: single `import` per symbol per bundle section |
| Missing `rt.alloc` imports | `ast.vri`, `builtins.vri`, `state.vri`, `diagnostics.vri` use `vir_alloc`/`page_alloc`; redundant import was removed too aggressively | Restored `include rt.alloc` + `import vir_alloc, page_alloc from rt.alloc` in each file |

## 7. Verification

All quality gates passed at commit `2e9895e`:

| Gate | Result |
|------|--------|
| `python3 tools/sync_virc.py --check` | ✅ PASS — zero drift |
| Self-compile `/Users/gengyang/Vir/bin/virc compiler/generated/virc.vri -o bin/virc` | ✅ PASS — 2,445 functions, 25,269,588 bytes |
| `codesign -s - -f bin/virc` | ✅ PASS |
| `python3 tests/cli_contract/runner.py` | ✅ **43/43 PASS** |
| `./run_tests.sh min` | ✅ **409/413 PASS** (matches historical baseline) |
| `python3 tools/check_pass_architecture.py` | ✅ PASS |
| `python3 tools/paper.py validate` | ✅ PASS (67 papers) |

## 8. Acceptance Criteria

All criteria from `VIRC-PLN-0004` Phase 10 are satisfied for Domain 1 (Parser):

- [x] No canonical non-generated source file exceeds 1,200 logical lines.
- [x] Submodules registered in `compiler/module.list`.
- [x] Bundle synced with zero drift (`sync_virc.py --check`).
- [x] Self-compile succeeds.
- [x] 43/43 contract tests pass.
- [x] 409/413 spec regression tests pass (historical baseline).
- [x] Architecture gate passes.
- [x] VPS paper validation passes.

## 9. Known Limitations

- The 5 pre-existing `E3007` errors in `compiler/src/semantic/borrow/walk_access.vri` (lines 28, 49) and `walk_call.vri` (lines 78, 109) are **not caused by this change** — they also appear when compiling the unmodified HEAD bundle with the stricter `virc_head_bin` binary. They do not affect compilation by the canonical `/Users/gengyang/Vir/bin/virc` binary.

## 10. Remaining Work

Remaining Phase 10 domains (per `VIRC-PLN-0004` ordering):

1. ~~Parser~~ — **DONE** (this report)
2. **AST-to-MIR lowering** — next
3. **LIR/codegen**
4. **CLI/main**
5. **Diagnostics**
6. **IDE/tool JSON**

## 11. Conclusion

REQUIRES_FOLLOWUP

Phase 10 Domain 1 (parser modularization) is complete. All quality gates pass. Followup is required for the remaining Phase 10 domains (AST-to-MIR lowering, LIR/codegen, CLI/main, diagnostics, IDE/tool JSON) per VIRC-PLN-0004.

## 12. Related Papers

- `VIRC-ISS-0006` — Source issue driving modularization
- `VIRC-PLN-0004` — Overarching modularization plan (Phase 10)
- `VIRC-RPT-0010` — Phase 9: MIR optimization modularization (immediately preceding domain)

## 13. Revision History

| Rev | Date       | Author    | Change                  |
|-----|------------|-----------|-------------------------|
| 1.0 | 2026-10-03 | compiler  | Initial accepted report |
